"use client";

import type { CaseTimelineStep, ConsultationCase } from "@/lib/api";

type Props = {
  caseDetail: ConsultationCase;
  onBackToVendors: () => void;
  onRefresh: () => void;
  /** Resident confirms the quote, unlocking their contact details. */
  onConfirm: () => void;
  /** Resident marks the service as delivered. */
  onComplete: () => void;
  /** Which action is in flight, if any. */
  busyAction: "confirm" | "complete" | null;
};

const STATUS_TONES: Record<string, string> = {
  waiting_vendor_response: "bg-amber-100 text-amber-900 ring-amber-300",
  vendor_accepted: "bg-violet-100 text-violet-900 ring-violet-300",
  contact_shared: "bg-sky-100 text-sky-900 ring-sky-300",
  completed: "bg-emerald-100 text-emerald-900 ring-emerald-300",
  vendor_rejected: "bg-rose-100 text-rose-900 ring-rose-300",
  cancelled: "bg-slate-200 text-slate-700 ring-slate-300",
};

export default function CaseTrackingBoard({
  caseDetail,
  onBackToVendors,
  onRefresh,
  onConfirm,
  onComplete,
  busyAction,
}: Props) {
  const tone =
    STATUS_TONES[caseDetail.status] ?? "bg-slate-100 text-slate-800 ring-slate-300";
  const shared = caseDetail.shared_with_vendor;
  const waiting = caseDetail.status === "waiting_vendor_response";
  const needsConfirm = caseDetail.status === "vendor_accepted";
  const inService = caseDetail.status === "contact_shared";
  const finished = caseDetail.status === "completed";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-slate-400">
            案件編號
          </p>
          <p className="font-mono text-lg font-bold text-slate-900">
            {caseDetail.case_number}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span
            aria-live="polite"
            className={`rounded-full px-3 py-1.5 text-sm font-semibold ring-1 ${tone}`}
          >
            {caseDetail.status_label}
          </span>
          <button
            type="button"
            onClick={onRefresh}
            className="text-xs text-slate-500 underline-offset-2 transition hover:text-slate-800 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            手動更新
          </button>
          {waiting ? (
            <p className="text-xs text-slate-400">每 4 秒自動檢查廠商回覆</p>
          ) : null}
        </div>
      </div>

      {caseDetail.vendor_note || caseDetail.proposed_time ? (
        <section className="rounded-xl border border-emerald-300 bg-emerald-50 p-4">
          <h3 className="text-sm font-semibold text-emerald-900">廠商回覆</h3>
          {caseDetail.proposed_time ? (
            <p className="mt-1 text-sm text-slate-800">
              預計到場：
              <span className="font-bold">
                {new Date(caseDetail.proposed_time).toLocaleString("zh-TW")}
              </span>
            </p>
          ) : null}
          {caseDetail.vendor_note ? (
            <p className="mt-1 text-sm leading-relaxed text-slate-700">
              備註：{caseDetail.vendor_note}
            </p>
          ) : null}
        </section>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
        <h3 className="text-sm font-semibold text-slate-900">選定廠商</h3>
        <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2">
          <p className="font-medium text-slate-900">
            {caseDetail.vendor.name}
            <span className="ml-2 text-sm font-normal text-amber-600">
              <span aria-hidden="true">★</span> {caseDetail.vendor.rating.toFixed(1)}
              <span className="sr-only">分，滿分 5 分</span>
            </span>
          </p>
          {caseDetail.estimated_price != null ? (
            <p className="text-sm text-slate-700">
              預估價格{" "}
              <span className="font-bold text-slate-900">
                {caseDetail.estimated_price.toLocaleString("zh-TW")} 元
              </span>
            </p>
          ) : null}
        </div>
        {caseDetail.vendor.service_city ? (
          <p className="mt-1 text-xs text-slate-500">
            服務範圍：{caseDetail.vendor.service_city}
            {caseDetail.vendor.service_districts.length > 0
              ? ` ${caseDetail.vendor.service_districts.join("、")}`
              : " 全市"}
          </p>
        ) : null}
        {caseDetail.recommendation_reason ? (
          <p className="mt-2 border-t border-slate-200 pt-2 text-xs leading-relaxed text-slate-600">
            {caseDetail.recommendation_reason}
          </p>
        ) : null}
      </section>

      {needsConfirm ? (
        <section className="rounded-xl border-2 border-violet-400 bg-violet-50 p-4">
          <h3 className="text-sm font-semibold text-violet-900">需要你確認</h3>
          <p className="mt-1 text-sm leading-relaxed text-slate-700">
            確認後，系統會把你的<strong>完整門牌地址與聯絡電話</strong>提供給
            {caseDetail.vendor.name}，方便師傅到場前聯繫。在你確認之前，廠商只看得到
            {shared.area ?? "你的地區"}。
          </p>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busyAction !== null}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-violet-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-violet-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {busyAction === "confirm" ? (
              <>
                <Spinner />
                處理中…
              </>
            ) : (
              "確認並提供聯絡資訊"
            )}
          </button>
        </section>
      ) : null}

      {inService ? (
        <section className="rounded-xl border border-sky-300 bg-sky-50 p-4">
          <h3 className="text-sm font-semibold text-sky-900">服務進行中</h3>
          <p className="mt-1 text-sm leading-relaxed text-slate-700">
            廠商已取得你的聯絡資訊。師傅到場並完成服務後，你或廠商任一方都可以標記完成。
          </p>
          <button
            type="button"
            onClick={onComplete}
            disabled={busyAction !== null}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {busyAction === "complete" ? (
              <>
                <Spinner />
                處理中…
              </>
            ) : (
              "服務已完成"
            )}
          </button>
        </section>
      ) : null}

      {finished ? (
        <section className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-center">
          <p className="text-2xl" aria-hidden="true">
            ✓
          </p>
          <h3 className="text-sm font-semibold text-emerald-900">服務已完成</h3>
          <p className="mt-1 text-sm text-emerald-800">感謝您的使用！</p>
        </section>
      ) : null}

      <section className="rounded-xl border border-sky-200 bg-sky-50 p-4">
        <h3 className="text-sm font-semibold text-sky-900">下一步</h3>
        <p className="mt-1 text-sm leading-relaxed text-slate-700">
          {caseDetail.next_action ?? "等待更新。"}
        </p>
        {caseDetail.blocked_reason ? (
          <p className="mt-2 rounded-lg bg-rose-100 px-3 py-2 text-sm text-rose-900">
            <span className="font-semibold">目前狀況：</span>
            {caseDetail.blocked_reason}
          </p>
        ) : (
          <p className="mt-2 text-xs text-sky-800">
            目前狀況：一切正常，沒有需要你處理的事項。
          </p>
        )}
      </section>

      <section className="rounded-xl border border-slate-300 bg-white p-4">
        <div className="flex items-start gap-2">
          <span aria-hidden="true" className="mt-0.5 text-slate-400">
            🔒
          </span>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">隱私保護</h3>
            <p className="mt-1 text-sm leading-relaxed text-slate-600">
              {caseDetail.privacy_notice}
            </p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-lg bg-emerald-50 px-3 py-2">
            <p className="text-xs font-semibold text-emerald-900">
              廠商目前看得到
            </p>
            <ul className="mt-1 space-y-0.5 text-xs text-emerald-800">
              {shared.category_name ? <li>服務類型：{shared.category_name}</li> : null}
              {shared.city ? (
                <li>
                  地區：{shared.city}
                  {shared.district ?? ""}
                </li>
              ) : null}
              {shared.budget_amount != null ? (
                <li>預算：{shared.budget_amount.toLocaleString("zh-TW")} 元</li>
              ) : null}
              {shared.preferred_time ? <li>希望時間：{shared.preferred_time}</li> : null}
              <li>需求摘要</li>
            </ul>
          </div>

          <div
            className={`rounded-lg px-3 py-2 ${
              shared.contact_unlocked ? "bg-sky-100" : "bg-slate-100"
            }`}
          >
            <p
              className={`text-xs font-semibold ${
                shared.contact_unlocked ? "text-sky-900" : "text-slate-700"
              }`}
            >
              {shared.contact_unlocked ? "已提供給廠商" : "尚未提供給廠商"}
            </p>
            {shared.contact_unlocked ? (
              <ul className="mt-1 space-y-0.5 text-xs text-sky-900">
                {shared.address ? <li>{shared.address}</li> : null}
                {shared.contact_name ? <li>{shared.contact_name}</li> : null}
                {shared.contact_phone ? <li>{shared.contact_phone}</li> : null}
              </ul>
            ) : (
              <ul className="mt-1 space-y-0.5 text-xs text-slate-600">
                {shared.withheld.map((item) => (
                  <li key={item}>· {item}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-semibold text-slate-900">案件進度</h3>
        <Timeline steps={caseDetail.timeline} />
      </section>

      <button
        type="button"
        onClick={onBackToVendors}
        className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
      >
        回到廠商清單
      </button>
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

function Timeline({ steps }: { steps: CaseTimelineStep[] }) {
  return (
    <ol className="relative space-y-0">
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1;
        const done = step.state === "done";
        const current = step.state === "current";

        const dot = done
          ? "bg-emerald-500 text-white"
          : current
            ? "bg-amber-500 text-white ring-4 ring-amber-100"
            : "bg-slate-200 text-slate-500";

        return (
          <li key={step.key} className="flex gap-3 pb-5 last:pb-0">
            <div className="flex flex-col items-center">
              <span
                aria-hidden="true"
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${dot}`}
              >
                {done ? "✓" : index + 1}
              </span>
              {!isLast ? (
                <span
                  aria-hidden="true"
                  className={`mt-1 w-0.5 flex-1 ${
                    done ? "bg-emerald-300" : "bg-slate-200"
                  }`}
                />
              ) : null}
            </div>

            <div className="min-w-0 flex-1 pt-0.5">
              <p
                className={`text-sm ${
                  done || current
                    ? "font-semibold text-slate-900"
                    : "text-slate-400"
                }`}
              >
                {index + 1}. {step.label}
                {current ? (
                  <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-900">
                    進行中
                  </span>
                ) : null}
                <span className="sr-only">
                  {done ? "（已完成）" : current ? "（進行中）" : "（尚未開始）"}
                </span>
              </p>
              {step.note ? (
                <p className="mt-0.5 text-xs text-slate-500">{step.note}</p>
              ) : null}
              {step.at ? (
                <time
                  dateTime={step.at}
                  className="mt-0.5 block text-xs text-slate-400"
                >
                  {new Date(step.at).toLocaleString("zh-TW")}
                </time>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
