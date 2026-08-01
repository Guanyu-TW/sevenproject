import PageHeader from "@/components/PageHeader";
import VendorPortal from "@/components/VendorPortal";

export const metadata = {
  title: "廠商接案後台 | AI 智慧管家",
};

export default function VendorPage() {
  return (
    <main className="mx-auto flex h-screen max-w-5xl flex-col gap-5 px-6 py-6">
      <PageHeader
        title="廠商接案後台"
        subtitle="住戶送來的需求會出現在這裡，接單後住戶的追蹤看板會同步更新"
      />

      <VendorPortal />
    </main>
  );
}
