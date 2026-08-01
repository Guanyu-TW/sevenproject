import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 生活管家 MVP",
  description: "智慧社區生活需求理解與服務媒合平台",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-Hant">
      <body>{children}</body>
    </html>
  );
}
