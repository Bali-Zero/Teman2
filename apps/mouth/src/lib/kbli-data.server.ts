import fs from "fs";
import path from "path";
import type { KBLIRawCode, KBLICode, KBLISection } from "./kbli-types";
import { GOLD_CODES } from "./kbli-gold-codes";

// Section names mapping
const SECTION_NAMES_EN: Record<string, string> = {
  A: "Agriculture, Forestry & Fishing",
  B: "Mining & Quarrying",
  C: "Manufacturing",
  D: "Electricity, Gas & Steam",
  E: "Water Supply & Waste Management",
  F: "Construction",
  G: "Wholesale & Retail Trade",
  H: "Transportation & Storage",
  I: "Accommodation & Food Service",
  J: "Information & Communication",
  K: "Financial & Insurance",
  L: "Real Estate",
  M: "Professional, Scientific & Technical",
  N: "Administrative & Support Services",
  O: "Public Administration & Defence",
  P: "Education",
  Q: "Human Health & Social Work",
  R: "Arts, Entertainment & Recreation",
  S: "Other Service Activities",
  T: "Household Activities",
  U: "Extraterritorial Organizations",
  V: "Activities Not Yet Defined",
};

const SECTION_ICONS: Record<string, string> = {
  A: "🌾",
  B: "⛏️",
  C: "🏭",
  D: "⚡",
  E: "💧",
  F: "🏗️",
  G: "🛒",
  H: "🚛",
  I: "🍽️",
  J: "💻",
  K: "🏦",
  L: "🏠",
  M: "🔬",
  N: "📋",
  O: "🏛️",
  P: "🎓",
  Q: "🏥",
  R: "🎭",
  S: "💇",
  T: "🏡",
  U: "🌐",
  V: "❓",
};

const DATA_PATH = path.join(
  process.cwd(),
  "..",
  "..",
  "source_documents",
  "KBLI_2025_FINAL_CLEAN.json",
);

let _cache: KBLICode[] | null = null;

/** Load all KBLI codes. Cached in memory during build. */
export function getAllCodes(): KBLICode[] {
  if (_cache) return _cache;

  try {
    const rawData = fs.readFileSync(DATA_PATH, "utf-8");
    const parsed = JSON.parse(rawData);
    const rawCodes: KBLIRawCode[] = parsed.data;

    _cache = rawCodes.map(transformCode);
    return _cache;
  } catch (err) {
    // eslint-disable-next-line no-console
    process.stderr.write(
      `❌ Error loading KBLI data from: ${DATA_PATH} ${err}\n`,
    );
    return [];
  }
}

/** Get a single code by its 5-digit ID */
export function getCode(code: string): KBLICode | undefined {
  return getAllCodes().find((c) => c.code === code);
}

/** Get all unique sections with metadata */
export function getSections(): KBLISection[] {
  const codes = getAllCodes();
  const sectionMap = new Map<string, number>();

  for (const code of codes) {
    const sec = code.section || "?";
    sectionMap.set(sec, (sectionMap.get(sec) || 0) + 1);
  }

  return Array.from(sectionMap.entries())
    .map(([id, count]) => ({
      id,
      nameEn: SECTION_NAMES_EN[id] || id,
      nameId: id, // Fallback
      icon: SECTION_ICONS[id] || "📋",
      codeCount: count,
      description: SECTION_DESCRIPTIONS[id] || "",
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

const SECTION_DESCRIPTIONS: Record<string, string> = {
  A: "Farming, animal husbandry, forestry, and fishing activities",
  B: "Mining, quarrying, and extraction of minerals",
  C: "Processing raw materials into finished goods",
  D: "Generation and distribution of electricity, gas, and steam",
  E: "Water collection, treatment, sewerage, and waste management",
  F: "Building construction, civil engineering, and specialized construction",
  G: "Wholesale and retail sale of goods, vehicle repair",
  H: "Land, water, and air transportation and warehousing",
  I: "Hotels, resorts, restaurants, bars, and catering",
  J: "Publishing, telecoms, IT services, and digital media",
  K: "Banking, insurance, pension funds, and financial services",
  L: "Real estate buying, selling, renting, and management",
  M: "Legal, accounting, consulting, architecture, and R&D",
  N: "Rental, employment, travel agencies, security, and office support",
  O: "Government administration, defence, and social security",
  P: "Pre-primary through higher education and training",
  Q: "Hospitals, clinics, social care, and health services",
  R: "Creative arts, sports, amusement, and recreation",
  S: "Professional associations, repair, personal services (spa, wellness)",
  T: "Household employers and subsistence activities",
  U: "International organizations and diplomatic bodies",
  V: "Activities not adequately defined elsewhere",
};

function transformCode(raw: KBLIRawCode): KBLICode {
  const code = raw.kode_kbli_2025;
  const section = (raw.sektor_id || "?").charAt(0);

  return {
    code,
    titleId: raw.judul,
    titleEn: raw.judul, // Fallback
    description: raw.uraian || "",
    section,
    sectionName: SECTION_NAMES_EN[section] || section,
    pma: {
      status: mapPmaStatus(raw.pma_status),
      maxForeign: raw.pma_max_asing || 0,
      condition: raw.pma_kondisi,
      isPriority: raw.pma_prioritas || false,
      note: raw.pma_nota,
      source: raw.pma_source,
    },
    licensing: (raw.per_skala || []).map((s) => ({
      scales: s.skala_usaha,
      riskCategory: s.kategori_risiko,
      licenseType: s.perizinan,
      requirements: s.persyaratan,
      timeframe: s.jangka_waktu,
      obligations: s.kewajiban,
      authority: s.kewenangan,
      fictivePositive: s.fiktif_positif || false,
    })),
    transition: {
      mappingStatus: raw.status_mapping,
      previousCodes: raw.pp28_sources || [],
      mappingNote: raw.mapping_note || undefined,
      aggregationNote: raw.aggregation_note || undefined,
    },
    intel: raw.intel_2026
      ? {
          whatItMeans: raw.intel_2026.whatItMeans || "",
          whatYouNeed: raw.intel_2026.whatYouNeed || "",
          whatChanged: raw.intel_2026.whatChanged || "",
          baliContext: raw.intel_2026.baliContext || "",
          zantaraOpener: raw.intel_2026.zantaraOpener || "",
          youllAlsoNeed: raw.intel_2026.youllAlsoNeed || "",
          coverImage: raw.intel_2026.coverImage || null,
        }
      : undefined,
    tier: GOLD_CODES.has(code) ? "gold" : "bronze",
    keywords: [],
  };
}

function mapPmaStatus(status: string): "open" | "restricted" | "closed" {
  const s = (status || "").toUpperCase();
  if (s === "TERBATAS") return "restricted";
  if (s === "TERTUTUP") return "closed";
  return "open";
}
