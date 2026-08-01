"use client";

import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/components/DemandWorkspace";

const SAMPLE_PROMPTS = [
  "嘉義市水龍頭漏水，預算兩千",
  "下週六想找人來大掃除，三房兩廳",
  "想訂 10 人份的便當送到社區活動中心",
];

type Props = {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  onSubmit: (prompt: string) => void;
};

export default function ChatPanel({
  messages,
  loading,
  error,
  onSubmit,
}: Props) {
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Keep the newest message in view.
    logRef.current?.scrollTo({
      top: logRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  const canSend = draft.trim().length > 0 && !loading;

  function send() {
    if (!canSend) return;
    onSubmit(draft.trim());
    setDraft("");
  }

  return (
    <section
      aria-labelledby="chat-heading"
      className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <h2 id="chat-heading" className="text-base font-semibold text-slate-900">
          AI 對話
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
          <EmptyState onPick={(p) => setDraft(p)} disabled={loading} />
        ) : (
          messages.map((m) => <Bubble key={m.id} message={m} />)
        )}

        {loading ? <TypingBubble /> : null}
      </div>

      {error ? (
        <p
          role="alert"
          className="mx-5 mb-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800"
        >
          {error}
        </p>
      ) : null}

      <div className="border-t border-slate-100 p-4">
        <label htmlFor="demand-input" className="sr-only">
          輸入你的生活需求
        </label>
        <textarea
          id="demand-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          rows={3}
          disabled={loading}
          placeholder="例如：嘉義市水龍頭漏水，預算兩千"
          className="w-full resize-none rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:bg-slate-50"
        />
        <div className="mt-3 flex items-center justify-between gap-3">
          <p className="text-xs text-slate-500">
            Enter 送出，Shift + Enter 換行
          </p>
          <button
            type="button"
            onClick={send}
            disabled={!canSend}
            className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {loading ? (
              <>
                <Spinner />
                解析中…
              </>
            ) : (
              "送出需求"
            )}
          </button>
        </div>
      </div>
    </section>
  );
}

function EmptyState({
  onPick,
  disabled,
}: {
  onPick: (prompt: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="space-y-4 py-6">
      <p className="text-sm text-slate-600">
        用一句話描述你需要的服務，AI 會幫你整理成可派工的任務。
      </p>
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
          試試這些
        </p>
        {SAMPLE_PROMPTS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPick(p)}
            disabled={disabled}
            className="block w-full rounded-lg border border-dashed border-slate-300 px-3 py-2 text-left text-sm text-slate-700 transition hover:border-sky-400 hover:bg-sky-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-50"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
          isUser
            ? "rounded-br-md bg-sky-600 text-white"
            : "rounded-bl-md bg-slate-100 text-slate-800"
        }`}
      >
        <span className="sr-only">{isUser ? "你說：" : "AI 回覆："}</span>
        {message.text}
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-slate-100 px-4 py-3 text-sm text-slate-600">
        <Spinner />
        AI 正在解析你的需求…
      </div>
    </div>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
    />
  );
}
