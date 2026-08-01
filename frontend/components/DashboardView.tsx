"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import TaskConditionsForm from "@/components/TaskConditionsForm";
import {
  ApiError,
  completeCase,
  confirmCase,
  fetchDashboard,
  type BadgeTone,
  type DashboardResponse,
  type DashboardTaskItem,
} from "@/lib/api";

/** Badge styling per coarse tone. The text itself comes from the API. */
const TONES: Record<BadgeTone, { dot: string; chip: string }> = {
  draft: { dot: "⚪", chip: "bg-slate-100 text-slate-700 ring-slate-300" },
  pending: { dot: "🟡", chip: "bg-amber-100 text-amber-900 ring-amber-300" },
  active: { dot: "🟢", chip: "bg-emerald-100 text-emerald-900 ring-emerald-300" },
  done: { dot: "🔵", chip: "bg-sky-100 text-sky-900 ring-sky-300" },
  failed: { dot: "🔴", chip: "bg-rose-100 text-rose-900 ring-rose-300" },
};

type Filter = "all" | BadgeTone;

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "active", label: "處理中" },
  { key: "pending", label: "等待中" },
  { key: "draft", label: "未完成" },
  { key: "failed", label: "已婉拒／取消" },
  { key: "done", label: "已完成" },
];

export default function DashboardView() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  /** Which card has its edit form open. */
  const [editing, setEditing] = useState<number | null>(null);
  /** Which case has a confirm / complete request in flight. */
  const [busyCase, setBusyCase] = useState<number | null>(null);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchDashboard(50, signal));
    } catch (err) {
      if (signal?.aborted) return;
      setError(
        err instanceof ApiError
          ? `讀取儀表板失敗（${err.status}）：${err.message}`
          : "無法連線至後端 API",
      );
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const visible = useMemo(() => {
    const tasks = data?.tasks ?? [];
    return filter === "all"
      ? tasks
      : tasks.filter((t) => t.badge_tone === filter);
  }, [data, filter]);

  /**
   * Confirm the quote or close the case straight from the dashboard.
   *
   * These used to live only on the consumer workspace's tracking board, which
   * was unreachable once you navigated away -- so a case that reached
   * vendor_accepted could never be confirmed and both sides stayed locked.
   */
  const act = useCallback(
    async (caseId: number, action: "confirm" | "complete") => {
      setBusyCase(caseId);
      setError(null);
      try {
        if (action === "confirm") await confirmCase(caseId);
        else await completeCase(caseId, "consumer");
        await load();
      } catch (err) {
        setError(
          err instanceof ApiError
            ? `${action === "confirm" ? "確認" : "標記完成"}失敗（${err.status}）：${err.message}`
            : "無法連線至後端 API",
        );
      } finally {
        setBusyCase(null);
      }
    },
    [load],
  );

  const stats = data?.stats;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5">
      <section aria-labelledby="stats-heading">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 id="stats-heading" className="text-sm font-semibold text-slate-900">
            狀態統計
            {data ? (
              <span className="ml-2 font-normal text-slate-500">
                {data.user.name}
              </span>
            ) : null}
          </h2>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-50"
          >
            {loading ? "更新中…" : "重新整理"}
          </button>
        </div>

        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatCard
            label="進行中案件"
            value={stats?.in_progress}
            tone="active"
            hint="廠商已接單"
          />
          <StatCard
            label="等待廠商回覆"
            value={stats?.waiting_vendor}
            tone="pending"
            hint="已送出，等回覆"
          />
          <StatCard
            label="已完成任務"
            value={stats?.completed}
            tone="done"
            hint="服務結束"
          />
          <StatCard
            label="待補資料"
            value={stats?.needs_input}
            tone="draft"
            hint="需要你填寫"
          />
          <StatCard
            label="待媒合"
            value={stats?.ready_for_matching}
            tone="pending"
            hint="可以找廠商了"
          />
          <StatCard
            label="已婉拒"
            value={stats?.rejected}
            tone="failed"
            hint="需改選廠商"
          />
        </dl>
      </section>

      {error ? (
        <p role="alert" className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </p>
      ) : null}

      <section aria-labelledby="tasks-heading" className="flex min-h-0 flex-1 flex-col">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h2 id="tasks-heading" className="text-sm font-semibold text-slate-900">
            我的生活事項
            {data
              ? data.truncated
                ? `（顯示最新 ${data.returned} / 共 ${data.total}）`
                : `（${data.total}）`
              : ""}
          </h2>

          <div role="group" aria-label="依狀態篩選" className="flex flex-wrap gap-1">
            {FILTERS.map((f) => {
              const count =
                f.key === "all"
                  ? (data?.tasks.length ?? 0)
                  : (data?.tasks.filter((t) => t.badge_tone === f.key).length ?? 0);
              return (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => setFilter(f.key)}
                  aria-pressed={filter === f.key}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                    filter === f.key
                      ? "bg-slate-900 text-white"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {f.label}
                  {data ? ` ${count}` : ""}
                </button>
              );
            })}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {loading && !data ? (
            <SkeletonGrid />
          ) : visible.length === 0 ? (
            <EmptyState hasAny={(data?.total ?? 0) > 0} />
          ) : (
            <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((task) => (
                <li key={task.task_id}>
                  <TaskCard
                    task={task}
                    editing={editing === task.task_id}
                    onToggleEdit={() =>
                      setEditing((prev) =>
                        prev === task.task_id ? null : task.task_id,
                      )
                    }
                    onSaved={() => {
                      setEditing(null);
                      void load();
                    }}
                    busy={
                      task.latest_case != null &&
                      busyCase === task.latest_case.case_id
                    }
                    disabled={busyCase !== null}
                    onAct={act}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: number | undefined;
  tone: BadgeTone;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <dt className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
        <span aria-hidden="true">{TONES[tone].dot}</span>
        {label}
      </dt>
      <dd className="mt-1 text-2xl font-bold tabular-nums text-slate-900">
        {value ?? "–"}
      </dd>
      <p className="text-xs text-slate-400">{hint}</p>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <ul className="grid animate-pulse grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <li key={i} className="h-44 rounded-xl bg-slate-200" />
      ))}
    </ul>
  );
}

function EmptyState({ hasAny }: { hasAny: boolean }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-6 py-12 text-center">
      <p className="text-sm font-medium text-slate-700">
        {hasAny ? "這個篩選條件下沒有任務" : "還沒有任何生活事項"}
      </p>
      <p className="mt-1 text-sm text-slate-500">
        {hasAny
          ? "換一個狀態看看，或選「全部」。"
          : "到「消費者端」用一句話描述需求，智慧管家會幫你整理成任務。"}
      </p>
    </div>
  );
}

function TaskCard({
  task,
  editing,
  onToggleEdit,
  onSaved,
  busy,
  disabled,
  onAct,
}: {
  task: DashboardTaskItem;
  editing: boolean;
  onToggleEdit: () => void;
  onSaved: () => void;
  busy: boolean;
  disabled: boolean;
  onAct: (caseId: number, action: "confirm" | "complete") => void;
}) {
  const tone = TONES[task.badge_tone] ?? TONES.draft;
  const heading = task.title || task.raw_input || `任務 #${task.task_id}`;
  const location = [task.city, task.district].filter(Boolean).join(" ");
  const caseRef = task.latest_case;
  const caseStatus = caseRef?.status;
  // A request is only editable while nobody else is acting on it. The server
  // enforces this too; this just avoids offering a button that would 409.
  const canEdit =
    caseStatus === undefined ||
    caseStatus === "vendor_rejected" ||
    caseStatus === "cancelled"
      ? task.status !== "completed" && task.status !== "cancelled"
      : false;
  // Deep link back into the workspace: ?case= reopens the tracking board,
  // ?task= reopens the form / vendor list.
  const resumeHref = caseRef
    ? `/?case=${caseRef.case_id}`
    : `/?task=${task.task_id}`;

  return (
    <article className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-sky-300">
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-xs text-slate-400">#{task.task_id}</p>
          <h3 className="mt-0.5 truncate font-semibold text-slate-900" title={heading}>
            {heading}
          </h3>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${tone.chip}`}
        >
          <span aria-hidden="true">{tone.dot} </span>
          {task.display_label}
        </span>
      </header>

      {task.tags.length > 0 ? (
        <ul className="mt-2 flex flex-wrap gap-1">
          {task.tags.map((tag) => (
            <li
              key={tag}
              className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600"
            >
              {tag}
            </li>
          ))}
        </ul>
      ) : null}

      <dl className="mt-3 space-y-1 text-xs text-slate-600">
        <Row
          label="建立日期"
          value={new Date(task.created_at).toLocaleDateString("zh-TW", {
            year: "numeric",
            month: "long",
            day: "numeric",
          })}
        />
        <Row
          label="預估預算"
          value={
            task.budget_amount != null
              ? `${task.budget_amount.toLocaleString("zh-TW")} ${task.currency ?? "TWD"}`
              : "尚未確定"
          }
        />
        {location ? <Row label="服務地區" value={location} /> : null}
        {task.latest_case ? (
          <>
            <Row label="媒合廠商" value={task.latest_case.vendor_name} />
            <Row
              label="案件編號"
              value={task.latest_case.case_number}
              mono
            />
            {task.latest_case.estimated_price != null ? (
              <Row
                label="廠商報價"
                value={`${task.latest_case.estimated_price.toLocaleString("zh-TW")} 元`}
              />
            ) : null}
            {task.latest_case.proposed_time ? (
              <Row
                label="預計到場"
                value={new Date(task.latest_case.proposed_time).toLocaleString("zh-TW")}
              />
            ) : null}
          </>
        ) : null}
      </dl>

      {task.next_action ? (
        <p className="mt-3 rounded-lg bg-sky-50 px-3 py-2 text-xs leading-relaxed text-sky-900">
          <span className="font-semibold">下一步：</span>
          {task.next_action}
        </p>
      ) : task.missing_count > 0 ? (
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-900">
          <span className="font-semibold">下一步：</span>
          還缺 {task.missing_count} 項資料，可以在這裡直接補，或回到消費者端繼續。
        </p>
      ) : null}

      <div className="mt-auto" />

      {editing ? (
        <TaskConditionsForm
          taskId={task.task_id}
          onSaved={onSaved}
          onCancel={onToggleEdit}
        />
      ) : (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
          {caseRef && caseStatus === "vendor_accepted" ? (
            <button
              type="button"
              onClick={() => onAct(caseRef.case_id, "confirm")}
              disabled={disabled}
              className="flex-1 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-violet-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {busy ? "處理中…" : "確認並提供聯絡資訊"}
            </button>
          ) : null}

          {caseRef && caseStatus === "contact_shared" ? (
            <button
              type="button"
              onClick={() => onAct(caseRef.case_id, "complete")}
              disabled={disabled}
              className="flex-1 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {busy ? "處理中…" : "標記服務完成"}
            </button>
          ) : null}

          {canEdit ? (
            <button
              type="button"
              onClick={onToggleEdit}
              className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              修改需求
            </button>
          ) : null}

          <Link
            href={resumeHref}
            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            {caseRef ? "查看進度" : "繼續處理"}
          </Link>
        </div>
      )}
    </article>
  );
}

function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="shrink-0 text-slate-400">{label}</dt>
      <dd
        className={`truncate text-right font-medium text-slate-800 ${
          mono ? "font-mono" : ""
        }`}
        title={value}
      >
        {value}
      </dd>
    </div>
  );
}
