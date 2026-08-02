import { AlertTriangle, RefreshCw, type LucideIcon } from "lucide-react";

/**
 * Shared loading / error / empty presentation.
 *
 * These three states used to be hand-rolled in every panel, which is how some
 * ended up as a bare line of text and others had no retry at all. One place
 * now decides what each state looks like.
 */

export function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  );
}

/** Inline failure notice with a retry affordance, placed next to what broke. */
export function ErrorPanel({
  message,
  onRetry,
  retrying = false,
  className = "",
}: {
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={`animate-rise rounded-xl border border-rose-200 bg-rose-50 p-4 ${className}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle
          aria-hidden="true"
          className="mt-0.5 h-5 w-5 shrink-0 text-rose-600"
        />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-rose-900">操作沒有成功</p>
          <p className="mt-0.5 text-sm leading-relaxed text-rose-800">{message}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              disabled={retrying}
              className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {retrying ? (
                <Spinner className="h-3.5 w-3.5" />
              ) : (
                <RefreshCw aria-hidden="true" className="h-3.5 w-3.5" />
              )}
              {retrying ? "重試中…" : "重試"}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

/** Illustrated placeholder for "nothing here yet", with an optional next step. */
export function EmptyState({
  icon: Icon,
  title,
  body,
  action,
  tone = "slate",
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: React.ReactNode;
  tone?: "slate" | "sky" | "emerald";
}) {
  const ring = {
    slate: "from-slate-100 to-slate-200 text-slate-400",
    sky: "from-sky-100 to-sky-200 text-sky-500",
    emerald: "from-emerald-100 to-emerald-200 text-emerald-600",
  }[tone];

  return (
    <div className="animate-rise flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/70 px-6 py-12 text-center">
      <span
        aria-hidden="true"
        className={`mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br ${ring}`}
      >
        <Icon className="h-8 w-8" strokeWidth={1.6} />
      </span>
      <p className="text-base font-semibold text-slate-800">{title}</p>
      <p className="mt-1 max-w-sm text-sm leading-relaxed text-slate-500">{body}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/** Grey blocks that echo the shape of what is loading. */
export function SkeletonCards({
  count = 6,
  className = "h-44",
}: {
  count?: number;
  className?: string;
}) {
  return (
    <ul
      aria-hidden="true"
      className="grid animate-pulse grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
    >
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className={`rounded-xl bg-slate-200/70 ${className}`} />
      ))}
    </ul>
  );
}

export function SkeletonRows({
  count = 3,
  className = "h-28",
}: {
  count?: number;
  className?: string;
}) {
  return (
    <div aria-hidden="true" className="animate-pulse space-y-3">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={`rounded-xl bg-slate-200/70 ${className}`} />
      ))}
    </div>
  );
}
