import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nuzantara V6",
  description: "Indonesian business consulting AI assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
