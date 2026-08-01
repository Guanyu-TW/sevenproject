import DashboardView from "@/components/DashboardView";
import PageHeader from "@/components/PageHeader";

export const metadata = {
  title: "我的儀表板 | AI 智慧管家",
};

export default function DashboardPage() {
  return (
    <main className="mx-auto flex h-screen max-w-7xl flex-col gap-5 px-6 py-6">
      <PageHeader
        title="我的生活事項總覽"
        subtitle="你提出過的每一筆需求、目前狀態，以及下一步該做什麼"
      />

      <DashboardView />
    </main>
  );
}
