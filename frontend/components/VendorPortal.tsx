"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  completeCase,
  listVendorCases,
  listVendors,
  respondToCase,
  type VendorCaseListItem,
  type VendorCaseListResponse,
  type VendorSummary,
} from "@/lib/api";

const ALL = "all";

/**
 * Vendor-side inbox. There is no vendor login yet, so the identity is picked
 * from a dropdown; every request carries that vendor_id so the API can still
 * verify the case really belongs to them.
 */
export default function VendorPortal() {
  const [vendors, setVendors] = useState<VendorSummary[]>([]);
  const [selected, setSelected] = useState<string>(ALL);
  const [data, setData] = useState<VendorCaseListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCase, setActiveCase] = useState<number | null>(null);

  const vendorId = selected === ALL ? null : Number(selected);

  useEffect(() => {
    const controller = new AbortController();
    listVendors(controller.signal)
      .then(setVendors)
      .catch(() => {
        /* the case list below surfaces connectivity problems already */
      });
    return () => controller.abort();
  }, []);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        setData(await listVendorCases(vendorId, signal));
      } catch (err) {
        if (signal?.aborted) return;
        setError(
          err instanceof ApiError
            ? `讀取案件失敗（${err.status}）：${err.message}`
            : "無法連線至後端 API",
        );
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [vendorId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  const pendingCases = useMemo(
    () => (data?.cases ?? []).filter((c) => c.status === "waiting_vendor_response"),
    [data],
  );
  const respondedCases = useMemo(
    () =>
      (data?.cases ?? []).filter(
        (c) => c.status === "vendor_accepted" || c.status === "contact_shared",
      ),
    [data],
  );
  const completedCases = useMemo(
    () => (data?.cases ?? []).filter((c) => c.status === "completed"),
    [data],
  );

  async function handleComplete(caseItem: VendorCaseListItem) {
    setActiveCase(caseItem.case_id);
    setError(null);
    try {
      await completeCase(caseItem.case_id, "vendor");
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `標記完成失敗（${err.status}）：${err.message}`
          : "無法連線至後端 API",
      );
    } finally {
      setActiveCase(null);
    }
  }

  async function handleRespond(
    caseItem: VendorCaseListItem,
    action: "accept" | "reject",
    note: string,
    proposedTime: string,
  ) {
    setActiveCase(caseItem.case_id);
    setError(null);
    try {
      await respondToCase(
        caseItem.case_id,
        {
          action,
          vendorNote: note.trim() || null,
          proposedTime: action === "accept" ? proposedTime : null,
        },
        caseItem.vendor_id,
      );
      await refresh();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `${action === "accept" ? "接單" : "婉拒"}失敗（${err.status}）：${err.message}`
          : "無法連線至後端 API",
      );
    } finally {
      setActiveCase(null);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <section className="flex flex-wrap items-end justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <div>
          <label
            htmlFor="vendor-picker"
            className="mb-1 block text-xs font-medium text-slate-500"
          >
            目前身分（尚未實作廠商登入）
          </label>
          <select
            id="vendor-picker"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-900 focus:border-sky-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            <option value={ALL}>全平台（所有廠商）</option>
            {vendors.map((v) => (
              <option key={v.id} value={String(v.id)}>
                {v.name}（★{v.rating.toFixed(1)}
                {v.open_case_count > 0 ? ` · 待處理 ${v.open_case_count}` : ""}）
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-3">
          <p aria-live="polite" className="text-right text-sm text-slate-600">
            待接單{" "}
            <span className="font-bold text-amber-700">{data?.pending ?? "…"}</span> 件
            {data && data.pending > data.pending_shown ? (
              <span className="mt-0.5 block text-xs text-slate-400">
                下方顯示最新 {data.pending_shown} 筆
              </span>
            ) : null}
          </p>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-50"
          >
            {loading ? "更新中…" : "重新整理"}
          </button>
        </div>
      </section>

      {error ? (
        <p
          role="alert"
          className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-800"
        >
          {error}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto">
        <section aria-labelledby="pending-heading">
          <h2
            id="pending-heading"
            className="mb-3 text-sm font-semibold text-slate-900"
          >
            待接單案件
            {data
              ? data.pending > pendingCases.length
                ? `（顯示 ${pendingCases.length} / 共 ${data.pending}）`
                : pendingCases.length > 0
                  ? `（${pendingCases.length}）`
                  : ""
              : ""}
          </h2>

          {loading && !data ? (
            <SkeletonRows />
          ) : pendingCases.length === 0 ? (
            <p className="rounded-xl border border-slate-200 bg-white px-4 py-6 text-center text-sm text-slate-500">
              目前沒有待接單的案件。到消費者端送出一筆需求並選擇廠商，就會出現在這裡。
            </p>
          ) : (
            <ul className="space-y-3">
              {pendingCases.map((c) => (
                <li key={c.case_id}>
                  <PendingCaseCard
                    caseItem={c}
                    busy={activeCase === c.case_id}
                    disabled={activeCase !== null}
                    onRespond={handleRespond}
                    showVendorName={vendorId === null}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        {respondedCases.length > 0 ? (
          <section aria-labelledby="responded-heading">
            <h2
              id="responded-heading"
              className="mb-3 text-sm font-semibold text-slate-900"
            >
              進行中案件
              {data && data.responded_total > respondedCases.length
                ? `（顯示 ${respondedCases.length} / 共 ${data.responded_total}）`
                : `（${respondedCases.length}）`}
            </h2>
            <ul className="space-y-3">
              {respondedCases.map((c) => (
                <li key={c.case_id}>
                  <ActiveCaseCard
                    caseItem={c}
                    showVendorName={vendorId === null}
                    busy={activeCase === c.case_id}
                    disabled={activeCase !== null}
                    onComplete={handleComplete}
                  />
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {completedCases.length > 0 ? (
          <section aria-labelledby="completed-heading">
            <h2
              id="completed-heading"
              className="mb-3 text-sm font-semibold text-slate-900"
            >
              已完成案件
              {data && data.completed_total > completedCases.length
                ? `（顯示 ${completedCases.length} / 共 ${data.completed_total}）`
                : `（${completedCases.length}）`}
            </h2>
            <ul className="space-y-2">
              {completedCases.map((c) => (
                <li key={c.case_id}>
                  <ActiveCaseCard
                    caseItem={c}
                    showVendorName={vendorId === null}
                    busy={false}
                    disabled
                    onComplete={handleComplete}
                  />
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function SkeletonRows() {
  return (
    <div className="animate-pulse space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-28 rounded-xl bg-slate-200" />
      ))}
    </div>
  );
}

function PendingCaseCard({
  caseItem,
  busy,
  disabled,
  onRespond,
  showVendorName,
}: {
  caseItem: VendorCaseListItem;
  busy: boolean;
  disabled: boolean;
  onRespond: (
    caseItem: VendorCaseListItem,
    action: "accept" | "reject",
    note: string,
    proposedTime: string,
  ) => void;
  showVendorName: boolean;
}) {
  const [note, setNote] = useState("");
  const [proposedTime, setProposedTime] = useState(defaultProposedTime());
  const timeId = `time-${caseItem.case_id}`;
  const noteId = `note-${caseItem.case_id}`;
  const d = caseItem.demand;

  return (
    <article className="rounded-xl border border-amber-300 bg-white p-4 shadow-sm">
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-xs text-slate-500">{caseItem.case_number}</p>
          <h3 className="mt-0.5 font-semibold text-slate-900">
            {d.title ?? "（無標題）"}
          </h3>
          <ServiceTags demand={d} />
        </div>
        <div className="text-right">
          <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900">
            {caseItem.status_label}
          </span>
          {showVendorName ? (
            <p className="mt-1 text-xs text-slate-500">{caseItem.vendor_name}</p>
          ) : null}
        </div>
      </header>

      {d.summary ? (
        <p className="mt-2 text-sm leading-relaxed text-slate-600">{d.summary}</p>
      ) : null}

      <dl className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
        <Fact
          label="地區"
          value={[d.city, d.district].filter(Boolean).join(" ") || null}
        />
        <Fact
          label="住戶預算"
          value={
            d.budget_amount != null
              ? `${d.budget_amount.toLocaleString("zh-TW")} 元`
              : null
          }
        />
        <Fact label="急迫程度" value={d.urgency} />
        <Fact label="希望時間" value={d.preferred_time} />
        <Fact
          label="平台預估"
          value={
            caseItem.estimated_price != null
              ? `${caseItem.estimated_price.toLocaleString("zh-TW")} 元`
              : null
          }
        />
      </dl>

      {d.withheld.length > 0 ? (
        <p className="mt-3 rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-600">
          <span aria-hidden="true">🔒 </span>
          接單後才會提供：{d.withheld.join("、")}
        </p>
      ) : null}

      <div className="mt-4 grid grid-cols-1 gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor={timeId}
            className="mb-1 block text-xs font-medium text-slate-700"
          >
            擬定到場時間
            <span aria-hidden="true" className="ml-1 text-rose-600">
              *
            </span>
          </label>
          <input
            id={timeId}
            type="datetime-local"
            required
            value={proposedTime}
            onChange={(e) => setProposedTime(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-sky-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          />
        </div>
        <div>
          <label
            htmlFor={noteId}
            className="mb-1 block text-xs font-medium text-slate-700"
          >
            廠商備註／報價說明
          </label>
          <textarea
            id={noteId}
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="例如：現場確認後報價，若需更換零件會先告知。"
            className="w-full resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onRespond(caseItem, "accept", note, proposedTime)}
          disabled={disabled || !proposedTime}
          className="flex flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {busy ? (
            <>
              <span
                aria-hidden="true"
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
              />
              處理中…
            </>
          ) : (
            "確認接單"
          )}
        </button>
        <button
          type="button"
          onClick={() => onRespond(caseItem, "reject", note, "")}
          disabled={disabled}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 disabled:opacity-50"
        >
          婉拒
        </button>
      </div>
      {!proposedTime ? (
        <p className="mt-1 text-xs text-amber-700">接單前請先填擬定到場時間。</p>
      ) : null}
    </article>
  );
}

function ActiveCaseCard({
  caseItem,
  showVendorName,
  busy,
  disabled,
  onComplete,
}: {
  caseItem: VendorCaseListItem;
  showVendorName: boolean;
  busy: boolean;
  disabled: boolean;
  onComplete: (caseItem: VendorCaseListItem) => void;
}) {
  const d = caseItem.demand;
  const unlocked = d.contact_unlocked;
  const done = caseItem.status === "completed";
  const canComplete = caseItem.status === "contact_shared";

  return (
    <article
      className={`rounded-xl border p-4 ${
        done
          ? "border-slate-200 bg-slate-50"
          : unlocked
            ? "border-sky-300 bg-sky-50"
            : "border-violet-300 bg-violet-50"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="font-mono text-xs text-slate-500">{caseItem.case_number}</p>
          <h3 className="mt-0.5 text-sm font-semibold text-slate-900">
            {d.title ?? "（無標題）"}
          </h3>
          <ServiceTags demand={d} />
        </div>
        <div className="text-right">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
              done
                ? "bg-slate-200 text-slate-700"
                : unlocked
                  ? "bg-sky-200 text-sky-900"
                  : "bg-violet-200 text-violet-900"
            }`}
          >
            {caseItem.status_label}
          </span>
          {showVendorName ? (
            <p className="mt-1 text-xs text-slate-500">{caseItem.vendor_name}</p>
          ) : null}
        </div>
      </div>

      <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-700">
        <Fact
          label="約定到場"
          value={
            caseItem.proposed_time
              ? new Date(caseItem.proposed_time).toLocaleString("zh-TW")
              : null
          }
        />
        <Fact label="備註" value={caseItem.vendor_note} />
      </dl>

      {unlocked ? (
        <div className="mt-3 rounded-lg border border-sky-400 bg-white px-3 py-2">
          <p className="text-xs font-semibold text-sky-900">
            <span aria-hidden="true">🔓 </span>
            住戶已確認，聯絡資訊已解鎖
          </p>
          <dl className="mt-1.5 space-y-1 text-sm">
            <UnlockedRow label="地址" value={d.address} />
            <UnlockedRow label="聯絡人" value={d.contact_name} />
            <UnlockedRow label="電話" value={d.contact_phone} />
          </dl>
        </div>
      ) : (
        <p className="mt-3 rounded-lg bg-white/70 px-3 py-2 text-xs text-violet-900">
          <span aria-hidden="true">🔒 </span>
          等待住戶確認報價，確認後才會提供完整地址與電話。目前只知道
          {d.area ?? "服務地區"}。
        </p>
      )}

      {canComplete ? (
        <button
          type="button"
          onClick={() => onComplete(caseItem)}
          disabled={disabled}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {busy ? (
            <>
              <span
                aria-hidden="true"
                className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
              />
              處理中…
            </>
          ) : (
            "標記為已完成"
          )}
        </button>
      ) : null}
    </article>
  );
}

/**
 * Category plus the finer service item. The category alone made every plumbing
 * job read as 水電維修, so a vendor could not tell a blocked toilet from a dead
 * socket without opening the summary.
 */
function ServiceTags({ demand }: { demand: VendorCaseListItem["demand"] }) {
  // When the request is narrow enough the model's title and label converge
  // ("水龍頭漏水維修" twice). Showing it once reads better.
  const label =
    demand.service_label && demand.service_label !== demand.title
      ? demand.service_label
      : null;
  if (!demand.category_name && !label) return null;
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
      {demand.category_name ? (
        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
          {demand.category_name}
        </span>
      ) : null}
      {label ? (
        <span className="rounded-md bg-sky-100 px-2 py-0.5 text-[11px] font-semibold text-sky-900">
          {label}
        </span>
      ) : null}
    </div>
  );
}

function UnlockedRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex gap-2">
      <dt className="w-12 shrink-0 text-xs text-slate-400">{label}</dt>
      <dd className="font-medium text-slate-900">{value ?? "—"}</dd>
    </div>
  );
}

function Fact({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div className="flex gap-1">
      <dt className="text-slate-400">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

/** Tomorrow 19:00 local, formatted for <input type="datetime-local">. */
function defaultProposedTime(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(19, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}
