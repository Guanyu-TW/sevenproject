"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "消費者端" },
  { href: "/vendor", label: "廠商端" },
] as const;

/** Switches between the resident workspace and the vendor portal. */
export default function AppNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="切換使用者角色" className="flex gap-1 rounded-lg bg-slate-200 p-1">
      {TABS.map((tab) => {
        const active =
          tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
              active
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
