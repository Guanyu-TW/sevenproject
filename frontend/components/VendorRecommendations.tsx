"use client";

import type { MatchVendorsResponse, VendorRecommendation } from "@/lib/api";

type Props = {
  result: MatchVendorsResponse;
  onBack: () => void;
  onSelect: (vendor: VendorRecommendation) => void;
  /** vendor_id currently being turned into a case, if any. */
  creatingFor: number | null;
};

export default function VendorRecommendations({
  result,
  onBack,
  onSelect,
  creatingFor,
}: Props) {
  const { recommendations, candidate_count, fallback_used, fallback_reason } = result;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-lg font-bold text-slate-900">推薦廠商</h3>
          <p className="text-xs text-slate-500">
            符合服務類型與地區的廠商共 {candidate_count} 家，
            AI 為你挑出 {recommendations.length} 家
          </p>
        </div>
        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-1"
        >
          回到任務內容
        </button>
      </div>

      {fallback_used ? (
        <p
          role="status"
          className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900"
        >
          AI 推薦沒有成功，以下改用規則式排序（依評分）。
          {fallback_reason ? ` 原因：${fallback_reason}` : null}
        </p>
      ) : null}

      {recommendations.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-6 text-center">
          <p className="text-sm font-medium text-slate-700">目前沒有符合的廠商</p>
          <p className="mt-1 text-sm text-slate-500">
            這個服務類型在該地區還沒有合作廠商，試試調整地區或服務項目。
          </p>
        </div>
      ) : (
        <ol className="space-y-3">
          {recommendations.map((vendor, index) => (
            <li key={vendor.vendor_id}>
              <VendorCard
                vendor={vendor}
                rank={index + 1}
                onSelect={onSelect}
                creating={creatingFor === vendor.vendor_id}
                disabled={creatingFor !== null}
              />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function VendorCard({
  vendor,
  rank,
  onSelect,
  creating,
  disabled,
}: {
  vendor: VendorRecommendation;
  rank: number;
  onSelect: (vendor: VendorRecommendation) => void;
  creating: boolean;
  disabled: boolean;
}) {
  const priceRange =
    vendor.price_min != null && vendor.price_max != null
      ? `${vendor.price_min.toLocaleString("zh-TW")} - ${vendor.price_max.toLocaleString("zh-TW")} 元`
      : null;

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-sky-300">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2">
          <span
            aria-hidden="true"
            className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-sky-100 text-xs font-bold text-sky-800"
          >
            {rank}
          </span>
          <div>
            <h4 className="font-semibold text-slate-900">
              <span className="sr-only">推薦順位 {rank}：</span>
              {vendor.name}
            </h4>
            <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
              <span className="font-medium text-amber-600">
                <span aria-hidden="true">★</span> {vendor.rating.toFixed(1)}
                <span className="sr-only">分，滿分 5 分</span>
              </span>
              {vendor.service_city ? (
                <span>
                  {vendor.service_city}
                  {vendor.service_districts.length > 0
                    ? ` ${vendor.service_districts.join("、")}`
                    : " 全市"}
                </span>
              ) : null}
              {vendor.categories.length > 0 ? (
                <span>{vendor.categories.join("、")}</span>
              ) : null}
            </p>
          </div>
        </div>

        <div className="shrink-0 text-right">
          {vendor.estimated_price != null ? (
            <p className="text-sm font-bold text-slate-900">
              約 {vendor.estimated_price.toLocaleString("zh-TW")} 元
            </p>
          ) : null}
          {priceRange ? (
            <p className="text-xs text-slate-400">{priceRange}</p>
          ) : null}
          <p className="mt-1 text-xs text-sky-700">
            適合度 {Math.round(vendor.match_score * 100)}%
          </p>
        </div>
      </div>

      <div className="mt-3 rounded-lg bg-sky-50 px-3 py-2">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-700">
          AI 推薦原因
        </p>
        <p className="text-sm leading-relaxed text-slate-700">
          {vendor.recommendation_reason}
        </p>
      </div>

      <button
        type="button"
        onClick={() => onSelect(vendor)}
        disabled={disabled}
        className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {creating ? (
          <>
            <span
              aria-hidden="true"
              className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
            />
            建立案件中…
          </>
        ) : (
          "選擇此廠商並建立案件"
        )}
      </button>
    </article>
  );
}
