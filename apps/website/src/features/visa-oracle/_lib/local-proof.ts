import type { Language } from "./flow";

export type LocalProof = boolean | "unsigned-proposal";

export function localProofNotice(language: Language, proof: LocalProof): string {
  if (!proof) return "";
  if (proof === "unsigned-proposal") return language === "en"
    ? "Local unsigned proposal · synthetic answers only. Proposed rules, not signed or activated. Offline assessment; no production verification, live pricing or submission."
    : "Usulan lokal belum ditandatangani · hanya jawaban sintetis. Aturan usulan belum ditandatangani atau diaktifkan. Penilaian luring; produksi, harga terkini, dan pengajuan belum diverifikasi.";
  return language === "en"
    ? "Local engine check · synthetic answers only. Offline signed reference; no live pricing or production verification."
    : "Pengujian mesin lokal · hanya jawaban sintetis. Referensi bertanda tangan secara luring; harga terkini dan produksi belum diverifikasi.";
}
