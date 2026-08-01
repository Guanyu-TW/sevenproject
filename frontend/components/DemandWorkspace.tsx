"use client";

import { useCallback, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import TaskResultPanel from "@/components/TaskResultPanel";
import {
  ApiError,
  DuplicateCaseError,
  analyzeDemand,
  createCase,
  getCase,
  matchVendors,
  updateTask,
  type ConsultationCase,
  type LifeTask,
  type MatchVendorsResponse,
  type VendorRecommendation,
} from "@/lib/api";

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

function describeError(err: unknown, prefix: string): string {
  if (err instanceof ApiError) return `${prefix}（${err.status}）：${err.message}`;
  if (err instanceof Error) return `${prefix}：${err.message}`;
  return `${prefix}：發生未知錯誤`;
}

/** Owns the shared state between the chat column and the result column. */
export default function DemandWorkspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [task, setTask] = useState<LifeTask | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matchResult, setMatchResult] = useState<MatchVendorsResponse | null>(null);
  const [caseDetail, setCaseDetail] = useState<ConsultationCase | null>(null);
  const [creatingCaseFor, setCreatingCaseFor] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef<AbortController | null>(null);

  const say = useCallback((role: ChatMessage["role"], text: string) => {
    setMessages((prev) => [...prev, { id: nextId(), role, text }]);
  }, []);

  const submit = useCallback(
    async (prompt: string) => {
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;

      setError(null);
      setAnalyzing(true);
      // A new demand invalidates any previous vendor list and case.
      setMatchResult(null);
      setCaseDetail(null);
      say("user", prompt);

      try {
        const result = await analyzeDemand(prompt, controller.signal);
        setTask(result);

        const missing = result.missing_fields;
        const title = result.parsed_data.title ?? "任務";

        if (result.category === null) {
          // Unclassified demands cannot be matched, so do not promise a form.
          say(
            "assistant",
            `我把這句話理解成「${title}」，但它不屬於平台目前提供的服務分類，` +
              "所以沒辦法幫你媒合廠商。目前支援水電維修、居家清潔、餐飲訂購與代購採買。",
          );
        } else {
          say(
            "assistant",
            missing.length > 0
              ? `我把需求整理成「${title}」，分類是${result.category.name}。` +
                  `還缺少 ${missing.map((f) => f.label).join("、")}，` +
                  "請在右邊補齊後按「確認並尋找廠商」。"
              : `我把需求整理成「${title}」，分類是${result.category.name}，` +
                  "資料已經完整，可以直接按「確認並尋找廠商」。",
          );
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        const message = describeError(err, "解析失敗");
        setError(message);
        say("assistant", "抱歉，這次解析沒有成功。");
      } finally {
        if (!controller.signal.aborted) setAnalyzing(false);
      }
    },
    [say],
  );

  /**
   * Two sequential calls: persist the form and flip the status, then match.
   * Matching is only attempted after the PATCH succeeds, because the matching
   * endpoint refuses anything that is not ready_for_matching.
   */
  const confirmAndMatch = useCallback(
    async (filled: Record<string, string>) => {
      if (!task) return;

      const controller = new AbortController();
      inFlight.current = controller;

      setError(null);
      setMatching(true);

      const filledCount = Object.keys(filled).length;
      say(
        "user",
        filledCount > 0
          ? `我補上了 ${filledCount} 項資料，請幫我找廠商。`
          : "請幫我找廠商。",
      );

      // Tracks which of the two calls failed so the message names the right step.
      let stage: "save" | "match" = "save";
      try {
        const updated = await updateTask(
          task.id,
          { filled_fields: filled, status: "ready_for_matching" },
          controller.signal,
        );
        setTask(updated);

        stage = "match";
        const result = await matchVendors(updated.id, 3, controller.signal);
        setMatchResult(result);

        if (result.recommendations.length === 0) {
          say(
            "assistant",
            `${updated.category?.name ?? "這個服務類型"}在你的地區還沒有合作廠商，` +
              "可以試著調整地區或服務項目。",
          );
        } else {
          const names = result.recommendations.map((v) => v.name).join("、");
          say(
            "assistant",
            `資料已存檔，任務狀態轉為「待媒合」。` +
              `符合條件的廠商有 ${result.candidate_count} 家，` +
              `我推薦這 ${result.recommendations.length} 家：${names}。` +
              "右邊可以看到每一家的推薦原因。",
          );
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(
          describeError(err, stage === "save" ? "資料存檔失敗" : "媒合失敗"),
        );
        say(
          "assistant",
          stage === "save"
            ? "抱歉，這次沒有成功存檔，需求還留在原地。"
            : "抱歉，這次沒有成功找到廠商。",
        );
      } finally {
        if (!controller.signal.aborted) setMatching(false);
      }
    },
    [task, say],
  );

  /**
   * Turn a recommendation into a real ConsultationCase.
   *
   * A duplicate (409) is not treated as a failure: the API hands back the
   * existing case id, so we load it and show the tracking board instead of
   * making the resident wonder what went wrong.
   */
  const selectVendor = useCallback(
    async (vendor: VendorRecommendation) => {
      if (!task) return;

      const controller = new AbortController();
      inFlight.current = controller;

      setError(null);
      setCreatingCaseFor(vendor.vendor_id);
      say("user", `我選擇「${vendor.name}」，請幫我建立案件。`);

      try {
        const created = await createCase(
          {
            taskId: task.id,
            selectedVendorId: vendor.vendor_id,
            formData: (task.parsed_data ?? {}) as Record<string, unknown>,
            estimatedPrice: vendor.estimated_price ?? null,
            recommendationReason: vendor.recommendation_reason,
          },
          controller.signal,
        );
        setCaseDetail(created);
        say(
          "assistant",
          `案件 ${created.case_number} 已建立，狀態是「${created.status_label}」。` +
            `${created.next_action ?? ""}` +
            "完整地址與聯絡電話還沒提供給廠商，等你確認後才會交換。",
        );
      } catch (err) {
        if (controller.signal.aborted) return;

        if (err instanceof DuplicateCaseError) {
          try {
            const existing = await getCase(err.detail.case_id, controller.signal);
            setCaseDetail(existing);
            say(
              "assistant",
              `這個需求已經建立過案件 ${existing.case_number}` +
                `（${existing.status_label}），我直接帶你看進度，不會重複建單。`,
            );
            return;
          } catch {
            setError(err.detail.message);
            return;
          }
        }

        setError(describeError(err, "建立案件失敗"));
        say("assistant", "抱歉，這次沒有成功建立案件。");
      } finally {
        if (!controller.signal.aborted) setCreatingCaseFor(null);
      }
    },
    [task, say],
  );

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-5 lg:grid-cols-2">
      <ChatPanel
        messages={messages}
        loading={analyzing || matching || creatingCaseFor !== null}
        error={error}
        onSubmit={(prompt) => void submit(prompt)}
      />
      <TaskResultPanel
        task={task}
        loading={analyzing}
        matching={matching}
        matchResult={matchResult}
        caseDetail={caseDetail}
        creatingCaseFor={creatingCaseFor}
        onConfirm={(filled) => void confirmAndMatch(filled)}
        onBackToTask={() => setMatchResult(null)}
        onSelectVendor={(vendor) => void selectVendor(vendor)}
        onBackToVendors={() => setCaseDetail(null)}
      />
    </div>
  );
}
