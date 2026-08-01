"use client";

import { useCallback, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import TaskResultPanel from "@/components/TaskResultPanel";
import { ApiError, analyzeDemand, type LifeTask } from "@/lib/api";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

let messageSeq = 0;
function nextId(): string {
  messageSeq += 1;
  return `m${messageSeq}`;
}

/** Owns the shared state between the chat column and the result column. */
export default function DemandWorkspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [task, setTask] = useState<LifeTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const submit = useCallback(async (prompt: string) => {
    inFlight.current?.abort();
    const controller = new AbortController();
    inFlight.current = controller;

    setError(null);
    setLoading(true);
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", text: prompt },
    ]);

    try {
      const result = await analyzeDemand(prompt, controller.signal);
      setTask(result);

      const missing = result.missing_fields;
      const reply =
        missing.length > 0
          ? `我把需求整理成「${result.parsed_data.title ?? "任務"}」，` +
            `分類是${result.category?.name ?? "未分類"}。` +
            `還缺少 ${missing.map((f) => f.label).join("、")}，補上之後就能開始媒合。`
          : `我把需求整理成「${result.parsed_data.title ?? "任務"}」，資料已經完整，可以開始媒合。`;

      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", text: reply },
      ]);
    } catch (err) {
      if (controller.signal.aborted) return;

      const message =
        err instanceof ApiError
          ? `解析失敗（${err.status}）：${err.message}`
          : err instanceof Error
            ? `無法連線至後端 API：${err.message}`
            : "發生未知錯誤";
      setError(message);
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", text: "抱歉，這次解析沒有成功。" },
      ]);
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, []);

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-5 lg:grid-cols-2">
      <ChatPanel
        messages={messages}
        loading={loading}
        error={error}
        onSubmit={(prompt) => void submit(prompt)}
      />
      <TaskResultPanel task={task} loading={loading} />
    </div>
  );
}
