import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bali Zero Magazine",
  description: "Internal intelligence, research, and operations for Bali Zero.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
