import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DBCI-QC · 流程协作",
  description: "质控模块、启用条件与评分方案。共同维护，固定版本。",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">{children}</body>
    </html>
  );
}
