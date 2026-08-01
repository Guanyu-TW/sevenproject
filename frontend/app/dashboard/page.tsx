import AppNav from "@/components/AppNav";
import DashboardView from "@/components/DashboardView";
import HealthBadge from "@/components/HealthBadge";

export const metadata = {
  title: "我的儀表板 | AI 生活管家",
};

export default function DashboardPage() {
  return (
    <main className="mx-auto flex h-screen max-w-7xl flex-col gap-5 px-6 py-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-widest text-sky-600">
            Step 7 · Dashboard
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            我的生活事項總覽
          </h1>
          <p className="text-sm text-slate-600">
            你提出過的每一筆需求、目前狀態，以及下一步該做什麼
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <AppNav />
          <HealthBadge />
        </div>
      </header>

      <DashboardView />
    </main>
  );
}
