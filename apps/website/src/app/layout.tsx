import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ZantaraEntry } from "../components/ZantaraEntry";
import { publicOrigin } from "../lib/public-origin";
import assistantStyles from "../components/ZantaraEntry.module.css";
import "../styles/brand-fonts.css";
import "./globals.css";
const origin = publicOrigin();

export const metadata: Metadata = {
  // No origin configured = not public yet: canonicals stay relative rather than
  // claiming a host robots.ts is simultaneously telling crawlers to stay off.
  ...(origin ? { metadataBase: new URL(origin) } : {}),
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
