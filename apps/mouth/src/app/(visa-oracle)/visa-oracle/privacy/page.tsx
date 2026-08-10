"use client";

import { useState } from "react";
import type { Language } from "../_lib/flow";
import { LanguageToggle } from "../_components/LanguageToggle";
import { ThemeToggle, type OracleTheme } from "../_components/ThemeToggle";

const COPY = {
  en: {
    back: "Back to Visa Oracle",
    eyebrow: "Privacy Policy V1 · approved 6 August 2026",
    title: "Your Visa Oracle data",
    intro:
      "Visa Oracle is a private decision-support tool. You can obtain a result without creating an account or giving us your name, phone, email, or passport number.",
    processingTitle: "Necessary evaluation",
    processing:
      "We process the structured answers you choose to provide to return the evaluation you requested. The legal basis is taking steps at your request before a possible service contract; it is not marketing consent.",
    retentionTitle: "Retention",
    retention:
      "A durable decision is retained for 30 days from evaluation. A safe-retry/idempotency record is retained for 24 hours. PII-free operational telemetry is retained for 90 days. An active, documented legal hold may suspend deletion for the affected record only.",
    telemetryTitle: "What telemetry excludes",
    telemetry:
      "Telemetry may contain an event name, terminal state, time, and a hash of a random opaque reference. It must never contain raw answers, nationality, passport or family data, free text, or request/response payloads.",
    consentTitle: "WhatsApp and CRM are separate choices",
    consent:
      "Opening WhatsApp requires its own unticked opt-in and sends only the result state and, when available, an opaque assessment reference. It does not create a CRM record. Any future CRM creation or contact requires a separate explicit opt-in.",
    minorsTitle: "Protection for minors",
    minors:
      "A case involving a minor requires confirmed parent or guardian involvement. Without that confirmation, Visa Oracle sends the case to human review and does not automate a supported recommendation or handoff.",
    rightsTitle: "Your rights",
    rights:
      "You may request access, correction, restriction, withdrawal, or deletion. We acknowledge and action a valid request within 3 × 24 hours, subject only to a documented legal obligation or legal hold. We verify identity proportionately and do not place identity evidence in engineering logs.",
    contact: "Send a request to privacy@balizero.com",
    law: "Official UU No. 27 of 2022 source",
    enforce:
      "Visa Oracle cannot enter ENFORCE mode until its Data Protection Impact Assessment (DPIA) and independent production gates are approved.",
  },
  id: {
    back: "Kembali ke Visa Oracle",
    eyebrow: "Kebijakan Privasi V1 · disetujui 6 Agustus 2026",
    title: "Data Visa Oracle Anda",
    intro:
      "Visa Oracle adalah alat bantu keputusan privat. Anda dapat memperoleh hasil tanpa membuat akun atau memberikan nama, nomor telepon, email, maupun nomor paspor.",
    processingTitle: "Evaluasi yang diperlukan",
    processing:
      "Kami memproses jawaban terstruktur yang Anda pilih untuk memberikan evaluasi yang Anda minta. Dasar pemrosesannya adalah langkah atas permintaan Anda sebelum kemungkinan kontrak layanan; ini bukan persetujuan pemasaran.",
    retentionTitle: "Retensi",
    retention:
      "Keputusan yang tersimpan dipertahankan selama 30 hari sejak evaluasi. Catatan idempotensi untuk percobaan ulang yang aman dipertahankan selama 24 jam. Telemetri operasional tanpa PII dipertahankan selama 90 hari. Legal hold yang aktif dan terdokumentasi hanya dapat menunda penghapusan catatan terkait.",
    telemetryTitle: "Data yang dilarang dalam telemetri",
    telemetry:
      "Telemetri hanya dapat memuat nama peristiwa, status akhir, waktu, dan hash dari referensi acak yang tidak bermakna. Telemetri tidak boleh memuat jawaban mentah, kewarganegaraan, data paspor atau keluarga, teks bebas, maupun payload permintaan/hasil.",
    consentTitle: "WhatsApp dan CRM adalah pilihan terpisah",
    consent:
      "Membuka WhatsApp memerlukan pilihan persetujuan tersendiri yang tidak dicentang sebelumnya dan hanya mengirim status hasil serta, jika tersedia, referensi asesmen yang tidak bermakna. Tindakan ini tidak membuat catatan CRM. Pembuatan atau kontak CRM di masa depan memerlukan persetujuan eksplisit yang terpisah.",
    minorsTitle: "Perlindungan anak",
    minors:
      "Kasus yang melibatkan anak memerlukan keterlibatan orang tua atau wali yang terkonfirmasi. Tanpa konfirmasi tersebut, Visa Oracle mengirim kasus ke peninjauan manusia dan tidak mengotomatiskan rekomendasi yang didukung maupun handoff.",
    rightsTitle: "Hak Anda",
    rights:
      "Anda dapat meminta akses, koreksi, pembatasan, penarikan persetujuan, atau penghapusan. Permintaan yang valid ditanggapi dan ditindaklanjuti dalam 3 × 24 jam, kecuali terdapat kewajiban hukum atau legal hold yang terdokumentasi. Identitas diverifikasi secara proporsional dan buktinya tidak dimasukkan ke log teknis.",
    contact: "Kirim permintaan ke privacy@balizero.com",
    law: "Sumber resmi UU Nomor 27 Tahun 2022",
    enforce:
      "Visa Oracle tidak dapat masuk ke mode ENFORCE sebelum Data Protection Impact Assessment (DPIA) dan gate produksi independen disetujui.",
  },
} as const;

export default function VisaOraclePrivacyPage() {
  const [language, setLanguage] = useState<Language>("en");
  const [theme, setTheme] = useState<OracleTheme>("light");
  const copy = COPY[language];

  return (
    <div className="oracle-root" data-oracle-theme={theme} data-funnel="visa">
      <div className="oracle-shell">
        <header className="oracle-topbar oracle-policy__topbar">
          <a className="oracle-question__back" href="/visa-oracle">
            {copy.back}
          </a>
          <div className="oracle-topbar__actions">
            <LanguageToggle language={language} onChange={setLanguage} />
            <ThemeToggle
              language={language}
              theme={theme}
              onChange={setTheme}
            />
          </div>
        </header>

        <main className="oracle-policy">
          <p className="oracle-eyebrow">{copy.eyebrow}</p>
          <h1>{copy.title}</h1>
          <p className="oracle-policy__intro">{copy.intro}</p>

          <section>
            <h2>{copy.processingTitle}</h2>
            <p>{copy.processing}</p>
          </section>
          <section>
            <h2>{copy.retentionTitle}</h2>
            <p>{copy.retention}</p>
          </section>
          <section>
            <h2>{copy.telemetryTitle}</h2>
            <p>{copy.telemetry}</p>
          </section>
          <section>
            <h2>{copy.consentTitle}</h2>
            <p>{copy.consent}</p>
          </section>
          <section>
            <h2>{copy.minorsTitle}</h2>
            <p>{copy.minors}</p>
          </section>
          <section>
            <h2>{copy.rightsTitle}</h2>
            <p>{copy.rights}</p>
            <p className="oracle-policy__actions">
              <a href="mailto:privacy@balizero.com">{copy.contact}</a>
              <a
                href="https://www.peraturan.go.id/id/uu-no-27-tahun-2022"
                target="_blank"
                rel="noopener noreferrer"
              >
                {copy.law}
              </a>
            </p>
          </section>

          <aside className="oracle-unverified" role="note">
            {copy.enforce}
          </aside>
        </main>
      </div>
    </div>
  );
}
