import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ZantaraEntry } from "../components/ZantaraEntry";
import assistantStyles from "../components/ZantaraEntry.module.css";
import "../styles/brand-fonts.css";
import "./globals.css";
export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.WEBSITE_PUBLIC_ORIGIN || "https://balizero.com",
  ),
  title: "Bali Zero | Immigration, Company Setup, Tax & Property in Indonesia",
  description:
    "Immigration, company setup, tax and property guidance in Indonesia.",
  icons: { icon: "/assets/logo.png" },
};
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={assistantStyles.shell}>
        {children}
        <ZantaraEntry />
      </body>
    </html>
  );
}
