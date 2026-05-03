/**
 * KBLI 2025 Type Definitions
 * Matches the structure of KBLI_2025_FINAL_CLEAN.json
 */

export interface KBLIRawCode {
  kode_kbli_2025: string;
  judul: string;
  uraian: string;
  per_skala: KBLIScaleEntry[];
  sektor_id: string | null;
  status_mapping: string;
  pp28_sources: string[];
  pma_status: "TERBUKA" | "TERTUTUP" | "TERBATAS" | string;
  pma_max_asing: number;
  pma_kondisi: string | null;
  pma_prioritas: boolean;
  pma_nota: string | null;
  pma_source: string | null;
  _source: string;
}

export interface KBLIScaleEntry {
  skala_usaha: string[];
  kategori_risiko: string;
  perizinan: string;
  persyaratan: string[];
  jangka_waktu: string;
  kewajiban: string[];
  pb_umku: string[];
  parameter: string;
  kewenangan: string;
  sanksi_peringatan: string;
  sanksi_denda: string;
  sanksi_penghentian: string;
  sanksi_pencabutan: string;
  fiktif_positif: boolean;
}

/** Processed code for frontend consumption */
export interface KBLICode {
  code: string;
  titleId: string;
  titleEn: string;
  description: string;
  section: string;
  sectionName: string;
  pma: {
    status: "open" | "restricted" | "closed" | "unknown";
    maxForeign: number;
    conditions: string | null;
    isPriority: boolean;
    note: string | null;
  };
  licensing: KBLILicenseByScale[];
  tier: "gold" | "silver" | "bronze";
}

export interface KBLILicenseByScale {
  scales: string[];
  riskCategory: string;
  licenseType: string;
  requirements: string[];
  timeline: string;
  obligations: string[];
  authority: string;
}

export interface KBLISection {
  id: string;
  nameEn: string;
  nameId: string;
  icon: string;
  codeCount: number;
}
