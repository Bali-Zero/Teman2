import fs from "fs";
import path from "path";
import type {
  KBLIRawCode,
  KBLICode,
  KBLISection,
  KBLIGoldContent,
} from "./kbli-types";

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
  "data",
  "KBLI_2025_FINAL_CLEAN.json",
);

const GOLD_PATH = path.join(process.cwd(), "data", "kbli-gold-all.json");

// ─── Caches ─────────────────────────────────────────────────────────────────

let _listCache: KBLICode[] | null = null;
let _mapCache: Map<string, KBLICode> | null = null;
let _goldCache: Record<string, KBLIGoldContent> | null = null;

function loadGoldData(): Record<string, KBLIGoldContent> {
  if (_goldCache) return _goldCache;
  try {
    const raw = JSON.parse(fs.readFileSync(GOLD_PATH, "utf-8"));
    _goldCache = raw.data ?? raw;
    return _goldCache!;
  } catch {
    process.stderr.write(
      `[kbli] Failed to load gold data from: ${GOLD_PATH}\n`,
    );
    _goldCache = {};
    return _goldCache;
  }
}

function loadAllCodes(): { list: KBLICode[]; map: Map<string, KBLICode> } {
  if (_listCache && _mapCache) return { list: _listCache, map: _mapCache };

  try {
    const rawData = fs.readFileSync(DATA_PATH, "utf-8");
    const parsed = JSON.parse(rawData);
    const rawCodes: KBLIRawCode[] = parsed.data;
    const gold = loadGoldData();

    const list: KBLICode[] = [];
    const map = new Map<string, KBLICode>();

    for (const raw of rawCodes) {
      const transformed = transformCode(raw, gold);
      list.push(transformed);
      map.set(transformed.code, transformed);
    }

    _listCache = list;
    _mapCache = map;
    return { list, map };
  } catch (err) {
    process.stderr.write(
      `[kbli] Error loading data from: ${DATA_PATH} ${err}\n`,
    );
    return { list: [], map: new Map() };
  }
}

/** Load all KBLI codes. Cached in memory during build. */
export function getAllCodes(): KBLICode[] {
  return loadAllCodes().list;
}

/** Get a single code by its 5-digit ID — O(1) hashmap lookup */
export function getCode(code: string): KBLICode | undefined {
  return loadAllCodes().map.get(code);
}

/** Get gold content for a single code */
export function getGoldContent(code: string): KBLIGoldContent | null {
  return loadGoldData()[code] ?? null;
}

/** Check if a code has gold content */
export function hasGoldContent(code: string): boolean {
  return code in loadGoldData();
}

/** Get all codes that have gold content */
export function getGoldCodes(): string[] {
  return Object.keys(loadGoldData());
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
      nameId: id,
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

function transformCode(
  raw: KBLIRawCode,
  gold: Record<string, KBLIGoldContent>,
): KBLICode {
  const code = raw.kode_kbli_2025;
  const section = (raw.sektor_id || "?").charAt(0);
  const goldEntry = gold[code];

  // Merge intel: gold content takes precedence, fall back to source intel_2026
  const intel = goldEntry
    ? {
        whatItMeans: goldEntry.whatItMeans || "",
        whatYouNeed: goldEntry.whatYouNeed || "",
        whatChanged: goldEntry.whatChanged || "",
        baliContext: goldEntry.baliContext || "",
        zantaraOpener: goldEntry.zantaraOpener || "",
        youllAlsoNeed: goldEntry.youllAlsoNeed || "",
        coverImage: raw.intel_2026?.coverImage || null,
      }
    : raw.intel_2026
      ? {
          whatItMeans: raw.intel_2026.whatItMeans || "",
          whatYouNeed: raw.intel_2026.whatYouNeed || "",
          whatChanged: raw.intel_2026.whatChanged || "",
          baliContext: raw.intel_2026.baliContext || "",
          zantaraOpener: raw.intel_2026.zantaraOpener || "",
          youllAlsoNeed: raw.intel_2026.youllAlsoNeed || "",
          coverImage: raw.intel_2026.coverImage || null,
        }
      : undefined;

  return {
    code,
    titleId: raw.judul,
    titleEn: raw.judul,
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
    intel,
    tier: goldEntry ? "gold" : "bronze",
    keywords: [],
  };
}

function mapPmaStatus(status: string): "open" | "restricted" | "closed" {
  const s = (status || "").toUpperCase();
  if (s === "TERBATAS") return "restricted";
  if (s === "TERTUTUP") return "closed";
  return "open";
}
