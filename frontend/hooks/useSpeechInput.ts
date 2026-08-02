"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Thin wrapper over the browser's SpeechRecognition.
 *
 * Not in the DOM lib types yet, and still vendor-prefixed in Chromium, so the
 * surface is declared here rather than reaching for `any` at each call site.
 */
type SpeechRecognitionAlternative = { transcript: string; confidence: number };
type SpeechRecognitionResult = {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionAlternative;
};
type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: { length: number; [index: number]: SpeechRecognitionResult };
};
type SpeechRecognitionErrorEventLike = { error: string };

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
};

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** Plain-language reasons, because the raw codes mean nothing to a resident. */
const ERROR_TEXT: Record<string, string> = {
  "not-allowed":
    "瀏覽器擋住了麥克風。請在網址列左側的圖示裡允許麥克風權限後再試一次。",
  "service-not-allowed":
    "瀏覽器擋住了麥克風。請在網址列左側的圖示裡允許麥克風權限後再試一次。",
  "no-speech": "沒有聽到聲音，請靠近麥克風再說一次。",
  "audio-capture": "找不到可用的麥克風，請確認裝置有接上收音設備。",
  network: "語音辨識需要連線，目前網路好像不通。",
  aborted: "語音輸入已取消。",
};

export type SpeechInputState = {
  /** False when the browser has no SpeechRecognition at all. */
  supported: boolean;
  listening: boolean;
  /** Words recognised but not yet finalised, for live feedback. */
  interim: string;
  error: string | null;
  start: () => void;
  stop: () => void;
  clearError: () => void;
};

/**
 * @param onResult Called with each finalised chunk of speech.
 * @param lang     BCP-47 tag; defaults to Taiwanese Mandarin.
 */
export function useSpeechInput(
  onResult: (text: string) => void,
  lang = "zh-TW",
): SpeechInputState {
  // Resolved in an effect, not during render: touching `window` while
  // rendering makes the server and the first client pass disagree.
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognition = useRef<SpeechRecognitionLike | null>(null);
  // Kept in a ref so restarting recognition does not need a new callback.
  const handler = useRef(onResult);
  handler.current = onResult;

  useEffect(() => {
    setSupported(getCtor() !== null);
  }, []);

  useEffect(() => {
    return () => {
      // Leaving the page while the mic is hot would keep the indicator on.
      recognition.current?.abort();
      recognition.current = null;
    };
  }, []);

  const start = useCallback(() => {
    const Ctor = getCtor();
    if (Ctor === null) {
      setError("這個瀏覽器不支援語音輸入，請改用文字輸入。");
      return;
    }
    if (recognition.current !== null) return;

    setError(null);
    setInterim("");

    const instance = new Ctor();
    instance.lang = lang;
    // continuous lets a slow speaker pause mid-sentence without being cut off.
    instance.continuous = true;
    instance.interimResults = true;
    instance.maxAlternatives = 1;

    instance.onstart = () => setListening(true);

    instance.onresult = (event) => {
      let pending = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) handler.current(text.trim());
        else pending += text;
      }
      setInterim(pending);
    };

    instance.onerror = (event) => {
      // A plain "no speech yet" is not worth shouting about while listening.
      if (event.error === "no-speech" && recognition.current !== null) return;
      setError(ERROR_TEXT[event.error] ?? `語音辨識失敗（${event.error}）。`);
    };

    instance.onend = () => {
      setListening(false);
      setInterim("");
      recognition.current = null;
    };

    recognition.current = instance;
    try {
      instance.start();
    } catch {
      // start() throws if called twice in a row; treat it as already running.
      recognition.current = instance;
    }
  }, [lang]);

  const stop = useCallback(() => {
    const instance = recognition.current;
    if (instance === null) return;
    // stop() flushes the last phrase; abort() would throw it away.
    instance.stop();
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { supported, listening, interim, error, start, stop, clearError };
}
