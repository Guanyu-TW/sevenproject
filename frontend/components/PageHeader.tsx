import AppNav from "@/components/AppNav";
import HealthBadge from "@/components/HealthBadge";

export const PRODUCT_NAME = "AI 智慧管家";

type Props = {
  /** What this particular page is for. */
  title: string;
  subtitle: string;
  /** Optional line under the subtitle, e.g. the sponsor strip. */
  eyebrowSlot?: React.ReactNode;
};

/**
 * Shared header for the three surfaces. Previously each page hand-rolled its
 * own, which is how they drifted into showing different product names and
 * stale "Step N" build labels.
 */
export default function PageHeader({ title, subtitle, eyebrowSlot }: Props) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-3.5">
        <BrandMark />
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-700">
            {PRODUCT_NAME}
          </p>
          <h1 className="mt-0.5 text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
            {title}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
          {eyebrowSlot ? <div className="mt-1.5">{eyebrowSlot}</div> : null}
        </div>
      </div>
      <div className="flex flex-col items-end gap-2">
        <AppNav />
        <HealthBadge />
      </div>
    </header>
  );
}

function BrandMark() {
  return (
    <span
      aria-hidden="true"
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 shadow-lg shadow-sky-500/25"
    >
      <svg viewBox="0 0 24 24" className="h-6 w-6 text-white" fill="none">
        <path
          d="M4 11.2 12 4.5l8 6.7"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M6.2 12.6V19h11.6v-6.4"
          stroke="currentColor"
          strokeWidth="1.9"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M12 13.1l.72 1.62 1.63.72-1.63.72L12 17.8l-.72-1.64-1.63-.72 1.63-.72z"
          fill="currentColor"
        />
      </svg>
    </span>
  );
}
