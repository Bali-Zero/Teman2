import type { Metadata } from "next";
import { KBLIDecoderCTA } from "./_components/KBLIDecoderCTA";
import { KBLIBreadcrumbJsonLd } from "@/components/kbli/KBLIStructuredData";

export const metadata: Metadata = {
  title: "KBLI Decoder — Temukan Kode Klasifikasi Bisnis Anda",
  description:
    "Tidak yakin kode KBLI mana yang sesuai untuk bisnis Anda? Tim Bali Zero menganalisis aktivitas usaha Anda dan menemukan klasifikasi KBLI 2025 yang tepat untuk pendaftaran PT PMA.",
  alternates: {
    canonical: "https://balizero.com/kbli/decoder",
  },
  openGraph: {
    title: "KBLI Decoder — Temukan Kode Klasifikasi Bisnis Anda",
    description:
      "Tidak yakin kode KBLI mana yang sesuai untuk bisnis Anda? Tim Bali Zero menganalisis aktivitas usaha Anda dan menemukan klasifikasi KBLI 2025 yang tepat untuk pendaftaran PT PMA.",
    url: "https://balizero.com/kbli/decoder",
    siteName: "Bali Zero",
    type: "website",
  },
};

export default function KBLIDecoderPage() {
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
          { name: "KBLI Decoder", url: "https://balizero.com/kbli/decoder" },
        ]}
      />
      <KBLIDecoderCTA />
    </main>
  );
}
