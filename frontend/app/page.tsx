import BrandBackdrop, { BrandStrip } from "@/components/BrandBackdrop";
import DemandWorkspace from "@/components/DemandWorkspace";
import PageHeader from "@/components/PageHeader";

export default function Home() {
  return (
    <>
      <BrandBackdrop />
      <main className="mx-auto flex h-screen max-w-7xl flex-col gap-5 px-6 py-6">
        <PageHeader
          title="說一句話，其他交給管家"
          subtitle="描述你的生活需求，管家會整理成任務、找到合適的廠商並全程追蹤"
          eyebrowSlot={<BrandStrip />}
        />

        <DemandWorkspace />
      </main>
    </>
  );
}
