import React from "react";
import type { Metadata } from "next";
import { TaxGapCTA } from "./_components/TaxGapCTA";

export const metadata: Metadata = {
  title:
    "Tax Gap Analysis — Periksa & Optimalkan Pajak Bisnis Anda | Bali Zero",
  description:
    "Evaluasi kepatuhan pajak dan temukan potensi penghematan serta risiko pajak PT PMA Anda di Indonesia dengan analisis Tax Gap dari Bali Zero.",
  alternates: {
    canonical: "https://kita.balizero.com/tax/gap",
  },
  openGraph: {
    title:
      "Tax Gap Analysis — Periksa & Optimalkan Pajak Bisnis Anda | Bali Zero",
    description:
      "Evaluasi kepatuhan pajak dan temukan potensi penghematan serta risiko pajak PT PMA Anda di Indonesia dengan analisis Tax Gap dari Bali Zero.",
    url: "https://kita.balizero.com/tax/gap",
    siteName: "Bali Zero",
    type: "website",
  },
};

export default function TaxGapPage(): React.ReactElement {
  return (
    <main
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <TaxGapCTA />
    </main>
  );
}
