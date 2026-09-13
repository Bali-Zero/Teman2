import type { Metadata } from "next";
import { KBLIBuilderCTA } from "./_components/KBLIBuilderCTA";
import { KBLIBreadcrumbJsonLd } from "@/components/kbli/KBLIStructuredData";

export const metadata: Metadata = {
  title: "KBLI Builder — Susun Struktur Kode KBLI untuk PT PMA Anda",
  description:
    "Mau mendirikan PT PMA di Bali? Tim Bali Zero menyusun struktur kode KBLI 2025 yang tepat untuk proses inkorporasi dan kepatuhan investasi asing Anda.",
  alternates: {
    canonical: "https://balizero.com/kbli/builder",
  },
  openGraph: {
    title: "KBLI Builder — Susun Struktur Kode KBLI untuk PT PMA Anda",
    description:
      "Mau mendirikan PT PMA di Bali? Tim Bali Zero menyusun struktur kode KBLI 2025 yang tepat untuk proses inkorporasi dan kepatuhan investasi asing Anda.",
    url: "https://balizero.com/kbli/builder",
    siteName: "Bali Zero",
    type: "website",
  },
};

export default function KBLIBuilderPage() {
  return (
    <main
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <KBLIBreadcrumbJsonLd
        items={[
          { name: "KBLI Navigator", url: "https://balizero.com/kbli" },
          { name: "KBLI Builder", url: "https://balizero.com/kbli/builder" },
        ]}
      />
      <KBLIBuilderCTA />
    </main>
  );
}
