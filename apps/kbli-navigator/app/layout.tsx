import type { Metadata } from "next";
import {
  Inter,
  DM_Sans,
  Instrument_Serif,
  League_Spartan,
  Montserrat,
} from "next/font/google";
import "./globals.css";
import { WebVitals } from "@/components/WebVitals";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  weight: "400",
  style: ["normal", "italic"],
  variable: "--font-instrument",
  display: "swap",
});
const leagueSpartan = League_Spartan({
  subsets: ["latin"],
  variable: "--font-league-spartan",
  display: "swap",
});
const montserrat = Montserrat({
  subsets: ["latin"],
  variable: "--font-montserrat",
  display: "swap",
});

export const metadata: Metadata = {
  title: "KBLI 2025 Navigator Pro — Bali Zero",
  description:
    "Navigate Indonesia's 1,563 KBLI 2025 business codes. PMA rules, licensing, and 2020-2025 transition. Powered by Zantara AI.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${dmSans.variable} ${instrumentSerif.variable} ${leagueSpartan.variable} ${montserrat.variable} min-h-screen antialiased`}
      >
        {children}
        <WebVitals />
      </body>
    </html>
  );
}
