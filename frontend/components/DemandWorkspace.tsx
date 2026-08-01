"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import TaskResultPanel from "@/components/TaskResultPanel";
import {
  ApiError,
  DuplicateCaseError,
  analyzeDemand,
  completeCase,
  confirmCase,
  createCase,
  getCase,
  getTask,
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

/** Statuses where the vendor may still act, so the board keeps polling. */
const POLLED_STATUSES = new Set(["waiting_vendor_response", "contact_shared"]);

function describeStatusChange(fresh: ConsultationCase): string {
  const tail = fresh.next_action ?? "";
  switch (fresh.status) {
    case "vendor_accepted":
      return `好消息，${fresh.vendor.name} 已經接單了！${tail}`;
    case "vendor_rejected":
      return `${fresh.vendor.name} 婉拒了這次委託。${tail}`;
    case "completed":
      return `${fresh.vendor.name} 已標記服務完成。${tail}`;
    default:
      return `案件狀態更新為「${fresh.status_label}」。${tail}`;
  }
}

/**
 * Put the current task / case in the query string.
 *
 * Everything in this workspace used to live in component state alone, so
 * switching to the dashboard or refreshing threw the case away -- and with it
 * the only button that could confirm a quote, which left cases stuck at
 * vendor_accepted forever. The URL is the cheapest durable place to keep the
 * pointer, and it makes the page linkable from the dashboard.
 */
function syncUrl(params: { task?: number | null; case?: number | null }) {
  if (typeof window === "undefined") return;
  const url = new URL(window.location.href);
  const apply = (key: string, value: number | null | undefined) => {
    if (value == null) url.searchParams.delete(key);
    else url.searchParams.set(key, String(value));
  };
  apply("task", params.task);
  apply("case", params.case);
  // replaceState, not push: the back button should leave the page rather than
  // walk backwards through one resident's own progress.
  window.history.replaceState(null, "", url.toString());
}

function readUrlIds(): { taskId: number | null; caseId: number | null } {
  if (typeof window === "undefined") return { taskId: null, caseId: null };
  const q = new URLSearchParams(window.location.search);
  const num = (key: string) => {
    const raw = Number(q.get(key));
    return Number.isInteger(raw) && raw > 0 ? raw : null;
  };
  return { taskId: num("task"), caseId: num("case") };
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
  const [busyAction, setBusyAction] = useState<"confirm" | "complete" | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Starts false and is raised inside the mount effect. Seeding it from
  // window.location here instead would make the server render `false` and the
  // first client render `true`, which is a hydration mismatch.
  const [restoring, setRestoring] = useState(false);
  const inFlight = useRef<AbortController | null>(null);

  const say = useCallback((role: ChatMessage["role"], text: string) => {
    setMessages((prev) => [...prev, { id: nextId(), role, text }]);
  }, []);

  /**
   * Reopen whatever ?task= / ?case= points at, so the dashboard can link
   * straight back into a request and a refresh no longer loses it.
   */
  useEffect(() => {
    const { taskId, caseId } = readUrlIds();
    if (taskId === null && caseId === null) return;

    setRestoring(true);
    const controller = new AbortController();
    (async () => {
      try {
        if (caseId !== null) {
          const restored = await getCase(caseId, controller.signal);
          if (controller.signal.aborted) return;
          setCaseDetail(restored);
          try {
            setTask(await getTask(restored.task_id, controller.signal));
          } catch {
            // The board renders from the case alone; the task is a nicety.
          }
          if (controller.signal.aborted) return;
          say(
            "assistant",
            `幫你叫出案件 ${restored.case_number}（${restored.status_label}）。` +
              `${restored.next_action ?? ""}`,
          );
          return;
        }

        const restored = await getTask(taskId as number, controller.signal);
        if (controller.signal.aborted) return;
        setTask(restored);
        const title = restored.parsed_data.title ?? `任務 #${restored.id}`;
        say(
          "assistant",
          restored.missing_fields.length > 0
            ? `幫你叫出「${title}」，還缺少 ` +
                `${restored.missing_fields.map((f) => f.label).join("、")}，` +
                "補齊後按「確認並尋找廠商」。"
            : `幫你叫出「${title}」，資料已完整，可以直接按「確認並尋找廠商」。`,
        );
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(describeError(err, "讀取先前的需求失敗"));
      } finally {
        if (!controller.signal.aborted) setRestoring(false);
      }
    })();

    return () => controller.abort();
    // Runs once on mount: the URL is read imperatively, not tracked as state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        syncUrl({ task: result.id, case: null });

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
        syncUrl({ task: created.task_id, case: created.id });
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
            syncUrl({ task: existing.task_id, case: existing.id });
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

  /**
   * Poll while the case is waiting on the vendor, so accepting in the vendor
   * portal shows up here without a manual refresh. Stops as soon as the case
   * reaches a state that only the resident can move.
   */
  useEffect(() => {
    if (!caseDetail) return;
    // Poll while the other side could still move the case. Terminal states and
    // "waiting on the resident" need no polling.
    if (!POLLED_STATUSES.has(caseDetail.status)) return;

    const controller = new AbortController();
    const timer = setInterval(async () => {
      try {
        const fresh = await getCase(caseDetail.id, controller.signal);
        if (fresh.status !== caseDetail.status) {
          setCaseDetail(fresh);
          say("assistant", describeStatusChange(fresh));
        }
      } catch {
        // Transient failure; the next tick retries.
      }
    }, 4000);

    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [caseDetail, say]);

  /** Resident accepts the quote, handing their contact details to the vendor. */
  const confirmContact = useCallback(async () => {
    if (!caseDetail) return;
    setBusyAction("confirm");
    setError(null);
    say("user", "我確認這位廠商的報價與時間，請提供我的聯絡資訊。");
    try {
      const updated = await confirmCase(caseDetail.id);
      setCaseDetail(updated);
      say(
        "assistant",
        `已把完整地址與聯絡電話提供給 ${updated.vendor.name}。` +
          `${updated.next_action ?? ""}`,
      );
    } catch (err) {
      setError(describeError(err, "確認失敗"));
      say("assistant", "抱歉，這次確認沒有成功。");
    } finally {
      setBusyAction(null);
    }
  }, [caseDetail, say]);

  const markComplete = useCallback(async () => {
    if (!caseDetail) return;
    setBusyAction("complete");
    setError(null);
    say("user", "服務已經完成了。");
    try {
      const updated = await completeCase(caseDetail.id, "consumer");
      setCaseDetail(updated);
      // The task is closed now, so the workspace's copy is stale.
      setTask((prev) =>
        prev && prev.id === updated.task_id
          ? { ...prev, status: updated.task_status, next_action: updated.next_action }
          : prev,
      );
      say("assistant", `案件 ${updated.case_number} 已標記完成。感謝您的使用！`);
    } catch (err) {
      setError(describeError(err, "標記完成失敗"));
      say("assistant", "抱歉，這次標記沒有成功。");
    } finally {
      setBusyAction(null);
    }
  }, [caseDetail, say]);

  const refreshCase = useCallback(async () => {
    if (!caseDetail) return;
    try {
      setCaseDetail(await getCase(caseDetail.id));
    } catch (err) {
      setError(describeError(err, "更新案件失敗"));
    }
  }, [caseDetail]);

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 gap-5 lg:grid-cols-2">
      <ChatPanel
        messages={messages}
        loading={analyzing || matching || creatingCaseFor !== null || restoring}
        error={error}
        onSubmit={(prompt) => void submit(prompt)}
      />
      <TaskResultPanel
        task={task}
        loading={analyzing || restoring}
        matching={matching}
        matchResult={matchResult}
        caseDetail={caseDetail}
        creatingCaseFor={creatingCaseFor}
        onConfirm={(filled) => void confirmAndMatch(filled)}
        onBackToTask={() => setMatchResult(null)}
        onSelectVendor={(vendor) => void selectVendor(vendor)}
        onBackToVendors={() => {
          setCaseDetail(null);
          syncUrl({ task: task?.id ?? null, case: null });
        }}
        onRefreshCase={() => void refreshCase()}
        onConfirmContact={() => void confirmContact()}
        onCompleteCase={() => void markComplete()}
        busyAction={busyAction}
      />
    </div>
  );
}
