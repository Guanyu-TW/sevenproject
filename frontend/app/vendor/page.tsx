import AppNav from "@/components/AppNav";
import HealthBadge from "@/components/HealthBadge";
import VendorPortal from "@/components/VendorPortal";

export const metadata = {
  title: "廠商接案後台 | AI 生活管家",
};

export default function VendorPage() {
  return (
    <main className="mx-auto flex h-screen max-w-5xl flex-col gap-5 px-6 py-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-widest text-emerald-600">
            Step 6 · Vendor Portal
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            廠商接案後台
          </h1>
          <p className="text-sm text-slate-600">
            住戶送來的需求會出現在這裡，接單後消費者端的追蹤看板會同步更新
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <AppNav />
          <HealthBadge />
        </div>
      </header>

      <VendorPortal />
    </main>
  );
}
