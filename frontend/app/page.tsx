import {
  ArrowRight,
  Bug,
  ClipboardCheck,
  Hammer,
  Home,
  LayoutDashboard,
  Mic,
  Package,
  ShieldCheck,
  ShoppingBasket,
  Snowflake,
  Sparkles,
  Store,
  UserRound,
  UtensilsCrossed,
  Wrench,
  Zap,
} from "lucide-react";
import Link from "next/link";
import BrandBackdrop, { BrandStrip } from "@/components/BrandBackdrop";
import HealthBadge from "@/components/HealthBadge";
import { PRODUCT_NAME } from "@/components/PageHeader";

export const metadata = {
  title: "AI 智慧管家｜智慧社區生活服務平台",
};

const CATEGORIES = [
  { icon: Wrench, label: "水電維修" },
  { icon: Zap, label: "電力跳電" },
  { icon: Snowflake, label: "冷氣空調" },
  { icon: Sparkles, label: "居家清潔" },
  { icon: Hammer, label: "居家修繕" },
  { icon: Package, label: "家電維修" },
  { icon: Bug, label: "除蟲消毒" },
  { icon: UtensilsCrossed, label: "餐飲訂購" },
  { icon: ShoppingBasket, label: "代購採買" },
  { icon: Home, label: "搬家搬運" },
  { icon: UserRound, label: "長者照護" },
];

const HIGHLIGHTS = [
  {
    icon: Mic,
    title: "動口不動手",
    body: "說一句話就能報修，長輩不必打字，也不用看懂表單。",
  },
  {
    icon: ClipboardCheck,
    title: "只問缺的那幾項",
    body: "AI 先讀懂需求，再針對這次派工真正缺的資料提問。",
  },
  {
    icon: ShieldCheck,
    title: "確認後才給個資",
    body: "廠商接單前只看得到行政區，你確認報價才交換地址與電話。",
  },
];

export default function LandingPage() {
  return (
    <>
      <BrandBackdrop />
      <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-10 px-6 py-10">
        <header className="animate-fade-in flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <span
              aria-hidden="true"
              className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 shadow-lg shadow-sky-500/25"
            >
              <svg viewBox="0 0 24 24" className="h-7 w-7 text-white" fill="none">
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
            <div>
              <p className="text-xl font-bold tracking-tight text-slate-900">
                {PRODUCT_NAME}
              </p>
              <BrandStrip />
            </div>
          </div>
          <HealthBadge />
        </header>

        <section className="animate-rise max-w-2xl">
          <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-900 sm:text-4xl">
            社區的生活雜事，
            <br className="hidden sm:block" />
            交給一位聽得懂人話的管家
          </h1>
          <p className="mt-4 text-base leading-relaxed text-slate-600">
            住戶用一句話說出需求，管家整理成可派工的任務、媒合在地廠商，並在雙方確認後才交換聯絡資訊。
          </p>
        </section>

        {/* The two doors. Deliberately the largest thing on the page: picking a
            side is the only decision a first-time visitor has to make. */}
        <section aria-labelledby="portals-heading">
          <h2 id="portals-heading" className="sr-only">
            選擇入口
          </h2>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <PortalCard
              href="/user"
              icon={UserRound}
              eyebrow="User Portal"
              title="我是住戶"
              body="提出生活需求、追蹤案件進度、確認報價並交換聯絡資訊。"
              bullets={[
                { icon: Mic, text: "語音或文字都能報修" },
                { icon: LayoutDashboard, text: "儀表板一次看完所有事項" },
              ]}
              cta="開始提出需求"
              secondary={{ href: "/dashboard", label: "直接前往我的儀表板" }}
              accent="consumer"
              delay="0ms"
            />
            <PortalCard
              href="/vendor"
              icon={Store}
              eyebrow="Vendor Portal"
              title="我是合作廠商"
              body="查看派來的案件、回覆報價與到場時間，完成後標記結案。"
              bullets={[
                { icon: ClipboardCheck, text: "待接單、進行中、已完成分區管理" },
                { icon: ShieldCheck, text: "住戶確認後才解鎖完整地址" },
              ]}
              cta="進入接單後台"
              accent="vendor"
              delay="80ms"
            />
          </div>
        </section>

        <section aria-labelledby="highlights-heading">
          <h2
            id="highlights-heading"
            className="mb-3 text-sm font-semibold text-slate-900"
          >
            平台特色
          </h2>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {HIGHLIGHTS.map((h, i) => (
              <li
                key={h.title}
                className="animate-rise rounded-2xl border border-slate-200 bg-white/80 p-4 shadow-sm"
                style={{ animationDelay: `${120 + i * 70}ms` }}
              >
                <h.icon
                  aria-hidden="true"
                  className="h-5 w-5 text-sky-600"
                  strokeWidth={1.8}
                />
                <p className="mt-2 text-sm font-semibold text-slate-900">{h.title}</p>
                <p className="mt-1 text-xs leading-relaxed text-slate-500">{h.body}</p>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="categories-heading" className="pb-4">
          <h2
            id="categories-heading"
            className="mb-3 text-sm font-semibold text-slate-900"
          >
            目前支援的服務領域
            <span className="ml-2 font-normal text-slate-400">
              共 {CATEGORIES.length} 類
            </span>
          </h2>
          <ul className="flex flex-wrap gap-2">
            {CATEGORIES.map((c, i) => (
              <li
                key={c.label}
                className="animate-pop flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white/80 px-3 py-2 text-xs font-medium text-slate-700 shadow-sm"
                style={{ animationDelay: `${i * 35}ms` }}
              >
                <c.icon
                  aria-hidden="true"
                  className="h-3.5 w-3.5 text-slate-400"
                  strokeWidth={1.8}
                />
                {c.label}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}

function PortalCard({
  href,
  icon: Icon,
  eyebrow,
  title,
  body,
  bullets,
  cta,
  secondary,
  accent,
  delay,
}: {
  href: string;
  icon: typeof UserRound;
  eyebrow: string;
  title: string;
  body: string;
  bullets: { icon: typeof Mic; text: string }[];
  cta: string;
  secondary?: { href: string; label: string };
  accent: "consumer" | "vendor";
  delay: string;
}) {
  const theme =
    accent === "vendor"
      ? {
          ring: "hover:border-emerald-400 hover:shadow-emerald-500/10",
          badge: "from-emerald-500 to-teal-600 shadow-emerald-500/25",
          eyebrow: "text-emerald-700",
          cta: "bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-500",
          glow: "from-emerald-50",
        }
      : {
          ring: "hover:border-sky-400 hover:shadow-sky-500/10",
          badge: "from-sky-500 to-violet-600 shadow-sky-500/25",
          eyebrow: "text-sky-700",
          cta: "bg-sky-600 hover:bg-sky-700 focus-visible:ring-sky-500",
          glow: "from-sky-50",
        };

  return (
    <article
      className={`animate-rise group relative flex h-full flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition duration-300 hover:-translate-y-0.5 hover:shadow-xl ${theme.ring}`}
      style={{ animationDelay: delay }}
    >
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-gradient-to-br ${theme.glow} to-transparent opacity-80`}
      />

      <span
        aria-hidden="true"
        className={`relative flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br shadow-lg ${theme.badge}`}
      >
        <Icon className="h-7 w-7 text-white" strokeWidth={1.7} />
      </span>

      <p
        className={`relative mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] ${theme.eyebrow}`}
      >
        {eyebrow}
      </p>
      <h3 className="relative mt-1 text-2xl font-bold tracking-tight text-slate-900">
        {title}
      </h3>
      <p className="relative mt-2 text-sm leading-relaxed text-slate-600">{body}</p>

      <ul className="relative mt-4 space-y-2">
        {bullets.map((b) => (
          <li key={b.text} className="flex items-start gap-2 text-xs text-slate-600">
            <b.icon
              aria-hidden="true"
              className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400"
              strokeWidth={1.9}
            />
            {b.text}
          </li>
        ))}
      </ul>

      <div className="relative mt-6 space-y-2 pt-1">
        <Link
          href={href}
          className={`flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${theme.cta}`}
        >
          {cta}
          <ArrowRight
            aria-hidden="true"
            className="h-4 w-4 transition group-hover:translate-x-0.5"
          />
        </Link>
        {secondary ? (
          <Link
            href={secondary.href}
            className="flex w-full items-center justify-center rounded-xl border border-slate-300 px-4 py-2 text-xs font-medium text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            {secondary.label}
          </Link>
        ) : null}
      </div>
    </article>
  );
}
