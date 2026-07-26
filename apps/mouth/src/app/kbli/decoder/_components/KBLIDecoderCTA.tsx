"use client";

import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";

const DECODER_WA_CONTEXT: { label: string; value: string }[] = [
  { label: "Layanan", value: "KBLI Decoder" },
  { label: "Halaman", value: "/kbli/decoder" },
];

const PAIN_POINTS: string[] = [
  "Kode KBLI salah = permohonan PT PMA ditolak atau harus diulang",
  "1.563 kode KBLI 2025 — satu aktivitas bisnis bisa masuk beberapa klasifikasi",
  "Daftar Negatif Investasi berubah setiap tahun — kode lama bisa tidak berlaku",
];

const STEPS: { step: string; text: string }[] = [
  {
    step: "1",
    text: "Deskripsikan aktivitas bisnis Anda via WhatsApp — dalam bahasa apa pun",
  },
  {
    step: "2",
    text: "Tim kami menganalisis dan memetakan ke kode KBLI 2025 yang tepat",
  },
  {
    step: "3",
    text: "Anda menerima rekomendasi kode beserta catatan eligibilitas PMA-nya",
  },
];

export function KBLIDecoderCTA() {
  return (
    <section className="max-w-2xl mx-auto px-4 py-12 md:py-20">
      <span
        className="inline-block text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full mb-6"
        style={{
          background: "var(--accent-funnel)",
          color: "var(--text-on-accent)",
        }}
      >
        KBLI 2025
      </span>

      <h1
        className="text-3xl md:text-4xl font-bold mb-4 leading-tight"
        style={{ color: "var(--text-primary)" }}
      >
        KBLI Decoder
      </h1>

      <p
        className="text-base md:text-lg mb-8"
        style={{ color: "var(--text-secondary)" }}
      >
        Tidak yakin kode KBLI mana yang sesuai? Ceritakan aktivitas bisnis Anda
        — tim kami menemukan kode yang tepat dari 1.563 klasifikasi KBLI 2025
        dan memverifikasi eligibilitas PMA-nya.
      </p>

      <div className="mb-12">
        <WhatsAppLeadButton
          source="kbli_decoder"
          whatsappContext={DECODER_WA_CONTEXT}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold"
          style={{
            background: "var(--accent-funnel)",
            color: "var(--text-on-accent)",
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
          Mengapa kode yang tepat penting
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
        Ingin cari kode sendiri?{" "}
        <Link
          href="/kbli"
          className="underline underline-offset-2"
          style={{ color: "var(--text-primary)" }}
        >
          Buka KBLI Navigator →
        </Link>
      </p>
    </section>
  );
}
