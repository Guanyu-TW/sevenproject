import DemandWorkspace from "@/components/DemandWorkspace";
import HealthBadge from "@/components/HealthBadge";

export default function Home() {
  return (
    <main className="mx-auto flex h-screen max-w-7xl flex-col gap-5 px-6 py-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-widest text-sky-600">
            Step 5 · 案件建立 + 進度追蹤
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            AI 生活管家 MVP
          </h1>
          <p className="text-sm text-slate-600">
            智慧社區生活需求理解與服務媒合平台
          </p>
        </div>
        <HealthBadge />
      </header>

      <DemandWorkspace />
    </main>
  );
}
