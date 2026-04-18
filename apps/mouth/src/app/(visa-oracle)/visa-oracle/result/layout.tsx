import type { Metadata } from "next";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Your visa recommendations — Visa Oracle",
  description:
    "Personalized Indonesian visa recommendations ranked by fit, cost, and complexity.",
  alternates: {
    canonical: `${baseUrl}/visa-oracle/result`,
  },
  robots: { index: false, follow: true },
};

export default function ResultLayout({ children }: { children: React.ReactNode }) {
  return children;
}
