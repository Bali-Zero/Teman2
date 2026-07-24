"use client";

import { type ReactElement } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";

const WA_CONTEXT: { label: string; value: string }[] = [
  { label: "Layanan", value: "Tax Gap Analysis" },
  { label: "Halaman", value: "/tax/gap" },
];

const PAIN_POINTS: string[] = [
  "PT PMA sering salah klasifikasi penghasilan — menyebabkan kelebihan bayar PPh yang tidak perlu",
  "Celah kepatuhan PPN dan withholding tax dapat memicu pemeriksaan DJP",
  "Perubahan tarif PPh dan PPN 2024–2025 membuat banyak bisnis out-of-compliance tanpa sadar",
  "Transfer pricing antar entitas perlu dokumentasi khusus — tanpa ini, risikonya signifikan",
];

const STEPS: { step: string; text: string }[] = [
  {
    step: "1",
    text: "Kami audit laporan pajak, SPT tahunan, dan data keuangan bisnis Anda",
  },
  {
    step: "2",
    text: "Identifikasi celah antara kewajiban pajak aktual vs yang telah dibayarkan",
  },
  {
    step: "3",
    text: "Rekomendasi konkret: potensi penghematan legal dan langkah perbaikan kepatuhan",
  },
  {
    step: "4",
    text: "Implementasi bersama konsultan pajak bersertifikat — terdaftar di DJP",
  },
];

export function TaxGapCTA(): ReactElement {
  return (
    <section className="max-w-2xl mx-auto px-4 py-12 md:py-20">
      <span
        className="inline-block text-xs font-semibold uppercase tracking-widest px-3 py-1 rounded-full mb-6"
        style={{
          background: "var(--accent-funnel)",
          color: "var(--text-on-accent)",
        }}
      >
        Perpajakan 2025
      </span>

      <h1
        className="text-3xl md:text-4xl font-bold mb-4 leading-tight"
        style={{ color: "var(--text-primary)" }}
      >
        Tax Gap Analysis
      </h1>

      <p
        className="text-base md:text-lg mb-8"
        style={{ color: "var(--text-secondary)" }}
      >
        Banyak bisnis di Indonesia membayar pajak lebih dari yang seharusnya —
        atau justru terekspos risiko pemeriksaan karena celah kepatuhan yang
        tidak disadari. Tim konsultan pajak bersertifikat Bali Zero menganalisis
        SPT, PPh, PPN, dan withholding tax bisnis Anda untuk menemukan celah dan
        peluang optimasi yang legal.
      </p>

      <div className="mb-12">
        <WhatsAppLeadButton
          source="tax_gap"
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
          Mengapa analisis tax gap penting
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
        Perlu bantuan klasifikasi KBLI untuk bisnis Anda?{" "}
        <Link
          href="/kbli/decoder"
          className="underline underline-offset-2"
          style={{ color: "var(--text-primary)" }}
        >
          Buka KBLI Decoder →
        </Link>
      </p>
    </section>
  );
}
