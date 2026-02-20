/** Matches KBLI_2025_FINAL_CLEAN.json exactly */
export interface KBLIRawCode {
  kode_kbli_2025: string;
  judul: string;
  uraian: string;
  per_skala: KBLIScaleEntry[];
  sektor_id: string | null;
  status_mapping: KBLIMappingStatus;
  pp28_sources: string[];
  pma_status: "TERBUKA" | "TERTUTUP" | "TERBATAS";
  pma_max_asing: number;
  pma_kondisi: string | null;
  pma_prioritas: boolean;
  pma_nota: string | null;
  pma_source: string | null;
  _source: string;
  aggregation_note?: string;
  mapping_note?: string;
  kbli_2020_source?: string;
  intel_2026?: {
    market_sentiment?: string;
    bali_nuance?: string;
    operational_risks?: string;
    investment_outlook?: string;
    legacy_bridge?: string;
  };
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
}

export type KBLIMappingStatus =
  | "MATCH_LANGSUNG"
  | "CODICE_RINUMERATO"
  | "MATCH_CON_AGGREGAZIONE"
  | "BPS_ONLY"
  | "";

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
    source: string | null;
  };
  licensing: KBLILicenseByScale[];
  transition: {
    status: KBLIMappingStatus;
    fromCodes: string[];
    note: string | null;
  };
  intel?: {
    market_sentiment: string;
    bali_nuance: string;
    operational_risks: string;
    investment_outlook: string;
    legacy_bridge: string;
  };
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

/** Section metadata */
export interface KBLISection {
  id: string;
  nameEn: string;
  nameId: string;
  icon: string;
  codeCount: number;
  description: string;
}
