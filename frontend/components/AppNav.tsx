"use client";

import { ArrowLeftRight, LayoutDashboard, MessageSquarePlus, Store } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { LucideIcon } from "lucide-react";

export type Audience = "consumer" | "vendor";

type Tab = { href: string; label: string; icon: LucideIcon };

/**
 * Navigation is scoped to one audience at a time.
 *
 * The three surfaces used to share a single switcher, so a resident saw a
 * 廠商端 tab and a vendor saw the resident's dashboard. Role switching now
 * happens deliberately, through the landing page.
 */
const TABS: Record<Audience, Tab[]> = {
  consumer: [
    { href: "/user", label: "提出需求", icon: MessageSquarePlus },
    { href: "/dashboard", label: "我的儀表板", icon: LayoutDashboard },
  ],
  vendor: [{ href: "/vendor", label: "接單總覽", icon: Store }],
};

export default function AppNav({ audience }: { audience: Audience }) {
  const pathname = usePathname();
  const tabs = TABS[audience];

  return (
    <div className="flex items-center gap-2">
      <nav
        aria-label={audience === "consumer" ? "住戶功能" : "廠商功能"}
        className="flex gap-1 rounded-xl bg-slate-200/80 p-1 backdrop-blur"
      >
        {tabs.map((tab) => {
          const active = pathname.startsWith(tab.href);
          const Icon = tab.icon;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                active
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:bg-white/60 hover:text-slate-900"
              }`}
            >
              <Icon aria-hidden="true" className="h-3.5 w-3.5" />
              {tab.label}
            </Link>
          );
        })}
      </nav>

      <Link
        href="/"
        className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white/70 px-3 py-2 text-xs font-medium text-slate-600 transition hover:bg-white hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        <ArrowLeftRight aria-hidden="true" className="h-3.5 w-3.5" />
        切換身分
      </Link>
    </div>
  );
}
