"use client";

import type { LifeTask, MissingField } from "@/lib/api";

type Props = {
  task: LifeTask | null;
  loading: boolean;
};

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  needs_info: "待補資料",
  ready: "可派工",
  matching: "媒合中",
  completed: "已完成",
  cancelled: "已取消",
};

export default function TaskResultPanel({ task, loading }: Props) {
  return (
    <section
      aria-labelledby="task-heading"
      aria-busy={loading}
      className="flex min-h-0 flex-col rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <h2 id="task-heading" className="text-base font-semibold text-slate-900">
          任務解析結果
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
        {task ? <TaskCard task={task} dimmed={loading} /> : null}
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

function TaskCard({ task, dimmed }: { task: LifeTask; dimmed: boolean }) {
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
            <Pill tone="amber">{p._meta.provider} provider</Pill>
          ) : null}
          {typeof confidence === "number" ? (
            <Pill tone="slate">信心 {Math.round(confidence * 100)}%</Pill>
          ) : null}
        </div>
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

      <MissingFields fields={task.missing_fields} />

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

function MissingFields({ fields }: { fields: MissingField[] }) {
  if (fields.length === 0) {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
        <p className="text-sm font-semibold text-emerald-900">資料已完整</p>
        <p className="text-sm text-emerald-800">沒有缺少的欄位，可以進入媒合。</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3">
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className="text-amber-600">
          ⚠
        </span>
        <p className="text-sm font-semibold text-amber-900">
          缺少 {fields.length} 項資料
        </p>
      </div>
      <ul className="mt-2 space-y-2">
        {fields.map((f) => (
          <li key={f.field} className="flex gap-2 text-sm">
            <span className="mt-0.5 shrink-0 rounded bg-amber-200 px-1.5 py-0.5 text-xs font-semibold text-amber-900">
              {f.label}
            </span>
            <span className="text-amber-900">
              {f.reason ?? "尚未提供"}
              {f.required ? (
                <span className="ml-1 text-xs text-amber-700">（必填）</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
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
  tone: "sky" | "slate" | "amber";
}) {
  const tones = {
    sky: "bg-sky-100 text-sky-800",
    slate: "bg-slate-100 text-slate-700",
    amber: "bg-amber-100 text-amber-800",
  } as const;

  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
