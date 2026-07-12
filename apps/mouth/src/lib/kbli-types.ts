// =============================================================================
// KBLI 2025 TypeScript Types
// Source: KBLI_2025_FINAL_CLEAN.json (1,563 codes, BPS 7/2025 + PP28/2025)
// =============================================================================

// -----------------------------------------------------------------------------
// Raw JSON types (exact match to source data structure)
// -----------------------------------------------------------------------------

/** Business scale categories in Indonesian licensing system */
export type KBLIBusinessScale = "Mikro" | "Kecil" | "Menengah" | "Besar";

/** Risk category levels from PP28/2025 */
export type KBLIRiskCategory =
  | "Rendah"
  | "Menengah Rendah"
  | "Menengah Tinggi"
  | "Tinggi";

/** Mapping status indicating how a 2025 code relates to 2020 codes */
export type KBLIMappingStatus =
  | "MATCH_LANGSUNG"
  | "CODICE_RINUMERATO"
  | "MATCH_CON_AGGREGAZIONE"
  | "BPS_ONLY"
  | "";

/** PMA (foreign investment) access status */
export type KBLIPmaRawStatus = "TERBUKA" | "TERTUTUP" | "TERBATAS";

/** Per-scale licensing entry from PP28/2025 data */
export interface KBLIScaleEntry {
  skala_usaha: KBLIBusinessScale[];
  kategori_risiko: KBLIRiskCategory;
  // Real data: an array on ~99.5% of scales (often empty []), a bare string on ~20 legacy
  // records. resolveLicenseType() in kbli-derive.ts handles both forms.
  perizinan: string | string[];
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

/** Raw KBLI code record — exact match to JSON structure */
export interface KBLIRawCode {
  kode_kbli_2025: string;
  judul: string;
  uraian: string;
  per_skala: KBLIScaleEntry[];
  sektor_id: string | null;
  status_mapping: KBLIMappingStatus;
  pp28_sources: string[];
  pma_status: KBLIPmaRawStatus;
  pma_max_asing: number | "special"; // "special" = open-with-special-conditions (47221-class), no clean %
  pma_kondisi: string | null;
  pma_prioritas: boolean;
  pma_nota: string | null;
  pma_source: string | null;
  // PMA cap provenance (synced from the native app dataset, 2026-06-27)
  pma_cap_special?: boolean; // true => special-distribution condition, render "special conditions" not "Closed 0%"
  pma_cap_verified?: boolean; // false => TERBATAS cap % not source-backed, render "≈N% unverified"
  pma_route_to?: string; // sibling private code when a govt code is closed to PMA
  _source: string;
  // Optional fields (present on some records)
  aggregation_note?: string;
  mapping_note?: string;
  kbli_2020_source?: string;
  sektors?: string[];
  // Base enrichment (populated by enrichment pipeline)
  intel_2026?: {
    whatItMeans?: string;
    whatYouNeed?: string;
    whatChanged?: string;
    zantaraOpener?: string;
    baliContext?: string;
    youllAlsoNeed?: string;
    whoThisIsFor?: string;
    coverImage?: string | null;
    // Legacy field names (older enrichment batches)
    legacy_bridge?: string;
    bali_nuance?: string;
  };
  // L4 Bali sovereign-local layer (injected from schema-v2: OSS L0 + Perpres L2 + Bali moratorium)
  l4_bali?: {
    status: string;
    reason?: string;
    confidence?: "HIGH" | "MEDIUM" | "LOW";
    needs_review?: boolean;
    blocked?: boolean;
    from_2020?: string | null;
    moratorium?: {
      rule?: string;
      effective?: string;
      source?: string;
      virtual_office?: string;
    };
  };
}

/** Top-level structure of KBLI_2025_FINAL_CLEAN.json */
export interface KBLIRawDataFile {
  metadata: {
    version: string;
    source: string;
    description: string;
    total_codes: number;
    from_both: number;
    from_bps_only: number;
    from_kbli_only: number;
    avg_uraian_length: number;
  };
  data: KBLIRawCode[];
}

// -----------------------------------------------------------------------------
// Processed / frontend-friendly types
// -----------------------------------------------------------------------------

/** Normalized PMA status for frontend display */
export type KBLIPmaStatus = "open" | "restricted" | "closed";

/** Content tier for progressive enhancement */
export type KBLITier = "gold" | "silver" | "bronze";

/** Match type for search results */
export type KBLIMatchType =
  | "exact_code"
  | "keyword"
  | "semantic"
  | "section_browse";

/** PMA (foreign investment) details — processed */
export interface KBLIPmaInfo {
  status: KBLIPmaStatus;
  maxForeign: number | "special";
  condition: string | null;
  isPriority: boolean;
  note: string | null;
  source: string | null;
  // Synced from native app (2026-06-27): provenance flags that change the label.
  capSpecial: boolean; // special-distribution (47221) → "special conditions", not "Closed 0%"
  capVerified: boolean; // false → TERBATAS % not source-backed → "≈N% unverified"
  routeTo: string | null; // sibling private code when a govt code is closed to PMA (86101→86103)
}

/** Processed licensing entry for a specific business scale */
export interface KBLILicenseByScale {
  scales: KBLIBusinessScale[];
  riskCategory: KBLIRiskCategory;
  licenseType: string;
  requirements: string[];
  timeframe: string;
  obligations: string[];
  authority: string;
  fictivePositive: boolean;
}

/** Transition information from KBLI 2020 to 2025 */
export interface KBLITransition {
  mappingStatus: KBLIMappingStatus;
  previousCodes: string[];
  kbli2020Source?: string;
  mappingNote?: string;
  aggregationNote?: string;
}

/** Processed KBLI code — frontend-friendly version */
export interface KBLICode {
  code: string;
  titleId: string;
  titleEn: string;
  /** true when titleEn is a real English title (curated or generated), not the Indonesian fallback */
  titleEnIsReal?: boolean;
  /** English title for <title>/meta — frozen to the curated-legacy map (SEO firebreak PR #1967) */
  titleEnMeta?: string;
  description: string;
  section: string | null;
  sectionName: string | null;
  pma: KBLIPmaInfo;
  licensing: KBLILicenseByScale[];
  transition: KBLITransition;
  tier: KBLITier;
  keywords: string[];
  intel?: {
    whatItMeans?: string;
    whatYouNeed?: string;
    whatChanged?: string;
    zantaraOpener?: string;
    baliContext?: string;
    youllAlsoNeed?: string;
    coverImage?: string | null;
  };
  intel_2026?: {
    whatItMeans?: string;
    whatYouNeed?: string;
    whatChanged?: string;
    zantaraOpener?: string;
    baliContext?: string;
    youllAlsoNeed?: string;
    whoThisIsFor?: string;
    coverImage?: string | null;
  };
  /** L4 — Bali sovereign-local status (moratorium 2026-05-13). National PMA openness != Bali registrability. */
  baliL4?: KBLIBaliL4;
}

/** L4 Bali status — the sovereign-local layer (moratorium B.27.000/642, 2026-05-13). */
export interface KBLIBaliL4 {
  status: string;
  reason: string;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  needsReview: boolean;
  blocked: boolean;
  from2020?: string | null;
  moratorium?: {
    rule?: string;
    effective?: string;
    source?: string;
    virtualOffice?: string;
  };
}

// -----------------------------------------------------------------------------
// Editorial / Gold content
// -----------------------------------------------------------------------------

/** TKA-eligible position from Kepmenaker 228/2019 */
export interface KBLIJabatanTKA {
  /** Position title in English */
  titleEn: string;
  /** Position title in Indonesian */
  titleId: string;
  /** ISCO occupation code */
  isco: string;
  /** Whether this is a temporary/emergency position */
  temporary?: boolean;
}

/** TKA workforce information for a KBLI code */
export interface KBLITkaInfo {
  /** Kepmenaker category ID (1-18) */
  categoryId: number;
  /** Category name in English */
  categoryName: string;
  /** Total jabatan available in this category */
  totalInCategory: number;
  /** Number of positions selected as relevant for this specific KBLI code */
  selectedForThisCode?: number;
  /** ISCO occupation groups selected for this KBLI code */
  iscoGroupsSelected?: string[];
  /** Method used to select relevant positions */
  selectionMethod?: string;
  /** Specific positions most relevant to this KBLI code */
  relevantPositions: KBLIJabatanTKA[];
  /** Key insight about TKA restrictions for this code */
  insight: string;
  /** KEDUA provision note (Directors/Commissioners exempt if not managing personalia) */
  keduaNote: string;
}

/** Gold-tier editorial content for featured KBLI codes */
export interface KBLIGoldContent {
  /** Plain-language explanation of what this business code covers */
  whatItMeans: string;
  /** Key requirements, licenses, and steps to get started */
  whatYouNeed: string;
  /** Changes from KBLI 2020 to 2025 for this code */
  whatChanged: string;
  /** Bali-specific context, local regulations, and practical tips */
  baliContext: string;
  /** Related codes, complementary activities, common pairings */
  youllAlsoNeed: string;
  /** Short conversational opener for the Zantara chatbot */
  zantaraOpener: string;
  /** TKA (foreign worker) positions available under Kepmenaker 228/2019 */
  tkaInfo?: KBLITkaInfo;
}

// -----------------------------------------------------------------------------
// Section metadata
// -----------------------------------------------------------------------------

/** KBLI section (top-level classification grouping) */
export interface KBLISection {
  id: string;
  nameEn: string;
  nameId: string;
  icon: string;
  codeCount: number;
  description: string;
}

// -----------------------------------------------------------------------------
// Search
// -----------------------------------------------------------------------------

/** Search result wrapping a KBLI code with relevance metadata */
export interface KBLISearchResult {
  code: KBLICode;
  score: number;
  matchType: KBLIMatchType;
}
