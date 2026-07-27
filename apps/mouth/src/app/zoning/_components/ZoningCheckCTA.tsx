"use client";

import { type ReactElement } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";

const WA_CONTEXT: { label: string; value: string }[] = [
  { label: "Layanan", value: "Zoning Check" },
  { label: "Halaman", value: "/zoning" },
];

const PAIN_POINTS: string[] = [
  "Banyak properti di Bali dijual dengan status zonasi yang tidak sesuai peruntukan — investor baru tahu setelah tanda tangan",
  "Perubahan RTRW Bali 2023 mengubah status zonasi ratusan area — due diligence lama bisa sudah tidak valid",
  "Zona hijau, zona pariwisata, dan zona permukiman punya aturan pembangunan yang berbeda — salah zona = IMB ditolak",
  "PT PMA asing hanya bisa beroperasi di zona tertentu — verifikasi zonasi adalah prasyarat sebelum akuisisi",
];

const STEPS: { step: string; text: string }[] = [
  {
    step: "1",
    text: "Kami terima koordinat GPS atau alamat lengkap properti yang ingin diverifikasi",
  },
  {
    step: "2",
    text: "Cek status zonasi berdasarkan RTRW Bali terbaru + peraturan daerah yang berlaku",
  },
  {
    step: "3",
    text: "Laporan zonasi lengkap: peruntukan, batasan pembangunan, dan risiko regulasi",
  },
  {
    step: "4",
    text: "Rekomendasi konkret: lanjut akuisisi, negosiasi ulang, atau hindari — dengan alasan hukum yang jelas",
  },
];

export function ZoningCheckCTA(): ReactElement {
  return (
    <section className="max-w-2xl mx-auto px-4 py-12 md:py-20">
      <span
        className="inline-block text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full mb-6"
        style={{
          background: "var(--accent-funnel)",
          color: "var(--text-on-accent)",
        }}
      >
        Properti 2025
      </span>

      <h1
        className="text-3xl md:text-4xl font-bold mb-4 leading-tight"
        style={{ color: "var(--text-primary)" }}
      >
        Zoning Check
      </h1>

      <p
        className="text-base md:text-lg mb-8"
        style={{ color: "var(--text-secondary)" }}
      >
        Membeli properti di Bali tanpa verifikasi zonasi adalah risiko besar —
        status zonasi menentukan apa yang boleh dibangun, bagaimana properti
        bisa digunakan, dan apakah PT PMA asing bisa beroperasi di lokasi
        tersebut. Tim Bali Zero memverifikasi status zonasi berdasarkan RTRW
        Bali terbaru sebelum Anda tanda tangan.
      </p>

      <div className="mb-12">
        <WhatsAppLeadButton
          source="zoning_check"
          whatsappContext={WA_CONTEXT}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold"
          style={{
            background: "var(--cta-primary-bg, var(--accent-funnel))",
            color: "var(--cta-primary-fg, var(--text-on-accent))",
          }}
        >
          Mulai Konsultasi via WhatsApp →
        </WhatsAppLeadButton>
      </div>

      <div className="mb-10">
        <h2
          className="text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--text-secondary)" }}
        >
          Mengapa verifikasi zonasi penting
        </h2>
        <ul className="space-y-3" role="list">
          {PAIN_POINTS.map((point) => (
            <li key={point} className="flex items-start gap-3">
              <AlertTriangle
                size={15}
                className="shrink-0 mt-0.5"
                style={{ color: "var(--accent-funnel)" }}
                aria-hidden="true"
              />
              <span
                className="text-sm leading-relaxed"
                style={{ color: "var(--text-secondary)" }}
              >
                {point}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mb-12">
        <h2
          className="text-xs font-semibold uppercase tracking-widest mb-4"
          style={{ color: "var(--text-secondary)" }}
        >
          Cara kerja
        </h2>
        <ol className="space-y-5" role="list">
          {STEPS.map(({ step, text }) => (
            <li key={step} className="flex items-start gap-4">
              <span
                className="shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                style={{
                  background: "var(--accent-funnel)",
                  color: "var(--text-on-accent)",
                }}
                aria-hidden="true"
              >
                {step}
              </span>
              <span
                className="text-sm leading-relaxed pt-0.5"
                style={{ color: "var(--text-secondary)" }}
              >
                {text}
              </span>
            </li>
          ))}
        </ol>
      </div>

      <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
        Butuh bantuan struktur kepemilikan properti asing?{" "}
        <Link
          href="/kbli/decoder"
          className="underline underline-offset-2"
          style={{ color: "var(--text-primary)" }}
        >
          Cek KBLI Decoder →
        </Link>
      </p>
    </section>
  );
}
