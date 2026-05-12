// =============================================================================
// KBLI 2025 Data Loader & Transformer
// Reads raw JSON, transforms to typed KBLICode objects, provides query functions.
// Runs server-side at build time (Next.js static generation).
// =============================================================================

import fs from "fs";
import path from "path";
import type {
  KBLICode,
  KBLIRawCode,
  KBLIRawDataFile,
  KBLISection,
  KBLIPmaStatus,
  KBLILicenseByScale,
  KBLITransition,
  KBLITier,
} from "./kbli-types";

import { ENGLISH_TITLES } from "./kbli-english";
import { GOLD_CODES } from "./kbli-gold-codes";

// =============================================================================
// Constants: Section metadata
// =============================================================================

/** KBLI section letter -> 2-digit code prefixes */
const SECTION_PREFIX_MAP: Record<string, string[]> = {
  A: ["01", "02", "03"],
  B: ["05", "06", "07", "08", "09"],
  C: [
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
  ],
  D: ["35"],
  E: ["36", "37", "38", "39"],
  F: ["41", "42", "43"],
  G: ["45", "46", "47"],
  H: ["49", "50", "51", "52", "53"],
  I: ["55", "56"],
  J: ["58", "59", "60", "61", "62", "63"],
  K: ["64", "65", "66"],
  L: ["68"],
  M: ["69", "70", "71", "72", "73", "74", "75"],
  N: ["77", "78", "79", "80", "81", "82"],
  O: ["84"],
  P: ["85"],
  Q: ["86", "87", "88"],
  R: ["90", "91", "92", "93"],
  S: ["94", "95", "96"],
  T: ["97", "98"],
  U: ["99"],
};

/** Reverse lookup: 2-digit prefix -> section letter */
const PREFIX_TO_SECTION: Record<string, string> = {};
for (const [section, prefixes] of Object.entries(SECTION_PREFIX_MAP)) {
  for (const prefix of prefixes) {
    PREFIX_TO_SECTION[prefix] = section;
  }
}

/** Section display metadata */
const SECTION_META: Record<
  string,
  { nameEn: string; nameId: string; icon: string; description: string }
> = {
  A: {
    nameEn: "Agriculture, Forestry & Fishing",
    nameId: "Pertanian, Kehutanan dan Perikanan",
    icon: "🌾",
    description: "Crop farming, livestock, forestry, and fishing activities",
  },
  B: {
    nameEn: "Mining & Quarrying",
    nameId: "Pertambangan dan Penggalian",
    icon: "⛏️",
    description: "Extraction of minerals, oil, gas, and quarrying",
  },
  C: {
    nameEn: "Manufacturing",
    nameId: "Industri Pengolahan",
    icon: "🏭",
    description: "Transformation of materials into finished goods",
  },
  D: {
    nameEn: "Electricity & Gas Supply",
    nameId: "Pengadaan Listrik dan Gas",
    icon: "⚡",
    description: "Generation and distribution of electricity and gas",
  },
  E: {
    nameEn: "Water Supply & Waste Management",
    nameId: "Pengadaan Air, Pengelolaan Sampah dan Daur Ulang",
    icon: "💧",
    description: "Water collection, treatment, and waste management",
  },
  F: {
    nameEn: "Construction",
    nameId: "Konstruksi",
    icon: "🏗️",
    description: "Building construction and civil engineering",
  },
  G: {
    nameEn: "Wholesale & Retail Trade",
    nameId: "Perdagangan Besar dan Eceran",
    icon: "🛒",
    description: "Wholesale and retail sale of goods",
  },
  H: {
    nameEn: "Transportation & Storage",
    nameId: "Transportasi dan Pergudangan",
    icon: "🚚",
    description: "Land, water, air transport and warehousing",
  },
  I: {
    nameEn: "Accommodation & Food Service",
    nameId: "Penyediaan Akomodasi dan Makan Minum",
    icon: "🏨",
    description: "Hotels, restaurants, and food service activities",
  },
  J: {
    nameEn: "Information & Communication",
    nameId: "Informasi dan Komunikasi",
    icon: "📡",
    description: "Publishing, broadcasting, telecommunications, and IT",
  },
  K: {
    nameEn: "Financial & Insurance Activities",
    nameId: "Aktivitas Keuangan dan Asuransi",
    icon: "🏦",
    description: "Banking, insurance, and financial services",
  },
  L: {
    nameEn: "Real Estate Activities",
    nameId: "Real Estat",
    icon: "🏠",
    description: "Buying, selling, and managing real estate",
  },
  M: {
    nameEn: "Professional, Scientific & Technical",
    nameId: "Aktivitas Profesional, Ilmiah dan Teknis",
    icon: "🔬",
    description: "Legal, accounting, consulting, and scientific activities",
  },
  N: {
    nameEn: "Administrative & Support Services",
    nameId: "Aktivitas Penyewaan dan Sewa Guna Usaha",
    icon: "📋",
    description: "Rental, employment, security, and support services",
  },
  O: {
    nameEn: "Public Administration & Defence",
    nameId: "Administrasi Pemerintahan dan Jaminan Sosial",
    icon: "🏛️",
    description: "Government administration and social security",
  },
  P: {
    nameEn: "Education",
    nameId: "Pendidikan",
    icon: "🎓",
    description: "Education at all levels and types",
  },
  Q: {
    nameEn: "Human Health & Social Work",
    nameId: "Aktivitas Kesehatan Manusia dan Aktivitas Sosial",
    icon: "🏥",
    description: "Healthcare, residential care, and social work",
  },
  R: {
    nameEn: "Arts, Entertainment & Recreation",
    nameId: "Kesenian, Hiburan dan Rekreasi",
    icon: "🎭",
    description: "Creative arts, sports, and recreation",
  },
  S: {
    nameEn: "Other Service Activities",
    nameId: "Aktivitas Jasa Lainnya",
    icon: "🔧",
    description: "Membership organizations, repair, and personal services",
  },
  T: {
    nameEn: "Household Activities",
    nameId: "Aktivitas Rumah Tangga",
    icon: "🏡",
    description: "Activities of households as employers",
  },
  U: {
    nameEn: "Extraterritorial Organizations",
    nameId: "Aktivitas Badan Internasional",
    icon: "🌐",
    description: "Activities of international organizations and bodies",
  },
  V: {
    nameEn: "Activities Not Yet Classified",
    nameId: "Kegiatan yang Belum Jelas Batasannya",
    icon: "❓",
    description: "Activities not adequately defined elsewhere",
  },
};

// =============================================================================
// Indonesian title case conversion
// =============================================================================

/** Indonesian prepositions/conjunctions that stay lowercase in title case */
const ID_LOWERCASE_WORDS = new Set([
  "dan",
  "di",
  "yang",
  "untuk",
  "dari",
  "ke",
  "atau",
  "dengan",
  "pada",
  "oleh",
  "dalam",
  "atas",
  "sebagai",
  "serta",
  "melalui",
]);

/**
 * Convert an UPPERCASE Indonesian string to Title Case.
 * Keeps Indonesian prepositions/conjunctions lowercase (except at start).
 */
function toTitleCase(text: string): string {
  if (!text) return text;

  return text
    .toLowerCase()
    .split(/\s+/)
    .map((word, index) => {
      if (index === 0) {
        // Always capitalize first word
        return word.charAt(0).toUpperCase() + word.slice(1);
      }
      if (ID_LOWERCASE_WORDS.has(word)) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

// =============================================================================
// PMA status mapping
// =============================================================================

function mapPmaStatus(raw: string): KBLIPmaStatus {
  switch (raw) {
    case "TERBUKA":
      return "open";
    case "TERBATAS":
      return "restricted";
    case "TERTUTUP":
      return "closed";
    default:
      return "open";
  }
}

// =============================================================================
// Section derivation from KBLI code
// =============================================================================

function getSectionFromCode(code: string): string | null {
  const prefix = code.substring(0, 2);
  return PREFIX_TO_SECTION[prefix] ?? null;
}

// =============================================================================
// Keyword extraction (simple, from title and description)
// =============================================================================

/** Extract meaningful keywords from title and description */
function extractKeywords(title: string, description: string): string[] {
  const stopwords = new Set([
    "yang",
    "dan",
    "di",
    "dari",
    "untuk",
    "dengan",
    "pada",
    "ke",
    "atau",
    "ini",
    "itu",
    "juga",
    "serta",
    "tidak",
    "dalam",
    "oleh",
    "atas",
    "sebagai",
    "melalui",
    "adalah",
    "akan",
    "telah",
    "bukan",
    "belum",
    "sudah",
    "bisa",
    "dapat",
    "harus",
    "perlu",
    "kelompok",
    "mencakup",
    "kegiatan",
    "termasuk",
    "lihat",
    "usaha",
    "jasa",
    "lainnya",
    "lain",
  ]);

  const combined = `${title} ${description}`.toLowerCase();
  const words = combined.match(/[a-zA-Z\u00C0-\u024F]+/g) ?? [];

  const unique = new Set<string>();
  for (const word of words) {
    if (word.length >= 3 && !stopwords.has(word)) {
      unique.add(word);
    }
  }

  return Array.from(unique).slice(0, 20);
}

// =============================================================================
// Tier assignment
// =============================================================================

function assignTier(code: string): KBLITier {
  if (GOLD_CODES.has(code)) return "gold";
  // Silver tier: codes with English titles available
  if (ENGLISH_TITLES[code]) return "silver";
  return "bronze";
}

// =============================================================================
// Transform a single raw record
// =============================================================================

function transformRecord(raw: KBLIRawCode): KBLICode {
  const code = raw.kode_kbli_2025;
  const section = getSectionFromCode(code);
  const sectionMeta = section ? SECTION_META[section] : null;

  const titleId = toTitleCase(raw.judul);
  const titleEn = ENGLISH_TITLES[code] ?? titleId; // Fallback to Indonesian title

  const pma = {
    status: mapPmaStatus(raw.pma_status),
    maxForeign: raw.pma_max_asing,
    condition: raw.pma_kondisi,
    isPriority: raw.pma_prioritas,
    note: raw.pma_nota,
    source: raw.pma_source,
  };

  const licensing: KBLILicenseByScale[] = (raw.per_skala ?? []).map(
    (entry) => ({
      scales: entry.skala_usaha,
      riskCategory: entry.kategori_risiko,
      licenseType: entry.perizinan,
      requirements: entry.persyaratan,
      timeframe: entry.jangka_waktu,
      obligations: entry.kewajiban,
      authority: entry.kewenangan,
      fictivePositive: entry.fiktif_positif,
    }),
  );

  const transition: KBLITransition = {
    mappingStatus: raw.status_mapping,
    previousCodes: raw.pp28_sources ?? [],
    kbli2020Source: raw.kbli_2020_source,
    mappingNote: raw.mapping_note,
    aggregationNote: raw.aggregation_note,
  };

  return {
    code,
    titleId,
    titleEn,
    description: raw.uraian,
    section,
    sectionName: sectionMeta?.nameEn ?? null,
    pma,
    licensing,
    transition,
    tier: assignTier(code),
    keywords: extractKeywords(raw.judul, raw.uraian),
    intel_2026: raw.intel_2026,
  };
}

// =============================================================================
// Data loading & caching
// =============================================================================

/** Module-level cache */
let _allCodes: KBLICode[] | null = null;
let _codeMap: Map<string, KBLICode> | null = null;
let _sectionMap: Map<string, KBLICode[]> | null = null;
let _prefixMap: Map<string, KBLICode[]> | null = null;

/**
 * Load and parse the KBLI JSON file.
 * Data is cached in module-level variables after first call.
 */
function loadData(): void {
  if (_allCodes !== null) return;

  // Load from apps/mouth/data/ — the canonical location for Vercel deployment
  const localPath = path.join(
    process.cwd(),
    "data",
    "KBLI_2025_FINAL_CLEAN.json",
  );
  const fallbackPath = path.join(process.cwd(), "data", "kbli-2025.json");

  let rawData: string;
  if (fs.existsSync(localPath)) {
    rawData = fs.readFileSync(localPath, "utf-8");
  } else if (fs.existsSync(fallbackPath)) {
    rawData = fs.readFileSync(fallbackPath, "utf-8");
  } else {
    throw new Error(
      `KBLI data file not found. Tried:\n  ${localPath}\n  ${fallbackPath}`,
    );
  }

  const raw: KBLIRawDataFile = JSON.parse(rawData);
  const codes = raw.data.map(transformRecord);

  // Build lookup maps
  const codeMap = new Map<string, KBLICode>();
  const sectionMap = new Map<string, KBLICode[]>();
  const prefixMap = new Map<string, KBLICode[]>();

  for (const kbli of codes) {
    codeMap.set(kbli.code, kbli);

    // Section index
    if (kbli.section) {
      const existing = sectionMap.get(kbli.section) ?? [];
      existing.push(kbli);
      sectionMap.set(kbli.section, existing);
    }

    // 3-digit prefix index (for related codes)
    const prefix3 = kbli.code.substring(0, 3);
    const prefixList = prefixMap.get(prefix3) ?? [];
    prefixList.push(kbli);
    prefixMap.set(prefix3, prefixList);
  }

  _allCodes = codes;
  _codeMap = codeMap;
  _sectionMap = sectionMap;
  _prefixMap = prefixMap;
}

// =============================================================================
// Public API
// =============================================================================

/**
 * Get all 1,563 KBLI codes as processed objects.
 * Data is loaded and cached on first call.
 */
export function getAllCodes(): KBLICode[] {
  loadData();
  return _allCodes!;
}

/**
 * Get a single KBLI code by its 5-digit code string.
 * Returns undefined if not found.
 */
export function getCode(code: string): KBLICode | undefined {
  loadData();
  return _codeMap!.get(code);
}

/**
 * Get all KBLI codes belonging to a given section letter (A-U).
 * Returns empty array if section not found.
 */
export function getCodesBySection(section: string): KBLICode[] {
  loadData();
  return _sectionMap!.get(section.toUpperCase()) ?? [];
}

/**
 * Get all 22 KBLI sections with metadata and code counts.
 */
export function getSections(): KBLISection[] {
  loadData();

  return Object.entries(SECTION_META).map(([id, meta]) => ({
    id,
    nameEn: meta.nameEn,
    nameId: meta.nameId,
    icon: meta.icon,
    codeCount: _sectionMap!.get(id)?.length ?? 0,
    description: meta.description,
  }));
}

/**
 * Find related KBLI codes for a given code.
 * Strategy: same 3-digit prefix first, then same section, excluding self.
 * Returns up to `limit` results (default 6).
 */
export function getRelatedCodes(code: string, limit: number = 6): KBLICode[] {
  loadData();

  const target = _codeMap!.get(code);
  if (!target) return [];

  const result: KBLICode[] = [];
  const seen = new Set<string>([code]);

  // Phase 1: Same 3-digit prefix (most closely related)
  const prefix3 = code.substring(0, 3);
  const prefixSiblings = _prefixMap!.get(prefix3) ?? [];
  for (const sibling of prefixSiblings) {
    if (result.length >= limit) break;
    if (!seen.has(sibling.code)) {
      result.push(sibling);
      seen.add(sibling.code);
    }
  }

  // Phase 2: Same section (broader relation)
  if (result.length < limit && target.section) {
    const sectionCodes = _sectionMap!.get(target.section) ?? [];
    for (const item of sectionCodes) {
      if (result.length >= limit) break;
      if (!seen.has(item.code)) {
        result.push(item);
        seen.add(item.code);
      }
    }
  }

  return result;
}

/**
 * Get section metadata for a given section letter.
 */
export function getSectionMeta(sectionId: string): {
  nameEn: string;
  nameId: string;
  icon: string;
  description: string;
} | null {
  return SECTION_META[sectionId.toUpperCase()] ?? null;
}

// =============================================================================
// Hero gradient — unique per sector, abstract and coherent
// =============================================================================

const SECTOR_HERO: Record<string, { gradient: string; pattern: string }> = {
  I: {
    gradient: "135deg, #e85d04, #f48c06, #dc2f02",
    pattern:
      "radial-gradient(circle at 20% 80%, rgba(255,255,255,0.08) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.05) 0%, transparent 40%)",
  },
  L: {
    gradient: "135deg, #0077b6, #00b4d8, #0096c7",
    pattern:
      "radial-gradient(circle at 75% 75%, rgba(255,255,255,0.07) 0%, transparent 50%), radial-gradient(circle at 15% 30%, rgba(255,255,255,0.04) 0%, transparent 40%)",
  },
  G: {
    gradient: "135deg, #d00000, #e85d04, #dc2f02",
    pattern:
      "radial-gradient(circle at 30% 70%, rgba(255,255,255,0.06) 0%, transparent 45%), radial-gradient(circle at 85% 25%, rgba(255,255,255,0.04) 0%, transparent 35%)",
  },
  J: {
    gradient: "135deg, #3a0ca3, #7209b7, #560bad",
    pattern:
      "radial-gradient(circle at 60% 80%, rgba(255,255,255,0.06) 0%, transparent 50%), radial-gradient(circle at 20% 20%, rgba(255,255,255,0.04) 0%, transparent 40%)",
  },
  N: {
    gradient: "135deg, #006d77, #83c5be, #0a9396",
    pattern:
      "radial-gradient(circle at 50% 70%, rgba(255,255,255,0.06) 0%, transparent 45%)",
  },
  A: {
    gradient: "135deg, #2d6a4f, #52b788, #40916c",
    pattern:
      "radial-gradient(circle at 40% 80%, rgba(255,255,255,0.06) 0%, transparent 50%)",
  },
  F: {
    gradient: "135deg, #774936, #c6893e, #a67c52",
    pattern:
      "radial-gradient(circle at 70% 70%, rgba(255,255,255,0.06) 0%, transparent 45%)",
  },
  M: {
    gradient: "135deg, #1d3557, #457b9d, #2a6f97",
    pattern:
      "radial-gradient(circle at 25% 75%, rgba(255,255,255,0.06) 0%, transparent 50%)",
  },
  R: {
    gradient: "135deg, #f72585, #b5179e, #7209b7",
    pattern:
      "radial-gradient(circle at 65% 80%, rgba(255,255,255,0.07) 0%, transparent 45%)",
  },
  P: {
    gradient: "135deg, #0466c8, #4cc9f0, #4895ef",
    pattern:
      "radial-gradient(circle at 35% 70%, rgba(255,255,255,0.06) 0%, transparent 50%)",
  },
  Q: {
    gradient: "135deg, #38b000, #70e000, #55a630",
    pattern:
      "radial-gradient(circle at 55% 75%, rgba(255,255,255,0.06) 0%, transparent 45%)",
  },
  C: {
    gradient: "135deg, #495057, #adb5bd, #6c757d",
    pattern:
      "radial-gradient(circle at 45% 65%, rgba(255,255,255,0.05) 0%, transparent 45%)",
  },
  E: {
    gradient: "135deg, #1b4332, #40916c, #2d6a4f",
    pattern:
      "radial-gradient(circle at 60% 80%, rgba(255,255,255,0.06) 0%, transparent 50%)",
  },
  S: {
    gradient: "135deg, #7b2cbf, #c77dff, #9d4edd",
    pattern:
      "radial-gradient(circle at 30% 75%, rgba(255,255,255,0.06) 0%, transparent 45%)",
  },
};

const DEFAULT_HERO = {
  gradient: "135deg, #343434, #4a4a4a, #3d3d3d",
  pattern:
    "radial-gradient(circle at 50% 70%, rgba(212,132,90,0.08) 0%, transparent 50%)",
};

export function getHeroStyle(section: string | null): {
  gradient: string;
  pattern: string;
} {
  return (section && SECTOR_HERO[section]) || DEFAULT_HERO;
}
