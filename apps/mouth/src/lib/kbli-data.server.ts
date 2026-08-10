import {
  humanizeInternalEnums,
  humanizeIntelBlock,
} from "@/lib/kbli-status-labels";
import fs from "fs";
import path from "path";
import type {
  KBLIRawCode,
  KBLICode,
  KBLISection,
  KBLIGoldContent,
} from "./kbli-types";
import { resolveLicenseType } from "./kbli-derive";
import { resolvePmaCap } from "./kbli-pma-cap";
import { perpresCitation } from "./kbli-perpres-locator";
import { deriveProvenance } from "./kbli-provenance";
import { riskDispute } from "./kbli-risk-dispute";
import { perpresSlice } from "./kbli-perpres-slice";
import { getSectionFromCode } from "./kbli-section";

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

/**
 * Get gold content for a single code.
 *
 * Cured at THIS choke point, not at the call sites: the gold layout on
 * `/kbli/[code]` renders `gold.whatChanged` / `gold.whatYouNeed` /
 * `gold.baliContext` / `gold.zantaraOpener` / `gold.tkaInfo` DIRECTLY, bypassing
 * `transformCode`'s merged `intel` entirely — so the loader cure never reached
 * them and 113 of the 428 gold codes were still printing `MATCH_CON_AGGREGAZIONE`
 * and friends at readers (whatChanged 111, whatYouNeed 11, baliContext 3,
 * zantaraOpener 2). Curing the accessor covers the page, `/api/kbli/gold/[code]`
 * and any future consumer at once. Found by the adversarial review of this
 * change, then re-measured against the gold file before fixing.
 */
export function getGoldContent(code: string): KBLIGoldContent | null {
  const raw = loadGoldData()[code];
  return raw ? humanizeIntelBlock(raw) : null;
}

/** Check if a code has gold content */
export function hasGoldContent(code: string): boolean {
  return code in loadGoldData();
}

let _datasetLastModified: Date | null = null;

const DATASET_VERSION_PATH = path.join(
  process.cwd(),
  "data",
  "kbli-dataset-version.json",
);

/**
 * Last real content-change event for the KBLI dataset, read from the
 * committed sidecar data/kbli-dataset-version.json. NOT the file mtime:
 * git/Vercel checkouts stamp clone time on every file, so mtime would
 * claim "modified today" on every deploy (red-team finding 2026-07-05).
 * Single source for every surface that claims a modification date for
 * /kbli/* pages (sitemap lastmod, JSON-LD dateModified) — the two must
 * never diverge or Google stops trusting either. A vitest guard fails
 * when the dataset hash changes without a sidecar bump.
 */
export function getKbliDatasetLastModified(): Date {
  if (!_datasetLastModified) {
    try {
      const version = JSON.parse(
        fs.readFileSync(DATASET_VERSION_PATH, "utf-8"),
      ) as { lastModified: string };
      _datasetLastModified = new Date(version.lastModified);
    } catch {
      _datasetLastModified = new Date("2026-06-19");
    }
  }
  return _datasetLastModified;
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
  // Mandate 12 fix (2026-08-09, PENDING-ARMS.md "sektor_id is not a
  // malformed KBLI section"): the section is derived from the code's
  // 2-digit prefix, the same single source of truth kbli-data.ts uses —
  // NEVER from `sektor_id`, which is a PP28/2025 Lampiran locator (almost
  // always starting with the roman numeral "I") and collapsed 1318/1559
  // codes onto the single fake section "I". An unmapped prefix returns
  // null (honest "unknown"), not a silent default to any letter.
  const section = getSectionFromCode(code);
  const goldEntry = gold[code];

  // Merge intel: gold content takes precedence for the editorial fields. EXCEPTION:
  // `baliContext` on a Bali-BLOCKED code. The static gold baliContext is stale for
  // ~56 blocked codes — it still describes setting up a "PT PMA"/"100% foreign"
  // operation on a code the 2026 moratorium now blocks, directly contradicting the
  // verdict. The L4 layer (#1814 risk-tier pass, #1815 placeholder fix) keeps the
  // current truth in raw.intel_2026.baliContext / l4_bali.reason. So when the code
  // is blocked AND the gold text reads as a foreign-ownership go-ahead, prefer the
  // live L4 text; otherwise keep the richer gold editorial.
  const goldBali = goldEntry?.baliContext || "";
  const liveBali = raw.intel_2026?.baliContext || raw.l4_bali?.reason || "";
  const goldBaliMisleads =
    !!raw.l4_bali?.blocked &&
    /\b(PT PMA|100% foreign|foreign-owned|open to foreign)\b/i.test(goldBali);
  // Internal pipeline symbols resolved to the labels the badges use — the gold
  // layer inherited the same narration, so it needs the same pass. Presentation
  // only; no verdict changes. See @/lib/kbli-status-labels.
  const intel = humanizeIntelBlock(
    goldEntry
      ? {
          whatItMeans: goldEntry.whatItMeans || "",
          whatYouNeed: goldEntry.whatYouNeed || "",
          whatChanged: goldEntry.whatChanged || "",
          baliContext: goldBaliMisleads && liveBali ? liveBali : goldBali,
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
        : undefined,
  );

  return {
    code,
    titleId: raw.judul,
    titleEn: raw.judul,
    description: raw.uraian || "",
    section,
    sectionName: section ? SECTION_NAMES_EN[section] || section : null,
    pma: {
      status: mapPmaStatus(raw.pma_status),
      maxForeign: resolvePmaCap(raw),
      condition: raw.pma_kondisi,
      isPriority: raw.pma_prioritas || false,
      note: raw.pma_nota,
      source: raw.pma_source,
      capSpecial: raw.pma_cap_special === true,
      capVerified: raw.pma_cap_verified !== false,
      routeTo: raw.pma_route_to ?? null,
      // Same single source as the sibling reader in kbli-data.ts. The cap was
      // once read in these two places with different defaults and rendered
      // "0% Open" on a live page; the citation gets one writer from the start.
      citation: perpresCitation(code),
    },
    licensing: (raw.per_skala || []).map((s) => ({
      scales: s.skala_usaha,
      riskCategory: s.kategori_risiko,
      // Derive the license from the risk tier when `perizinan` is empty (Pasal 124(4)) —
      // a flat "NIB" understated the 937 high-risk codes. Parity with the Swift app.
      licenseType: resolveLicenseType(s.perizinan, s.kategori_risiko),
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
      bpsCrosswalk: raw.bps_2020_ancestors
        ? {
            codes: raw.bps_2020_ancestors.codes || [],
            adjudicationStatus:
              raw.bps_2020_ancestors.adjudication_status || "mechanical-only",
            inheritanceVerdict:
              raw.bps_2020_ancestors.inheritance_verdict || "not-adjudicated",
          }
        : undefined,
    },
    intel,
    // L4 — Bali sovereign-local status (national PMA openness != Bali registrability)
    baliL4: raw.l4_bali?.status
      ? {
          status: raw.l4_bali.status,
          // Reader-facing prose (badge tooltip + generated FAQ answer) — cured like
          // the editorial layer. `_data_note` deliberately stays verbatim: there the
          // symbol is cited AS EVIDENCE of divergence, not narrated at a reader.
          reason: humanizeInternalEnums(raw.l4_bali.reason || ""),
          confidence: raw.l4_bali.confidence || "MEDIUM",
          needsReview: !!raw.l4_bali.needs_review,
          blocked: !!raw.l4_bali.blocked,
          from2020: raw.l4_bali.from_2020 ?? null,
          moratorium: raw.l4_bali.moratorium
            ? {
                rule: raw.l4_bali.moratorium.rule || "",
                effective: raw.l4_bali.moratorium.effective || "",
                source: raw.l4_bali.moratorium.source || "",
                virtualOffice: raw.l4_bali.moratorium.virtual_office || "",
              }
            : undefined,
        }
      : undefined,
    provenance: deriveProvenance(raw),
    riskDispute: riskDispute(code) ?? undefined,
    // Same dual-reader discipline as riskDispute above — set in BOTH
    // transforms (kbli-data.ts is the one the page actually consumes) or the
    // two readers disagree on the 14 slice-disclosure codes.
    perpresSlice: perpresSlice(code) ?? undefined,
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
