import { type ReactElement } from "react";
import type { Metadata } from "next";
import { ZoningCheckCTA } from "./_components/ZoningCheckCTA";

export const metadata: Metadata = {
  title: "Zoning Check — Verifikasi Zonasi Properti Bali Anda | Bali Zero",
  description:
    "Pastikan properti atau lahan Anda di Bali sesuai zonasi yang berlaku sebelum membeli atau membangun. Tim Bali Zero memverifikasi status zonasi dan risiko regulasi untuk PT PMA dan investor asing.",
  alternates: {
    canonical: "https://kita.balizero.com/zoning",
  },
  openGraph: {
    title: "Zoning Check — Verifikasi Zonasi Properti Bali Anda | Bali Zero",
    description:
      "Pastikan properti atau lahan Anda di Bali sesuai zonasi yang berlaku sebelum membeli atau membangun. Tim Bali Zero memverifikasi status zonasi dan risiko regulasi untuk PT PMA dan investor asing.",
    url: "https://kita.balizero.com/zoning",
    siteName: "Bali Zero",
    type: "website",
  },
};

export default function ZoningCheckPage(): ReactElement {
  return (
    <main
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <ZoningCheckCTA />
    </main>
  );
}
