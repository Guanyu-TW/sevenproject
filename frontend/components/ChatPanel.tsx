"use client";

import { Mic, MicOff, Send, Sparkles, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/components/DemandWorkspace";
import { ErrorPanel, Spinner } from "@/components/ui/Feedback";
import { useSpeechInput } from "@/hooks/useSpeechInput";

// Spread across categories on purpose. With only plumbing samples every demo
// task came back looking identical, which made the vendor portal look like it
// only understood one kind of job.
const SAMPLE_PROMPTS = [
  "嘉義市水龍頭漏水，預算兩千",
  "嘉義市西區跳電好幾次，插座沒電了",
  "嘉義市西區冷氣不冷還會滴水，想找人來洗",
  "嘉義市東區馬桶阻塞沖不下去，很急",
  "嘉義市西區想在客廳裝兩盞吸頂燈",
  "下週六想找人來大掃除，三房兩廳",
  "嘉義市西區想找人陪我媽去醫院復健，每週兩次",
  "想訂 10 人份的便當送到社區活動中心",
];

type Props = {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  onSubmit: (prompt: string) => void;
  /** Re-runs whatever failed, so the error can be recovered in place. */
  onRetry?: () => void;
};

export default function ChatPanel({
  messages,
  loading,
  error,
  onSubmit,
  onRetry,
}: Props) {
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  /** Speech arrives in chunks; append rather than replace what is typed. */
  const appendSpeech = useCallback((text: string) => {
    if (!text) return;
    setDraft((prev) => (prev ? `${prev}${prev.endsWith("，") ? "" : "，"}${text}` : text));
  }, []);

  const speech = useSpeechInput(appendSpeech);

  useEffect(() => {
    logRef.current?.scrollTo({
      top: logRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  // Bringing focus back after dictation means Enter can send straight away.
  useEffect(() => {
    if (!speech.listening) inputRef.current?.focus();
  }, [speech.listening]);

  const canSend = draft.trim().length > 0 && !loading;

  function send() {
    if (!canSend) return;
    if (speech.listening) speech.stop();
    onSubmit(draft.trim());
    setDraft("");
  }

  return (
    <section
      aria-labelledby="chat-heading"
      className="animate-rise flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <h2
          id="chat-heading"
          className="flex items-center gap-2 text-base font-semibold text-slate-900"
        >
          <Sparkles aria-hidden="true" className="h-4 w-4 text-sky-600" />
          與智慧管家對話
        </h2>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
          說出你的生活需求
        </span>
      </header>

      <div
        ref={logRef}
        role="log"
        aria-live="polite"
        aria-busy={loading}
        className="flex-1 space-y-3 overflow-y-auto px-5 py-4"
      >
        {messages.length === 0 ? (
          <EmptyPrompts onPick={(p) => setDraft(p)} disabled={loading} />
        ) : (
          messages.map((m) => <Bubble key={m.id} message={m} />)
        )}

        {loading ? <TypingBubble /> : null}
      </div>

      {error ? (
        <div className="mx-5 mb-3">
          <ErrorPanel message={error} onRetry={onRetry} retrying={loading} />
        </div>
      ) : null}

      {speech.error ? (
        <p
          role="alert"
          className="animate-fade-in mx-5 mb-3 flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900"
        >
          <MicOff aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="flex-1">{speech.error}</span>
          <button
            type="button"
            onClick={speech.clearError}
            className="shrink-0 font-semibold underline underline-offset-2"
          >
            關閉
          </button>
        </p>
      ) : null}

      <div className="border-t border-slate-100 p-4">
        <label htmlFor="demand-input" className="sr-only">
          輸入你的生活需求
        </label>
        <div className="relative">
          <textarea
            id="demand-input"
            ref={inputRef}
            value={
              speech.interim ? `${draft}${draft ? "" : ""}${speech.interim}` : draft
            }
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={3}
            disabled={loading}
            placeholder={
              speech.listening
                ? "正在聆聽，請開始說話…"
                : "例如：嘉義市水龍頭漏水，預算兩千"
            }
            className={`w-full resize-none rounded-xl border px-3 py-2 pr-12 text-sm text-slate-900 transition placeholder:text-slate-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:bg-slate-50 ${
              speech.listening
                ? "border-rose-400 bg-rose-50/40"
                : "border-slate-300 focus:border-sky-500"
            }`}
          />

          {speech.supported ? (
            <MicButton
              listening={speech.listening}
              disabled={loading}
              onStart={speech.start}
              onStop={speech.stop}
            />
          ) : null}
        </div>

        {speech.listening ? (
          <p
            aria-live="polite"
            className="animate-fade-in mt-2 flex items-center gap-2 text-xs font-medium text-rose-700"
          >
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ripple absolute inset-0 rounded-full bg-rose-500" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-rose-600" />
            </span>
            正在聆聽…說完後再按一次麥克風就會送進輸入框
          </p>
        ) : null}

        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            {speech.supported
              ? "可以直接說話，或打字後按 Enter 送出"
              : "Enter 送出，Shift + Enter 換行"}
          </p>
          <button
            type="button"
            onClick={send}
            disabled={!canSend}
            className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {loading ? (
              <>
                <Spinner className="h-3.5 w-3.5" />
                處理中…
              </>
            ) : (
              <>
                <Send aria-hidden="true" className="h-3.5 w-3.5" />
                送出需求
              </>
            )}
          </button>
        </div>
      </div>
    </section>
  );
}

function MicButton({
  listening,
  disabled,
  onStart,
  onStop,
}: {
  listening: boolean;
  disabled: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  return (
    <button
      type="button"
      id="voice-button"
      onClick={listening ? onStop : onStart}
      disabled={disabled}
      aria-pressed={listening}
      aria-label={listening ? "停止語音輸入" : "使用語音輸入"}
      className={`absolute bottom-2 right-2 flex h-9 w-9 items-center justify-center rounded-full transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 ${
        listening
          ? "bg-rose-600 text-white focus-visible:ring-rose-500"
          : "bg-slate-100 text-slate-600 hover:bg-sky-100 hover:text-sky-700 focus-visible:ring-sky-500"
      }`}
    >
      {listening ? (
        <>
          <span
            aria-hidden="true"
            className="animate-ripple absolute inset-0 rounded-full bg-rose-500"
          />
          <Square className="relative h-3.5 w-3.5" fill="currentColor" />
        </>
      ) : (
        <Mic className="h-4 w-4" strokeWidth={1.9} />
      )}
    </button>
  );
}

function EmptyPrompts({
  onPick,
  disabled,
}: {
  onPick: (prompt: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="animate-fade-in space-y-4 py-4">
      <p className="text-sm text-slate-600">
        用一句話描述你需要的服務，智慧管家會幫你整理成可派工的任務。
      </p>
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
          試試這些
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {SAMPLE_PROMPTS.map((p, i) => (
            <button
              key={p}
              type="button"
              onClick={() => onPick(p)}
              disabled={disabled}
              style={{ animationDelay: `${i * 40}ms` }}
              className="animate-pop block w-full rounded-lg border border-dashed border-slate-300 px-3 py-2 text-left text-sm text-slate-700 transition hover:border-sky-400 hover:bg-sky-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-50"
            >
              {p}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`animate-rise flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
          isUser
            ? "rounded-br-md bg-sky-600 text-white"
            : "rounded-bl-md bg-slate-100 text-slate-800"
        }`}
      >
        <span className="sr-only">{isUser ? "你說：" : "智慧管家回覆："}</span>
        {message.text}
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="animate-fade-in flex justify-start">
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3 text-sm text-slate-600">
        <Spinner className="h-3.5 w-3.5" />
        智慧管家正在處理您的需求…
      </div>
    </div>
  );
}
