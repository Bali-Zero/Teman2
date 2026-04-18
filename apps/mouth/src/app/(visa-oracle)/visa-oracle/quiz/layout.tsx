import type { Metadata } from "next";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Visa Quiz — Visa Oracle",
  description:
    "Answer a few questions about your trip to Indonesia and get instant visa recommendations from Visa Oracle.",
  alternates: {
    canonical: `${baseUrl}/visa-oracle/quiz`,
  },
  robots: { index: false, follow: true },
};

export default function QuizLayout({ children }: { children: React.ReactNode }) {
  return children;
}
