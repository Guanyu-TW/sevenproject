"use client";

import MissingFieldsForm from "@/components/MissingFieldsForm";
import VendorRecommendations from "@/components/VendorRecommendations";
import type { LifeTask, MatchVendorsResponse } from "@/lib/api";

type Props = {
  task: LifeTask | null;
  loading: boolean;
  /** Non-null once matching has returned; switches the panel to the vendor list. */
  matchResult: MatchVendorsResponse | null;
  matching: boolean;
  onConfirm: (filled: Record<string, string>) => void;
  onBackToTask: () => void;
};

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  needs_info: "待補資料",
  ready_for_matching: "待媒合",
  matching: "媒合中",
  completed: "已完成",
  cancelled: "已取消",
};

export default function TaskResultPanel({
  task,
  loading,
  matchResult,
  matching,
  onConfirm,
  onBackToTask,
}: Props) {
  const showVendors = matchResult !== null;

  return (
    <section
      aria-labelledby="task-heading"
      aria-busy={loading || matching}
      className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <h2 id="task-heading" className="text-base font-semibold text-slate-900">
          {showVendors ? "廠商推薦清單" : "任務解析結果"}
        </h2>
        {task ? (
          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600">
            Task #{task.id}
          </span>
        ) : null}
      </header>

      <div className="flex-1 overflow-y-auto px-5 py-4">
        {loading && !task ? <SkeletonCard /> : null}
        {!loading && !task ? <Placeholder /> : null}

        {task && showVendors ? (
          <VendorRecommendations result={matchResult} onBack={onBackToTask} />
        ) : null}

        {task && !showVendors ? (
          <TaskCard
            task={task}
            dimmed={loading}
            matching={matching}
            onConfirm={onConfirm}
          />
        ) : null}
      </div>
    </section>
  );
}

function Placeholder() {
  return (
    <div className="flex h-full min-h-48 flex-col items-center justify-center gap-2 text-center">
      <p className="text-sm font-medium text-slate-700">還沒有解析結果</p>
      <p className="max-w-xs text-sm text-slate-500">
        在左邊送出一句需求，AI 擷取到的服務類型、預算與缺少的資料會顯示在這裡。
      </p>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="h-6 w-2/3 rounded bg-slate-200" />
      <div className="h-4 w-full rounded bg-slate-100" />
      <div className="h-4 w-5/6 rounded bg-slate-100" />
      <div className="h-24 w-full rounded-xl bg-slate-100" />
    </div>
  );
}

function TaskCard({
  task,
  dimmed,
  matching,
  onConfirm,
}: {
  task: LifeTask;
  dimmed: boolean;
  matching: boolean;
  onConfirm: (filled: Record<string, string>) => void;
}) {
  const p = task.parsed_data;
  const budget = p.budget;
  const location = p.location;
  const confidence = p._meta?.confidence;

  const locationText =
    [location?.city, location?.district, location?.address]
      .filter(Boolean)
      .join(" ") || null;

  return (
    <div className={`space-y-5 transition-opacity ${dimmed ? "opacity-50" : ""}`}>
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone="sky">{task.category?.name ?? "未分類"}</Pill>
          <Pill tone="slate">
            {STATUS_LABELS[task.status] ?? task.status}
          </Pill>
          {p._meta?.provider ? (
            <Pill tone={p._meta.provider === "mock" ? "amber" : "emerald"}>
              {p._meta.provider === "mock" ? "mock 假資料" : p._meta.provider}
            </Pill>
          ) : null}
          {typeof confidence === "number" ? (
            <Pill tone="slate">信心 {Math.round(confidence * 100)}%</Pill>
          ) : null}
        </div>
        {p._meta?.model ? (
          <p className="text-xs text-slate-400">模型：{p._meta.model}</p>
        ) : null}
        <h3 className="text-xl font-bold text-slate-900">
          {p.title ?? "（無標題）"}
        </h3>
        {p.summary ? (
          <p className="text-sm leading-relaxed text-slate-600">{p.summary}</p>
        ) : null}
      </div>

      <dl className="grid grid-cols-1 gap-px overflow-hidden rounded-xl border border-slate-200 bg-slate-200 sm:grid-cols-2">
        <Field label="服務類型" value={task.category?.name ?? null} hint={task.category?.code} />
        <Field label="細項" value={p.service_type ?? null} />
        <Field
          label="預算"
          value={
            typeof budget?.amount === "number"
              ? `${budget.amount.toLocaleString("zh-TW")} ${budget.currency ?? ""}`.trim()
              : null
          }
          hint={budget?.note ?? undefined}
        />
        <Field label="地點" value={locationText} />
        <Field label="急迫程度" value={p.urgency ?? null} />
        <Field label="希望時間" value={p.preferred_time ?? null} />
      </dl>

      <MissingFieldsForm
        task={task}
        submitting={matching}
        onConfirm={onConfirm}
      />

      {task.raw_input ? (
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
            原始輸入
          </p>
          <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {task.raw_input}
          </p>
        </div>
      ) : null}

      <details className="rounded-lg border border-slate-200">
        <summary className="cursor-pointer px-3 py-2 text-xs font-medium text-slate-600">
          原始 JSON
        </summary>
        <pre className="overflow-x-auto rounded-b-lg bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
          {JSON.stringify(task, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function Field({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | null;
  hint?: string;
}) {
  return (
    <div className="bg-white px-4 py-3">
      <dt className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </dt>
      <dd
        className={`mt-1 text-sm ${
          value ? "font-medium text-slate-900" : "text-slate-400"
        }`}
      >
        {value ?? "—"}
      </dd>
      {hint ? <p className="mt-0.5 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}

function Pill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone: "sky" | "slate" | "amber" | "emerald";
}) {
  const tones = {
    sky: "bg-sky-100 text-sky-800",
    slate: "bg-slate-100 text-slate-700",
    amber: "bg-amber-100 text-amber-800",
    emerald: "bg-emerald-100 text-emerald-800",
  } as const;

  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
