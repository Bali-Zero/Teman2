import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LLM Cost Dashboard (Pro local)",
  description: "Not deployed anywhere. localhost:3100 only.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased">{children}</body>
    </html>
  );
}
