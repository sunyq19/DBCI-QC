import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "模块协作",
  description: "质控模块、启用条件与评分方案。共同维护，固定版本。",
  icons: {
    icon: { url: "/linjian-mark.png", type: "image/png" },
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
