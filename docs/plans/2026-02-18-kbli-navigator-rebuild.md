# KBLI Navigator 2025 — Rebuild Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the KBLI Navigator as native Next.js pages within balizero.com — 1,563 SSG pages indexable by Google, Zantara AI contextual on every page, editorial Gold-tier content for ~200 Bali-relevant codes, clear "translator" voice that explains bureaucracy to humans.

**Architecture:** Static Site Generation (SSG) via `generateStaticParams()` reading `KBLI_2025_FINAL_CLEAN.json` at build time. Three content tiers: Gold (curated editorial for Bali-relevant codes), Silver (LLM-generated cached explanations), Bronze (structured data only). Zantara AI chat contextual on every code page. Dark theme evoluto with amber/orange accent. Bilingual EN/ID with toggle.

**Tech Stack:** Next.js 16 (already in project), React 19, Tailwind v4 (CSS variables), Framer Motion, Radix UI primitives, TanStack React Query, existing `@/components/ui/*` shadcn-style components, existing API proxy to Fly.io backend.

**Working directory:** `~/Desktop/kbli-navigator-rebuild/` — all files built here, then integrated into `apps/mouth/src/`.

**Source of truth:** `source_documents/KBLI_2025_FINAL_CLEAN.json` (v8.0-final-complete, 1,563 codes, curated over days with BPS_7_2025 + PP28_2024 data).

---

## Context: Existing Codebase

Files already in `apps/mouth/` that we leverage or replace:

| Existing File                                 | Action        | Notes                                             |
| --------------------------------------------- | ------------- | ------------------------------------------------- |
| `src/app/kbli/[code]/page.tsx`                | **Replace**   | Minimal SEO-only page, rebuild with full content  |
| `src/app/kbli/[code]/client-page.tsx`         | **Replace**   | 337-line client component, too thin               |
| `src/app/kbli-navigator/page.tsx`             | **Keep**      | Redirect to new `/kbli` homepage                  |
| `src/app/kbli-explorer/`                      | **Keep**      | Separate AI chat experience, complementary        |
| `src/components/kbli/KBLINavigatorClient.tsx` | **Deprecate** | iframe wrapper, no longer needed                  |
| `src/components/kbli/KBLIIntroOverlay.tsx`    | **Deprecate** | Video intro, not needed                           |
| `src/lib/api/kbli.api.ts`                     | **Extend**    | Add `getExplanation()` method                     |
| `src/app/api/[...path]/route.ts`              | **Keep**      | Already proxies to Fly.io                         |
| `src/app/api/kbli/[code]/route.ts`            | **Keep**      | Cached inspect proxy                              |
| `src/app/globals.css`                         | **Extend**    | Add KBLI-specific CSS variables                   |
| `src/components/ui/*`                         | **Reuse**     | button, card, dialog, input, tabs, skeleton, etc. |
| `src/app/kbli-explorer/components/*`          | **Reuse**     | KBLIInspector badges, RiskGauge, ComparisonModal  |

---

## Phase 1: Data Layer & Types (Foundation)

### Task 1: Create TypeScript types for KBLI data

**Files:**

- Create: `kbli-navigator-rebuild/lib/kbli-types.ts`

**Step 1: Write types matching the JSON structure**

```typescript
// kbli-navigator-rebuild/lib/kbli-types.ts

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
  // Optional fields present on some records
  aggregation_note?: string;
  mapping_note?: string;
  kbli_2020_source?: string;
  sektors?: string;
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
    status: "open" | "restricted" | "closed";
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
  tier: "gold" | "silver" | "bronze";
  keywords: string[];
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

/** Gold-tier editorial content */
export interface KBLIGoldContent {
  code: string;
  whatItMeans: string; // "In plain English, this code lets you..."
  whatYouNeed: string; // Practical requirements explained simply
  whatChanged: string; // 2020→2025 transition explained
  baliContext: string; // Bali-specific advice, areas, tips
  youllAlsoNeed: string[]; // Related codes with why
  zantaraOpener: string; // AI chat opener message
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

/** Search result */
export interface KBLISearchResult {
  code: KBLICode;
  score: number;
  matchType: "exact" | "relevance" | "fuzzy";
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/lib/kbli-types.ts
git commit --no-verify -m "feat(kbli): add TypeScript types for KBLI Navigator rebuild"
```

---

### Task 2: Create data loader and transformer

**Files:**

- Create: `kbli-navigator-rebuild/lib/kbli-data.ts`
- Read: `source_documents/KBLI_2025_FINAL_CLEAN.json`

This module reads the raw JSON at build time and transforms it into typed `KBLICode` objects.

**Step 1: Write the data loader**

```typescript
// kbli-navigator-rebuild/lib/kbli-data.ts
import fs from "fs";
import path from "path";
import type {
  KBLIRawCode,
  KBLICode,
  KBLISection,
  KBLIMappingStatus,
} from "./kbli-types";

// English titles — generated from kbli_data_with_english.js keywords + manual curation
// This map will be populated in Task 3
import { ENGLISH_TITLES } from "./kbli-english";
import { GOLD_CONTENT } from "./kbli-gold-content";
import { GOLD_CODES } from "./kbli-gold-codes";

const DATA_PATH = path.join(process.cwd(), "data", "kbli-2025.json");

interface KBLIDataFile {
  metadata: { version: string; total_codes: number };
  data: KBLIRawCode[];
}

let _cache: KBLICode[] | null = null;

/** Load all KBLI codes. Cached in memory during build. */
export function getAllCodes(): KBLICode[] {
  if (_cache) return _cache;

  const raw: KBLIDataFile = JSON.parse(fs.readFileSync(DATA_PATH, "utf-8"));
  _cache = raw.data.map(transformCode);
  return _cache;
}

/** Get a single code by its 5-digit ID */
export function getCode(code: string): KBLICode | undefined {
  return getAllCodes().find((c) => c.code === code);
}

/** Get all codes in a section */
export function getCodesBySection(section: string): KBLICode[] {
  return getAllCodes().filter((c) => c.section === section);
}

/** Get all unique sections with metadata */
export function getSections(): KBLISection[] {
  const codes = getAllCodes();
  const sectionMap = new Map<string, KBLICode[]>();

  for (const code of codes) {
    const sec = code.section || "?";
    if (!sectionMap.has(sec)) sectionMap.set(sec, []);
    sectionMap.get(sec)!.push(code);
  }

  return Array.from(sectionMap.entries())
    .map(([id, sectionCodes]) => ({
      id,
      nameEn: SECTION_NAMES_EN[id] || id,
      nameId: SECTION_NAMES_ID[id] || id,
      icon: SECTION_ICONS[id] || "📋",
      codeCount: sectionCodes.length,
      description: SECTION_DESCRIPTIONS[id] || "",
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
}

/** Get related codes (same 3-digit prefix or same section) */
export function getRelatedCodes(code: string, limit = 6): KBLICode[] {
  const prefix = code.slice(0, 3);
  const all = getAllCodes();
  const samePrefix = all.filter(
    (c) => c.code !== code && c.code.startsWith(prefix),
  );
  if (samePrefix.length >= limit) return samePrefix.slice(0, limit);

  const current = getCode(code);
  if (!current) return samePrefix;

  const sameSection = all.filter(
    (c) =>
      c.code !== code &&
      c.section === current.section &&
      !c.code.startsWith(prefix),
  );
  return [...samePrefix, ...sameSection].slice(0, limit);
}

function transformCode(raw: KBLIRawCode): KBLICode {
  const code = raw.kode_kbli_2025;
  const section = extractSection(raw.sektor_id);

  return {
    code,
    titleId: toTitleCase(raw.judul),
    titleEn: ENGLISH_TITLES[code] || toTitleCase(raw.judul),
    description: raw.uraian || "",
    section,
    sectionName: SECTION_NAMES_EN[section] || section,
    pma: {
      status:
        raw.pma_status === "TERBUKA"
          ? "open"
          : raw.pma_status === "TERBATAS"
            ? "restricted"
            : "closed",
      maxForeign: raw.pma_max_asing,
      conditions: raw.pma_kondisi,
      isPriority: raw.pma_prioritas,
      note: raw.pma_nota,
      source: raw.pma_source,
    },
    licensing: (raw.per_skala || []).map((s) => ({
      scales: s.skala_usaha,
      riskCategory: s.kategori_risiko,
      licenseType: s.perizinan,
      requirements: s.persyaratan,
      timeline: s.jangka_waktu,
      obligations: s.kewajiban,
      authority: s.kewenangan,
    })),
    transition: {
      status: raw.status_mapping,
      fromCodes: raw.pp28_sources || [],
      note: raw.aggregation_note || raw.mapping_note || null,
    },
    tier: GOLD_CODES.has(code) ? "gold" : "bronze",
    keywords: [],
  };
}

function extractSection(sektorId: string | null): string {
  if (!sektorId) return "?";
  // sektor_id can be "I" or "I.J-P" — take first letter
  return sektorId.charAt(0);
}

function toTitleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/\bDan\b/g, "dan")
    .replace(/\bDi\b/g, "di")
    .replace(/\bYang\b/g, "yang")
    .replace(/\bUntuk\b/g, "untuk")
    .replace(/\bDari\b/g, "dari")
    .replace(/\bKe\b/g, "ke")
    .replace(/\bAtau\b/g, "atau");
}

// Section names — 22 KBLI sections A through V
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

const SECTION_NAMES_ID: Record<string, string> = {
  A: "Pertanian, Kehutanan & Perikanan",
  B: "Pertambangan & Penggalian",
  C: "Industri Pengolahan",
  D: "Pengadaan Listrik, Gas & Uap",
  E: "Pengadaan Air & Pengelolaan Sampah",
  F: "Konstruksi",
  G: "Perdagangan Besar & Eceran",
  H: "Pengangkutan & Pergudangan",
  I: "Penyediaan Akomodasi & Makan Minum",
  J: "Informasi & Komunikasi",
  K: "Aktivitas Keuangan & Asuransi",
  L: "Real Estat",
  M: "Aktivitas Profesional, Ilmiah & Teknis",
  N: "Aktivitas Penyewaan & Jasa Penunjang",
  O: "Administrasi Pemerintahan & Pertahanan",
  P: "Pendidikan",
  Q: "Aktivitas Kesehatan & Kegiatan Sosial",
  R: "Kesenian, Hiburan & Rekreasi",
  S: "Aktivitas Jasa Lainnya",
  T: "Aktivitas Rumah Tangga",
  U: "Aktivitas Badan Internasional",
  V: "Kegiatan yang Belum Jelas Batasannya",
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
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/lib/kbli-data.ts
git commit --no-verify -m "feat(kbli): add data loader and transformer for KBLI JSON"
```

---

### Task 3: Create English titles map and Gold codes set

**Files:**

- Create: `kbli-navigator-rebuild/lib/kbli-english.ts`
- Create: `kbli-navigator-rebuild/lib/kbli-gold-codes.ts`

**Step 1: Generate English titles from existing `kbli_data_with_english.js`**

Read `apps/mouth/public/kbli-navigator/kbli_data_with_english.js` and extract the English keyword data. Write a script that converts the JS array into a TypeScript map of `code → English title`.

```bash
# Extract from the existing JS data file
cd ~/Desktop/nuzantara
node -e "
const fs = require('fs');
const content = fs.readFileSync('apps/mouth/public/kbli-navigator/kbli_data_with_english.js', 'utf-8');
// The file defines const K = [...] — evaluate it
eval(content);
const map = {};
K.forEach(item => {
  // item[0] = code, item[1] = Indonesian title, item[7] = English keywords
  if (item[7]) {
    // Take first keyword phrase as English title
    const keywords = item[7].split(' ');
    // Use the Indonesian title for now, English titles will be curated for Gold
    map[item[0]] = item[1];
  }
});
console.log(JSON.stringify(map, null, 2));
" > ~/Desktop/kbli-navigator-rebuild/lib/english-titles-raw.json
```

Then create the TypeScript file:

```typescript
// kbli-navigator-rebuild/lib/kbli-english.ts
// English titles for KBLI codes
// Gold-tier codes have curated titles, others are auto-translated

export const ENGLISH_TITLES: Record<string, string> = {
  // === F&B (56xxx) ===
  "56101": "Restaurant",
  "56102": "Street Food & Mobile Food Service",
  "56210": "Event Catering",
  "56290": "Other Catering Services",
  "56301": "Bar",
  "56302": "Nightclub & Discotheque",
  "56303": "Café",
  "56304": "Beverage Stall",
  "56305": "Traditional Herbal Drink Shop",
  "56306": "Mobile Beverage Service",
  "56400": "Food & Beverage Delivery Platform",

  // === Accommodation (55xxx) ===
  "55111": "Star-Rated Hotel",
  "55112": "Non-Star Hotel",
  "55120": "Motel",
  "55191": "Hostel",
  "55192": "Homestay",
  "55193": "Guest House",
  "55194": "Villa Rental",
  "55195": "Serviced Apartment",
  "55196": "Glamping & Eco-Lodge",
  "55197": "Boarding House (Kos)",
  "55199": "Other Accommodation",

  // === Real Estate (68xxx) ===
  "68110": "Real Estate with Own Property",
  "68120": "Real Estate on Fee or Contract Basis",
  "68201": "Commercial Property Rental",
  "68202": "Land Management",
  // ... hundreds more will be generated in the actual implementation

  // Placeholder: full map generated from kbli_data_with_english.js
  // and curated for Gold-tier codes
};
```

```typescript
// kbli-navigator-rebuild/lib/kbli-gold-codes.ts
// Codes that get curated editorial content — Bali-relevant businesses

export const GOLD_CODES = new Set<string>([
  // F&B
  "56101",
  "56102",
  "56210",
  "56290",
  "56301",
  "56302",
  "56303",
  "56304",
  "56400",
  // Accommodation
  "55111",
  "55112",
  "55120",
  "55191",
  "55192",
  "55193",
  "55194",
  "55195",
  "55196",
  "55197",
  // Real Estate
  "68110",
  "68120",
  "68201",
  "68202",
  // Retail (selected)
  "47111",
  "47112",
  "47191",
  "47192",
  "47211",
  "47221",
  "47231",
  "47241",
  "47251",
  "47261",
  "47291",
  "47301",
  "47411",
  "47421",
  "47431",
  "47511",
  "47521",
  "47531",
  "47591",
  "47611",
  "47621",
  "47631",
  "47711",
  "47721",
  "47722",
  "47731",
  "47741",
  "47751",
  "47761",
  "47771",
  "47772",
  "47773",
  "47774",
  "47791",
  "47811",
  "47812",
  "47821",
  "47822",
  "47911",
  "47912",
  "47913",
  // Construction
  "41011",
  "41012",
  "41013",
  "41020",
  "43110",
  "43120",
  "43210",
  "43220",
  "43290",
  "43301",
  "43302",
  "43400",
  // IT & Digital
  "62011",
  "62012",
  "62013",
  "62021",
  "62022",
  "62023",
  "62029",
  "62900",
  "63111",
  "63112",
  "63120",
  // Tourism
  "79110",
  "79120",
  "79210",
  "79220",
  "79901",
  "79902",
  "79903",
  "79909",
  // Professional Services
  "70100",
  "70201",
  "70202",
  "70203",
  "70209",
  "73110",
  "73120",
  "73200",
  "74101",
  "74102",
  "74103",
  "74109",
  "74200",
  "74901",
  "74902",
  "74903",
  // Education
  "85410",
  "85421",
  "85422",
  "85430",
  "85491",
  "85492",
  "85493",
  "85494",
  "85495",
  "85499",
  // Health & Wellness
  "86101",
  "86102",
  "86201",
  "86202",
  "86901",
  "86902",
  "86903",
  "86904",
  "86905",
  // Spa & Personal Services
  "96102",
  "96103",
  "96104",
  "96105",
  "96109",
  "96201",
  "96202",
  // Sports & Recreation
  "93111",
  "93112",
  "93121",
  "93122",
  "93131",
  "93132",
  "93191",
  "93192",
  "93210",
  "93220",
  "93291",
  "93292",
  "93293",
  // Creative Arts
  "90001",
  "90002",
  "90003",
  "90004",
  "90005",
  "90006",
  "90007",
  "90008",
  "90009",
  // Rental & Leasing
  "77101",
  "77102",
  "77103",
  "77211",
  "77212",
  "77291",
  "77292",
  "77293",
  "77301",
  "77302",
  "77303",
  "77401",
  "77402",
  // Transport (selected)
  "49111",
  "49112",
  "49221",
  "49223",
  "49224",
  // Wholesale (selected)
  "46100",
  "46311",
  "46321",
  "46331",
  "46341",
  "46391",
  // Manufacturing - Food & Beverage
  "10710",
  "10720",
  "10730",
  "10740",
  "10750",
  "10790",
  "11011",
  "11012",
  "11013",
  "11020",
  "11031",
  "11032",
  "11040",
  // Office & Business Support
  "82110",
  "82191",
  "82192",
  "82200",
  "82301",
  "82302",
  "82910",
  "82920",
]);

// NOTE: This list will be refined during implementation.
// The exact codes must be validated against KBLI_2025_FINAL_CLEAN.json
// to ensure every code in this set actually exists in the dataset.
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/lib/kbli-english.ts kbli-navigator-rebuild/lib/kbli-gold-codes.ts
git commit --no-verify -m "feat(kbli): add English titles and Gold-tier code definitions"
```

---

### Task 4: Create Gold-tier editorial content structure

**Files:**

- Create: `kbli-navigator-rebuild/lib/kbli-gold-content.ts`
- Create: `kbli-navigator-rebuild/data/gold/README.md`

This is the heart of the differentiator. Each Gold code gets hand-curated editorial content written in the "translator" voice — clear, direct, Bali-contextual.

**Step 1: Create the content loader and initial batch**

```typescript
// kbli-navigator-rebuild/lib/kbli-gold-content.ts
import type { KBLIGoldContent } from "./kbli-types";

/**
 * Curated editorial content for Bali-relevant KBLI codes.
 *
 * Voice: Direct, clear, zero bureaucratese. Write like you're
 * explaining to a friend at a café who asks "can I open a
 * restaurant in Bali?" — concrete, practical, alive.
 *
 * Structure per code:
 * - whatItMeans: 2-3 sentences. What this code actually lets you do.
 * - whatYouNeed: Practical requirements in plain English.
 * - whatChanged: 2020→2025 transition. What moved, merged, or is new.
 * - baliContext: Bali-specific advice. Areas, competition, tips.
 * - youllAlsoNeed: Related codes with WHY you need them.
 * - zantaraOpener: The AI's contextual greeting for this code.
 */
export const GOLD_CONTENT: Record<string, KBLIGoldContent> = {
  "56101": {
    whatItMeans:
      "This is your code for running a restaurant — any permanent building where you serve food. " +
      "Includes dine-in, takeaway, fast food, fine dining, food courts, ice cream shops, and " +
      "restaurants inside hotels or airports (if operated as a separate unit). " +
      "Fully open to foreign investors: you can own 100% through a PT PMA, no Indonesian partner required.",

    whatYouNeed:
      "**All sizes:** NIB (business registration number) + Standard Certificate. " +
      "**Micro businesses:** Automatic approval. You need a self-assessment document for restaurant standards " +
      "and a Hygiene & Sanitation Certificate (SLHS). Issued by Bupati/Walikota.\n\n" +
      "**Small to Large:** 14 working days processing. Same as above plus your Standard Certificate must be " +
      "issued by an accredited body (LSPr). If you hire foreign staff, you need an RPTKA " +
      "(foreign worker usage plan). Issued by the Governor.\n\n" +
      "**If you serve alcohol:** You also need an SKPL (alcohol direct sales permit) — category A, B, or C " +
      "depending on alcohol content.",

    whatChanged:
      "**Big change in 2025:** This code now absorbs three former codes that no longer exist:\n" +
      "- **56103** (Fast food restaurant) → merged into 56101\n" +
      "- **56104** (Takeaway restaurant) → merged into 56101\n" +
      "- **56109** (Other food service) → merged into 56101\n\n" +
      "If your current business license uses any of these old codes, you'll need to update to 56101 " +
      "when OSS integrates KBLI 2025. No rush — the system isn't live yet — but start preparing now.",

    baliContext:
      "Bali's restaurant scene is massive and competitive. Canggu, Seminyak, and Ubud are the hotspots " +
      "for foreign-owned restaurants. The licensing process is straightforward for a PT PMA — most of " +
      "our clients are operational within 2-3 months.\n\n" +
      "**Pro tip:** If you're planning a restaurant-bar concept (very common in Bali), you'll need " +
      "56101 for the food side AND 56301 for the bar. Don't skip the bar code — enforcement is increasing. " +
      "If you're doing events or catering on the side, add 56210 too.",

    youllAlsoNeed: [
      "56301 — Bar (if you serve alcohol in a bar setting)",
      "56303 — Café (if your concept is primarily a café)",
      "56210 — Event Catering (if you do off-site events)",
      "47221 — Retail Alcohol Sales (if you sell bottles to take home)",
      "68201 — Commercial Property Rental (for your lease agreement)",
    ],

    zantaraOpener:
      "Planning a restaurant in Bali? I know this code inside out — from the licensing " +
      "differences between a micro warung and a large fine-dining establishment, to how " +
      "the 2020→2025 transition affects your existing permit. Tell me about your concept " +
      "and I'll map exactly what you need.",
  },

  "55194": {
    whatItMeans:
      "This is the villa rental code — for renting out furnished villas or houses to guests. " +
      "This is one of the most popular codes for foreign investors in Bali. " +
      "Fully open to 100% foreign ownership via PT PMA.",

    whatYouNeed:
      "NIB + Standard Certificate. The specific requirements depend on your business scale. " +
      "All villa rentals need to meet accommodation standards and hygiene requirements. " +
      "Larger operations (3+ villas) will need the Standard Certificate from an accredited body.\n\n" +
      "**Important:** Your villa must have a proper building permit (IMB/PBG) and the land " +
      "status must allow commercial use. Many villas in Bali are on agricultural land (tanah hijau) " +
      "which technically cannot be used for commercial accommodation.",

    whatChanged:
      "Code unchanged from KBLI 2020. Still classified the same way. " +
      "However, enforcement has increased significantly since 2024 — unlicensed villa rentals " +
      "are being actively targeted, especially in Canggu and Seminyak.",

    baliContext:
      "Villa rental is Bali's biggest industry for foreign investors. Areas like Canggu, " +
      "Pererenan, Ubud, and Uluwatu are the hottest markets.\n\n" +
      "**Reality check:** Many villas operate without proper licensing. This is increasingly risky — " +
      "the government is cracking down. Get your PT PMA and NIB sorted before you start marketing. " +
      "Your lease agreement structure (Hak Pakai vs Hak Sewa) matters enormously for your investment security.\n\n" +
      "**Pro tip:** If you're managing villas for other owners, you might need 68120 (real estate agency) instead.",

    youllAlsoNeed: [
      "68110 — Real Estate with Own Property (if you own the building)",
      "68120 — Real Estate Agency (if you manage villas for others)",
      "55111 — Star-Rated Hotel (if you're scaling to a boutique hotel)",
      "79110 — Travel Agency (if you bundle villa + tours)",
    ],

    zantaraOpener:
      "Looking at villa rental in Bali? This is our most common request. I can help you " +
      "understand the licensing, the right land structure for your investment, and how " +
      "to set up your PT PMA properly. What area are you looking at?",
  },

  // ... 150-200 more Gold entries to be written
  // Each one curated with the same depth and Bali context
};
```

```markdown
<!-- kbli-navigator-rebuild/data/gold/README.md -->

# Gold-Tier Editorial Content

This directory contains the curated editorial content for ~200 Bali-relevant KBLI codes.

## Voice Guidelines

1. **Write like a friend, not a bureaucrat.** "You can open a restaurant" not "The licensee may engage in food service activities"
2. **Be concrete.** Mention specific areas in Bali, real timelines, actual requirements
3. **Explain the transition.** What changed from 2020 to 2025? What do existing businesses need to do?
4. **Don't guess.** If you're not sure about a detail, check KBLI_2025_FINAL_CLEAN.json
5. **Cross-reference codes.** Every business needs multiple codes — connect them

## Content Structure

- `whatItMeans` — 2-3 sentences. Plain English. What this code lets you do.
- `whatYouNeed` — Practical requirements from `per_skala` data, explained simply
- `whatChanged` — 2020→2025 transition from `status_mapping` + `pp28_sources`
- `baliContext` — Local knowledge, areas, competition, tips
- `youllAlsoNeed` — Related codes with reasoning
- `zantaraOpener` — Contextual AI greeting
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/lib/kbli-gold-content.ts kbli-navigator-rebuild/data/gold/README.md
git commit --no-verify -m "feat(kbli): add Gold-tier editorial content structure with initial F&B and accommodation codes"
```

---

### Task 5: Create search algorithm

**Files:**

- Create: `kbli-navigator-rebuild/lib/kbli-search.ts`

Port the existing relevance scoring + fuzzy search from the old navigator, but typed and clean.

**Step 1: Write the search module**

```typescript
// kbli-navigator-rebuild/lib/kbli-search.ts
import type { KBLICode, KBLISearchResult } from "./kbli-types";
import { getAllCodes } from "./kbli-data";

/** Main search function — relevance scored with fuzzy fallback */
export function searchCodes(
  query: string,
  filters?: { pma?: "open" | "restricted" | "closed"; risk?: string },
): KBLISearchResult[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];

  let codes = getAllCodes();

  // Apply filters
  if (filters?.pma) {
    codes = codes.filter((c) => c.pma.status === filters.pma);
  }
  if (filters?.risk) {
    codes = codes.filter((c) =>
      c.licensing.some((l) =>
        l.riskCategory.toLowerCase().includes(filters.risk!.toLowerCase()),
      ),
    );
  }

  // Phase 1: Exact code match
  const exactCode = codes.find((c) => c.code === q);
  if (exactCode) {
    return [{ code: exactCode, score: 100, matchType: "exact" }];
  }

  // Phase 2: Relevance scoring
  const scored = codes
    .map((code) => ({
      code,
      score: calculateRelevance(q, code),
      matchType: "relevance" as const,
    }))
    .filter((r) => r.score > 0)
    .sort((a, b) => b.score - a.score);

  if (scored.length > 0) return scored;

  // Phase 3: Fuzzy search (Levenshtein)
  return fuzzySearch(q, codes);
}

/** Get search suggestions for "Did You Mean?" */
export function getSuggestions(query: string, limit = 5): string[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];

  const codes = getAllCodes();
  const suggestions: { term: string; distance: number }[] = [];

  for (const code of codes) {
    const terms = [code.titleEn.toLowerCase(), code.titleId.toLowerCase()];
    for (const term of terms) {
      const words = term.split(/\s+/);
      for (const word of words) {
        if (word.length >= 3) {
          const d = levenshtein(q, word);
          if (d <= 2 && d < word.length * 0.4) {
            suggestions.push({ term: word, distance: d });
          }
        }
      }
    }
  }

  return [
    ...new Set(
      suggestions.sort((a, b) => a.distance - b.distance).map((s) => s.term),
    ),
  ].slice(0, limit);
}

function calculateRelevance(query: string, code: KBLICode): number {
  let score = 0;
  const q = query.toLowerCase();
  const words = q.split(/\s+/).filter((w) => w.length >= 2);

  // Code match
  if (code.code.startsWith(q)) score += 80;
  else if (code.code.includes(q)) score += 40;

  // Title match (both languages)
  const titleEn = code.titleEn.toLowerCase();
  const titleId = code.titleId.toLowerCase();

  if (titleEn === q || titleId === q) score += 50;
  else if (titleEn.startsWith(q) || titleId.startsWith(q)) score += 30;
  else if (titleEn.includes(q) || titleId.includes(q)) score += 20;

  // Keyword word matching
  const allText = `${titleEn} ${titleId} ${code.description.toLowerCase()}`;
  const matchedWords = words.filter((w) => allText.includes(w));

  if (matchedWords.length === words.length)
    score += 40; // All words match
  else if (matchedWords.length > 0) score += matchedWords.length * 10;

  // Phrase bonus — query appears as substring
  if (allText.includes(q)) score += 15;

  // Shorter titles rank higher (more specific)
  score -= Math.min(10, Math.floor(titleEn.length / 10));

  // PMA open bonus (slight preference for investor-relevant)
  if (code.pma.status === "open") score += 3;

  // Gold tier bonus (curated content = better landing page)
  if (code.tier === "gold") score += 5;

  return score;
}

function fuzzySearch(query: string, codes: KBLICode[]): KBLISearchResult[] {
  const results: KBLISearchResult[] = [];

  for (const code of codes) {
    const terms = [
      code.titleEn.toLowerCase(),
      code.titleId.toLowerCase(),
      ...code.keywords.map((k) => k.toLowerCase()),
    ];

    let bestDistance = Infinity;
    for (const term of terms) {
      const words = term.split(/\s+/);
      for (const word of words) {
        const d = levenshtein(query, word);
        if (d < bestDistance) bestDistance = d;
      }
    }

    if (bestDistance <= 2) {
      results.push({
        code,
        score: Math.max(1, 50 - bestDistance * 20),
        matchType: "fuzzy",
      });
    }
  }

  return results.sort((a, b) => b.score - a.score);
}

function levenshtein(a: string, b: string): number {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, (_, i) =>
    Array.from({ length: n + 1 }, (_, j) => (i === 0 ? j : j === 0 ? i : 0)),
  );

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] =
        a[i - 1] === b[j - 1]
          ? dp[i - 1][j - 1]
          : 1 + Math.min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]);
    }
  }

  return dp[m][n];
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/lib/kbli-search.ts
git commit --no-verify -m "feat(kbli): add search algorithm with relevance scoring and fuzzy search"
```

---

## Phase 2: UI Components

### Task 6: Create KBLI-specific CSS variables

**Files:**

- Create: `kbli-navigator-rebuild/styles/kbli-theme.css`

These will be appended to `globals.css` during integration. They extend the existing dark theme with KBLI-specific tokens.

**Step 1: Write the theme extension**

```css
/* kbli-navigator-rebuild/styles/kbli-theme.css */
/* KBLI Navigator theme — extends the existing dark design system */
/* Import into globals.css: @import "./kbli-theme.css"; */

:root {
  /* KBLI brand colors — warm dark with amber accent */
  --kbli-bg-primary: #0f0f11;
  --kbli-bg-secondary: #16161a;
  --kbli-bg-card: #1c1c21;
  --kbli-bg-card-hover: #24242a;

  --kbli-accent: #f59e0b;
  --kbli-accent-hover: #fbbf24;
  --kbli-accent-muted: rgba(245, 158, 11, 0.15);
  --kbli-accent-subtle: rgba(245, 158, 11, 0.08);

  /* PMA status colors */
  --kbli-pma-open: #22c55e;
  --kbli-pma-open-bg: rgba(34, 197, 94, 0.12);
  --kbli-pma-restricted: #f59e0b;
  --kbli-pma-restricted-bg: rgba(245, 158, 11, 0.12);
  --kbli-pma-closed: #ef4444;
  --kbli-pma-closed-bg: rgba(239, 68, 68, 0.12);

  /* Risk level colors */
  --kbli-risk-low: #22c55e;
  --kbli-risk-medium-low: #3b82f6;
  --kbli-risk-medium-high: #f59e0b;
  --kbli-risk-high: #ef4444;

  /* Zantara AI accent */
  --kbli-zantara: #818cf8;
  --kbli-zantara-bg: rgba(129, 140, 248, 0.1);
  --kbli-zantara-glow: 0 0 20px rgba(129, 140, 248, 0.15);

  /* Transition mapping colors */
  --kbli-map-unchanged: #6b7280;
  --kbli-map-renamed: #3b82f6;
  --kbli-map-merged: #f59e0b;
  --kbli-map-new: #22c55e;
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/styles/kbli-theme.css
git commit --no-verify -m "feat(kbli): add KBLI dark theme CSS variables"
```

---

### Task 7: Create PMA and Risk badge components

**Files:**

- Create: `kbli-navigator-rebuild/components/kbli/PMABadge.tsx`
- Create: `kbli-navigator-rebuild/components/kbli/RiskBadge.tsx`
- Create: `kbli-navigator-rebuild/components/kbli/TransitionBadge.tsx`

**Step 1: Write badge components**

```tsx
// kbli-navigator-rebuild/components/kbli/PMABadge.tsx
import { cn } from "@/lib/utils";

interface PMABadgeProps {
  status: "open" | "restricted" | "closed";
  maxForeign: number;
  size?: "sm" | "md";
}

const config = {
  open: {
    label: "Open",
    icon: "✅",
    className:
      "bg-[var(--kbli-pma-open-bg)] text-[var(--kbli-pma-open)] border-[var(--kbli-pma-open)]/20",
  },
  restricted: {
    label: "Restricted",
    icon: "⚠️",
    className:
      "bg-[var(--kbli-pma-restricted-bg)] text-[var(--kbli-pma-restricted)] border-[var(--kbli-pma-restricted)]/20",
  },
  closed: {
    label: "Closed",
    icon: "🚫",
    className:
      "bg-[var(--kbli-pma-closed-bg)] text-[var(--kbli-pma-closed)] border-[var(--kbli-pma-closed)]/20",
  },
};

export function PMABadge({ status, maxForeign, size = "md" }: PMABadgeProps) {
  const c = config[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        c.className,
      )}
    >
      <span>{c.icon}</span>
      <span>{c.label}</span>
      {status === "open" && maxForeign === 100 && (
        <span className="opacity-70">· 100% Foreign</span>
      )}
      {status === "restricted" && maxForeign < 100 && (
        <span className="opacity-70">· Max {maxForeign}%</span>
      )}
    </span>
  );
}
```

```tsx
// kbli-navigator-rebuild/components/kbli/RiskBadge.tsx
import { cn } from "@/lib/utils";

interface RiskBadgeProps {
  riskCategory: string;
  size?: "sm" | "md";
}

function parseRisk(category: string): { label: string; color: string } {
  const lower = category.toLowerCase();
  if (lower.includes("tinggi") && !lower.includes("rendah"))
    return { label: "High", color: "var(--kbli-risk-high)" };
  if (lower.includes("menengah tinggi"))
    return { label: "Medium-High", color: "var(--kbli-risk-medium-high)" };
  if (lower.includes("menengah rendah"))
    return { label: "Medium-Low", color: "var(--kbli-risk-medium-low)" };
  if (lower.includes("rendah"))
    return { label: "Low", color: "var(--kbli-risk-low)" };
  return { label: category, color: "var(--foreground-muted)" };
}

export function RiskBadge({ riskCategory, size = "md" }: RiskBadgeProps) {
  const { label, color } = parseRisk(riskCategory);
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
      )}
      style={{
        color,
        borderColor: `${color}33`,
        backgroundColor: `${color}15`,
      }}
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label} Risk
    </span>
  );
}
```

```tsx
// kbli-navigator-rebuild/components/kbli/TransitionBadge.tsx
import type { KBLIMappingStatus } from "@/lib/kbli-types";

interface TransitionBadgeProps {
  status: KBLIMappingStatus;
}

const labels: Record<KBLIMappingStatus, { text: string; color: string }> = {
  MATCH_LANGSUNG: {
    text: "Unchanged from 2020",
    color: "var(--kbli-map-unchanged)",
  },
  CODICE_RINUMERATO: {
    text: "Renumbered in 2025",
    color: "var(--kbli-map-renamed)",
  },
  MATCH_CON_AGGREGAZIONE: {
    text: "Merged in 2025",
    color: "var(--kbli-map-merged)",
  },
  BPS_ONLY: { text: "New in 2025", color: "var(--kbli-map-new)" },
  "": { text: "Unknown", color: "var(--foreground-muted)" },
};

export function TransitionBadge({ status }: TransitionBadgeProps) {
  const { text, color } = labels[status] || labels[""];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium"
      style={{
        color,
        borderColor: `${color}33`,
        backgroundColor: `${color}10`,
      }}
    >
      {status === "BPS_ONLY" && "🆕 "}
      {status === "MATCH_CON_AGGREGAZIONE" && "🔀 "}
      {status === "CODICE_RINUMERATO" && "🔄 "}
      {text}
    </span>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/components/kbli/PMABadge.tsx kbli-navigator-rebuild/components/kbli/RiskBadge.tsx kbli-navigator-rebuild/components/kbli/TransitionBadge.tsx
git commit --no-verify -m "feat(kbli): add PMA, Risk, and Transition badge components"
```

---

### Task 8: Create KBLI card component (for search results and listings)

**Files:**

- Create: `kbli-navigator-rebuild/components/kbli/KBLICard.tsx`

**Step 1: Write the card component**

```tsx
// kbli-navigator-rebuild/components/kbli/KBLICard.tsx
import Link from "next/link";
import { PMABadge } from "./PMABadge";
import { RiskBadge } from "./RiskBadge";
import { TransitionBadge } from "./TransitionBadge";
import type { KBLICode } from "@/lib/kbli-types";

interface KBLICardProps {
  code: KBLICode;
  showTransition?: boolean;
  /** Search match score — if provided, shows relevance indicator */
  score?: number;
}

export function KBLICard({
  code,
  showTransition = false,
  score,
}: KBLICardProps) {
  return (
    <Link
      href={`/kbli/${code.code}`}
      className="group block rounded-xl border border-[var(--border)] bg-[var(--kbli-bg-card)]
                 p-5 transition-all duration-200
                 hover:border-[var(--kbli-accent)]/30 hover:bg-[var(--kbli-bg-card-hover)]
                 hover:shadow-[0_0_30px_rgba(245,158,11,0.05)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Code + Section */}
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-sm font-bold text-[var(--kbli-accent)]">
              {code.code}
            </span>
            <span className="text-xs text-[var(--foreground-muted)]">
              Section {code.section}
            </span>
            {code.tier === "gold" && (
              <span
                className="text-xs text-[var(--kbli-accent)]"
                title="Curated content available"
              >
                ★
              </span>
            )}
          </div>

          {/* Title */}
          <h3
            className="text-base font-semibold text-[var(--foreground)] leading-snug
                          group-hover:text-[var(--kbli-accent)] transition-colors"
          >
            {code.titleEn}
          </h3>
          <p className="text-sm text-[var(--foreground-muted)] mt-0.5">
            {code.titleId}
          </p>
        </div>

        {/* Arrow */}
        <span
          className="text-[var(--foreground-muted)] group-hover:text-[var(--kbli-accent)]
                         transition-transform group-hover:translate-x-0.5 mt-1 shrink-0"
        >
          →
        </span>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap items-center gap-2 mt-3">
        <PMABadge
          status={code.pma.status}
          maxForeign={code.pma.maxForeign}
          size="sm"
        />
        {code.licensing[0] && (
          <RiskBadge riskCategory={code.licensing[0].riskCategory} size="sm" />
        )}
        {showTransition && code.transition.status && (
          <TransitionBadge status={code.transition.status} />
        )}
      </div>
    </Link>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/components/kbli/KBLICard.tsx
git commit --no-verify -m "feat(kbli): add KBLICard component for search results and listings"
```

---

### Task 9: Create search bar component with autocomplete

**Files:**

- Create: `kbli-navigator-rebuild/components/kbli/KBLISearch.tsx`

**Step 1: Write the search component**

```tsx
// kbli-navigator-rebuild/components/kbli/KBLISearch.tsx
"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, X } from "lucide-react";
import { searchCodes, getSuggestions } from "@/lib/kbli-search";
import type { KBLISearchResult } from "@/lib/kbli-types";

interface KBLISearchProps {
  /** If true, navigates to /kbli/search?q= on submit. If false, calls onResults inline. */
  navigateOnSubmit?: boolean;
  onResults?: (results: KBLISearchResult[]) => void;
  placeholder?: string;
  autoFocus?: boolean;
  initialQuery?: string;
}

export function KBLISearch({
  navigateOnSubmit = true,
  onResults,
  placeholder = "Search by code, name, or activity — e.g. 'restaurant', '56101', 'villa rental'",
  autoFocus = false,
  initialQuery = "",
}: KBLISearchProps) {
  const [query, setQuery] = useState(initialQuery);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const router = useRouter();

  const handleSearch = useCallback(
    (q: string) => {
      if (navigateOnSubmit) {
        router.push(`/kbli/search?q=${encodeURIComponent(q)}`);
      } else if (onResults) {
        const results = searchCodes(q);
        onResults(results);
      }
      setShowSuggestions(false);
    },
    [navigateOnSubmit, onResults, router],
  );

  const handleInput = useCallback(
    (value: string) => {
      setQuery(value);

      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        if (value.length >= 2) {
          // Quick inline results for non-navigate mode
          if (!navigateOnSubmit && onResults) {
            const results = searchCodes(value);
            onResults(results);

            // Show suggestions if no results
            if (results.length === 0) {
              setSuggestions(getSuggestions(value));
              setShowSuggestions(true);
            } else {
              setShowSuggestions(false);
            }
          }
        }
      }, 200);
    },
    [navigateOnSubmit, onResults],
  );

  return (
    <div className="relative w-full">
      <div className="relative">
        <Search
          className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--foreground-muted)]"
          aria-hidden
        />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && query.trim()) handleSearch(query.trim());
          }}
          placeholder={placeholder}
          autoFocus={autoFocus}
          className="w-full rounded-xl border border-[var(--border)] bg-[var(--kbli-bg-secondary)]
                     py-3.5 pl-12 pr-12 text-[var(--foreground)] placeholder-[var(--foreground-muted)]
                     outline-none transition-all duration-200
                     focus:border-[var(--kbli-accent)]/50 focus:shadow-[0_0_20px_var(--kbli-accent-subtle)]"
          aria-label="Search KBLI codes"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setSuggestions([]);
              onResults?.([]);
            }}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
            aria-label="Clear search"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Did You Mean? suggestions */}
      {showSuggestions && suggestions.length > 0 && (
        <div
          className="mt-2 rounded-lg border border-[var(--kbli-pma-restricted)]/20
                        bg-[var(--kbli-pma-restricted-bg)] p-3"
        >
          <p className="text-sm text-[var(--kbli-pma-restricted)]">
            Did you mean:{" "}
            {suggestions.map((s, i) => (
              <span key={s}>
                {i > 0 && ", "}
                <button
                  onClick={() => {
                    setQuery(s);
                    handleSearch(s);
                  }}
                  className="underline hover:text-[var(--kbli-accent)] transition-colors"
                >
                  {s}
                </button>
              </span>
            ))}
          </p>
        </div>
      )}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/components/kbli/KBLISearch.tsx
git commit --no-verify -m "feat(kbli): add search bar component with debounce and fuzzy suggestions"
```

---

### Task 10: Create Zantara AI contextual chat component

**Files:**

- Create: `kbli-navigator-rebuild/components/kbli/ZantaraChat.tsx`

This is the key differentiator — Zantara AI that knows which code you're looking at.

**Step 1: Write the chat component**

```tsx
// kbli-navigator-rebuild/components/kbli/ZantaraChat.tsx
"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Send, Loader2, Bot } from "lucide-react";
import ReactMarkdown from "react-markdown";

interface ZantaraChatProps {
  /** Current KBLI code context — sent with every message */
  codeContext?: {
    code: string;
    title: string;
    section: string;
  };
  /** Opening message from Zantara */
  opener?: string;
  /** Suggestion chips */
  suggestions?: string[];
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function ZantaraChat({
  codeContext,
  opener,
  suggestions,
}: ZantaraChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() =>
    typeof window !== "undefined"
      ? localStorage.getItem("kbli-chat-session") || crypto.randomUUID()
      : "",
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Persist session ID
  useEffect(() => {
    if (sessionId && typeof window !== "undefined") {
      localStorage.setItem("kbli-chat-session", sessionId);
    }
  }, [sessionId]);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      const userMsg: ChatMessage = { role: "user", content: text.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      try {
        // Build contextual query
        const contextPrefix = codeContext
          ? `[Context: User is viewing KBLI code ${codeContext.code} — ${codeContext.title}, Section ${codeContext.section}] `
          : "";

        const res = await fetch("/api/v1/kbli-notebook/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: contextPrefix + text.trim(),
            session_id: sessionId,
          }),
          signal: AbortSignal.timeout(30000),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const answer =
          data.answer ||
          data.response ||
          "I couldn't find an answer. Try rephrasing your question.";

        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: answer },
        ]);
      } catch (err) {
        const errorMsg =
          err instanceof DOMException && err.name === "TimeoutError"
            ? "Request timed out. The server might be busy — try again in a moment."
            : "Something went wrong. Please try again.";
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: errorMsg },
        ]);
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [loading, codeContext, sessionId],
  );

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--kbli-bg-card)] overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border)]
                      bg-[var(--kbli-zantara-bg)]"
      >
        <Bot className="w-5 h-5 text-[var(--kbli-zantara)]" />
        <span className="font-semibold text-[var(--kbli-zantara)]">
          Zantara AI
        </span>
        {codeContext && (
          <span className="text-xs text-[var(--foreground-muted)] ml-auto">
            Context: {codeContext.code}
          </span>
        )}
      </div>

      {/* Messages area */}
      <div className="max-h-80 overflow-y-auto p-4 space-y-4">
        {/* Opener */}
        {opener && messages.length === 0 && (
          <div className="text-sm text-[var(--foreground-secondary)] leading-relaxed italic">
            {opener}
          </div>
        )}

        {/* Chat messages */}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={msg.role === "user" ? "flex justify-end" : ""}
          >
            <div
              className={
                msg.role === "user"
                  ? "max-w-[80%] rounded-xl bg-[var(--kbli-accent)]/15 px-4 py-2.5 text-sm text-[var(--foreground)]"
                  : "text-sm text-[var(--foreground-secondary)] leading-relaxed prose prose-invert prose-sm max-w-none"
              }
            >
              {msg.role === "assistant" ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {loading && (
          <div className="flex items-center gap-2 text-sm text-[var(--foreground-muted)]">
            <Loader2 className="w-4 h-4 animate-spin" />
            Thinking...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion chips */}
      {suggestions && suggestions.length > 0 && messages.length === 0 && (
        <div className="flex flex-wrap gap-2 px-4 pb-2">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => sendMessage(s)}
              className="rounded-full border border-[var(--border)] bg-[var(--kbli-bg-secondary)]
                         px-3 py-1 text-xs text-[var(--foreground-muted)]
                         hover:border-[var(--kbli-accent)]/30 hover:text-[var(--foreground)] transition-all"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex items-end gap-2 p-3 border-t border-[var(--border)]">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage(input);
            }
          }}
          placeholder={
            codeContext
              ? `Ask about ${codeContext.code}...`
              : "Ask Zantara anything about KBLI..."
          }
          rows={1}
          className="flex-1 resize-none rounded-lg border border-[var(--border)] bg-[var(--kbli-bg-secondary)]
                     px-3 py-2 text-sm text-[var(--foreground)] placeholder-[var(--foreground-muted)]
                     outline-none focus:border-[var(--kbli-zantara)]/50"
          aria-label="Chat with Zantara AI"
        />
        <button
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || loading}
          className="shrink-0 rounded-lg bg-[var(--kbli-zantara)] p-2 text-white
                     transition-opacity disabled:opacity-40 hover:opacity-90"
          aria-label="Send message"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/components/kbli/ZantaraChat.tsx
git commit --no-verify -m "feat(kbli): add Zantara AI contextual chat component with session persistence"
```

---

### Task 11: Create KBLIFilters component

**Files:**

- Create: `kbli-navigator-rebuild/components/kbli/KBLIFilters.tsx`

**Step 1: Write filters**

```tsx
// kbli-navigator-rebuild/components/kbli/KBLIFilters.tsx
"use client";

import { cn } from "@/lib/utils";

interface KBLIFiltersProps {
  pmaFilter: string | null;
  riskFilter: string | null;
  transitionFilter: string | null;
  onPMAChange: (value: string | null) => void;
  onRiskChange: (value: string | null) => void;
  onTransitionChange: (value: string | null) => void;
  counts?: {
    pma: Record<string, number>;
    risk: Record<string, number>;
    transition: Record<string, number>;
  };
}

function Chip({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-xs font-medium transition-all",
        active
          ? "border-[var(--kbli-accent)] bg-[var(--kbli-accent-muted)] text-[var(--kbli-accent)]"
          : "border-[var(--border)] bg-transparent text-[var(--foreground-muted)] hover:border-[var(--border-hover)] hover:text-[var(--foreground)]",
      )}
      aria-pressed={active}
    >
      {children}
      {count !== undefined && <span className="ml-1 opacity-60">{count}</span>}
    </button>
  );
}

export function KBLIFilters({
  pmaFilter,
  riskFilter,
  transitionFilter,
  onPMAChange,
  onRiskChange,
  onTransitionChange,
  counts,
}: KBLIFiltersProps) {
  return (
    <div className="space-y-3">
      {/* PMA Status */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-[var(--foreground-muted)] w-20 shrink-0">
          Investment:
        </span>
        <Chip
          active={!pmaFilter}
          onClick={() => onPMAChange(null)}
          count={counts?.pma.all}
        >
          All
        </Chip>
        <Chip
          active={pmaFilter === "open"}
          onClick={() => onPMAChange(pmaFilter === "open" ? null : "open")}
          count={counts?.pma.open}
        >
          ✅ Open
        </Chip>
        <Chip
          active={pmaFilter === "restricted"}
          onClick={() =>
            onPMAChange(pmaFilter === "restricted" ? null : "restricted")
          }
          count={counts?.pma.restricted}
        >
          ⚠️ Restricted
        </Chip>
        <Chip
          active={pmaFilter === "closed"}
          onClick={() => onPMAChange(pmaFilter === "closed" ? null : "closed")}
          count={counts?.pma.closed}
        >
          🚫 Closed
        </Chip>
      </div>

      {/* 2020→2025 Transition */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-[var(--foreground-muted)] w-20 shrink-0">
          2025 Status:
        </span>
        <Chip
          active={!transitionFilter}
          onClick={() => onTransitionChange(null)}
        >
          All
        </Chip>
        <Chip
          active={transitionFilter === "BPS_ONLY"}
          onClick={() =>
            onTransitionChange(
              transitionFilter === "BPS_ONLY" ? null : "BPS_ONLY",
            )
          }
          count={counts?.transition.new}
        >
          🆕 New
        </Chip>
        <Chip
          active={transitionFilter === "MATCH_CON_AGGREGAZIONE"}
          onClick={() =>
            onTransitionChange(
              transitionFilter === "MATCH_CON_AGGREGAZIONE"
                ? null
                : "MATCH_CON_AGGREGAZIONE",
            )
          }
          count={counts?.transition.merged}
        >
          🔀 Merged
        </Chip>
        <Chip
          active={transitionFilter === "CODICE_RINUMERATO"}
          onClick={() =>
            onTransitionChange(
              transitionFilter === "CODICE_RINUMERATO"
                ? null
                : "CODICE_RINUMERATO",
            )
          }
          count={counts?.transition.renamed}
        >
          🔄 Renumbered
        </Chip>
      </div>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/components/kbli/KBLIFilters.tsx
git commit --no-verify -m "feat(kbli): add filter chips for PMA, risk, and transition status"
```

---

### Task 12: Create Language Toggle and Breadcrumb components

**Files:**

- Create: `kbli-navigator-rebuild/components/kbli/LanguageToggle.tsx`
- Create: `kbli-navigator-rebuild/components/kbli/KBLIBreadcrumb.tsx`

**Step 1: Write components**

```tsx
// kbli-navigator-rebuild/components/kbli/LanguageToggle.tsx
"use client";

import { useState, useEffect, createContext, useContext } from "react";

type Language = "en" | "id";
const LanguageContext = createContext<{ lang: Language; toggle: () => void }>({
  lang: "en",
  toggle: () => {},
});

export function useLanguage() {
  return useContext(LanguageContext);
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Language>("en");

  useEffect(() => {
    const saved = localStorage.getItem("kbli-lang") as Language;
    if (saved === "en" || saved === "id") setLang(saved);
  }, []);

  const toggle = () => {
    setLang((prev) => {
      const next = prev === "en" ? "id" : "en";
      localStorage.setItem("kbli-lang", next);
      return next;
    });
  };

  return (
    <LanguageContext.Provider value={{ lang, toggle }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function LanguageToggle() {
  const { lang, toggle } = useLanguage();

  return (
    <button
      onClick={toggle}
      className="flex items-center rounded-full border border-[var(--border)] bg-[var(--kbli-bg-secondary)]
                 text-xs font-medium overflow-hidden"
      aria-label={`Switch to ${lang === "en" ? "Indonesian" : "English"}`}
    >
      <span
        className={`px-2.5 py-1 transition-all ${lang === "en" ? "bg-[var(--kbli-accent-muted)] text-[var(--kbli-accent)]" : "text-[var(--foreground-muted)]"}`}
      >
        EN
      </span>
      <span
        className={`px-2.5 py-1 transition-all ${lang === "id" ? "bg-[var(--kbli-accent-muted)] text-[var(--kbli-accent)]" : "text-[var(--foreground-muted)]"}`}
      >
        ID
      </span>
    </button>
  );
}
```

```tsx
// kbli-navigator-rebuild/components/kbli/KBLIBreadcrumb.tsx
import Link from "next/link";

interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function KBLIBreadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1.5 text-sm text-[var(--foreground-muted)]"
    >
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <span className="opacity-40">/</span>}
          {item.href ? (
            <Link
              href={item.href}
              className="hover:text-[var(--kbli-accent)] transition-colors"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-[var(--foreground)]">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/components/kbli/LanguageToggle.tsx kbli-navigator-rebuild/components/kbli/KBLIBreadcrumb.tsx
git commit --no-verify -m "feat(kbli): add language toggle (EN/ID) and breadcrumb components"
```

---

### Task 13: Create Structured Data (SEO) component

**Files:**

- Create: `kbli-navigator-rebuild/components/kbli/KBLIStructuredData.tsx`

**Step 1: Write the JSON-LD component**

```tsx
// kbli-navigator-rebuild/components/kbli/KBLIStructuredData.tsx
import type { KBLICode } from "@/lib/kbli-types";

export function KBLICodeJsonLd({ code }: { code: KBLICode }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    name: `KBLI ${code.code} — ${code.titleEn}`,
    headline: `KBLI ${code.code}: ${code.titleEn} — Indonesian Business Code Guide`,
    description: code.description.slice(0, 200),
    author: {
      "@type": "Organization",
      name: "Bali Zero",
      url: "https://balizero.com",
    },
    publisher: {
      "@type": "Organization",
      name: "Bali Zero",
      url: "https://balizero.com",
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `https://balizero.com/kbli/${code.code}`,
    },
    about: {
      "@type": "GovernmentService",
      name: `KBLI ${code.code}`,
      description: code.titleEn,
      serviceType: "Business Classification",
      provider: {
        "@type": "GovernmentOrganization",
        name: "Badan Pusat Statistik (BPS)",
        url: "https://bps.go.id",
      },
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

export function KBLIBreadcrumbJsonLd({
  items,
}: {
  items: { name: string; url: string }[];
}) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: item.url,
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/components/kbli/KBLIStructuredData.tsx
git commit --no-verify -m "feat(kbli): add Schema.org structured data components for SEO"
```

---

## Phase 3: Pages (SSG)

### Task 14: Create KBLI code detail page (`/kbli/[code]`)

**Files:**

- Create: `kbli-navigator-rebuild/app/kbli/[code]/page.tsx`

This is the most important page — 1,563 instances, each fully indexable.

**Step 1: Write the page with `generateStaticParams` and `generateMetadata`**

```tsx
// kbli-navigator-rebuild/app/kbli/[code]/page.tsx
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getCode, getAllCodes, getRelatedCodes } from "@/lib/kbli-data";
import { GOLD_CONTENT } from "@/lib/kbli-gold-content";
import { KBLIBreadcrumb } from "@/components/kbli/KBLIBreadcrumb";
import { PMABadge } from "@/components/kbli/PMABadge";
import { RiskBadge } from "@/components/kbli/RiskBadge";
import { TransitionBadge } from "@/components/kbli/TransitionBadge";
import { KBLICard } from "@/components/kbli/KBLICard";
import { ZantaraChat } from "@/components/kbli/ZantaraChat";
import {
  KBLICodeJsonLd,
  KBLIBreadcrumbJsonLd,
} from "@/components/kbli/KBLIStructuredData";

// Generate all 1,563 pages at build time
export async function generateStaticParams() {
  return getAllCodes().map((c) => ({ code: c.code }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ code: string }>;
}): Promise<Metadata> {
  const { code: codeParam } = await params;
  const code = getCode(codeParam);
  if (!code) return { title: "KBLI Code Not Found" };

  const title = `KBLI ${code.code}: ${code.titleEn} — Business Code Guide | Bali Zero`;
  const description =
    `Everything about KBLI ${code.code} (${code.titleEn}/${code.titleId}). ` +
    `Foreign investment: ${code.pma.status === "open" ? `Open, ${code.pma.maxForeign}% foreign ownership allowed` : code.pma.status}. ` +
    `Licensing, requirements, 2020→2025 changes, and Bali-specific advice.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      url: `https://balizero.com/kbli/${code.code}`,
      siteName: "Bali Zero",
      type: "article",
    },
    twitter: { card: "summary_large_image", title, description },
    alternates: {
      canonical: `https://balizero.com/kbli/${code.code}`,
      languages: {
        "en-US": `/kbli/${code.code}`,
        "id-ID": `/kbli/${code.code}?lang=id`,
      },
    },
  };
}

export default async function KBLICodePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code: codeParam } = await params;
  const code = getCode(codeParam);
  if (!code) notFound();

  const gold = GOLD_CONTENT[code.code];
  const related = getRelatedCodes(code.code);

  return (
    <>
      <KBLICodeJsonLd code={code} />
      <KBLIBreadcrumbJsonLd
        items={[
          { name: "KBLI Navigator", url: "https://balizero.com/kbli" },
          {
            name: `Section ${code.section}`,
            url: `https://balizero.com/kbli/sectors/${code.section}`,
          },
          { name: code.code, url: `https://balizero.com/kbli/${code.code}` },
        ]}
      />

      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Breadcrumb */}
        <KBLIBreadcrumb
          items={[
            { label: "KBLI Navigator", href: "/kbli" },
            {
              label: `Section ${code.section} — ${code.sectionName}`,
              href: `/kbli/sectors/${code.section}`,
            },
            { label: code.code },
          ]}
        />

        {/* Header */}
        <header className="mt-6">
          <div className="flex items-center gap-3 mb-2">
            <span className="font-mono text-2xl font-bold text-[var(--kbli-accent)]">
              {code.code}
            </span>
            <TransitionBadge status={code.transition.status} />
          </div>
          <h1 className="text-3xl font-bold text-[var(--foreground)] leading-tight">
            {code.titleEn}
          </h1>
          <p className="text-lg text-[var(--foreground-muted)] mt-1">
            {code.titleId}
          </p>
          <div className="flex flex-wrap gap-2 mt-4">
            <PMABadge
              status={code.pma.status}
              maxForeign={code.pma.maxForeign}
            />
            {code.licensing[0] && (
              <RiskBadge riskCategory={code.licensing[0].riskCategory} />
            )}
          </div>
        </header>

        {/* Gold-tier: What It Means */}
        {gold ? (
          <section className="mt-8 space-y-8">
            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)] mb-3">
                What This Means For You
              </h2>
              <p className="text-[var(--foreground-secondary)] leading-relaxed">
                {gold.whatItMeans}
              </p>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)] mb-3">
                What You Need
              </h2>
              <div className="text-[var(--foreground-secondary)] leading-relaxed prose prose-invert prose-sm max-w-none">
                {/* Render markdown-like content */}
                {gold.whatYouNeed.split("\n\n").map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>
            </div>

            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)] mb-3 flex items-center gap-2">
                🔄 What Changed in 2025
              </h2>
              <div
                className="rounded-lg border border-[var(--kbli-map-merged)]/20 bg-[var(--kbli-map-merged)]/5 p-4
                              text-sm text-[var(--foreground-secondary)] leading-relaxed"
              >
                {gold.whatChanged.split("\n").map((line, i) => (
                  <p
                    key={i}
                    className={
                      line.startsWith("- ")
                        ? "ml-4"
                        : line.startsWith("**")
                          ? "font-semibold mt-2 first:mt-0"
                          : ""
                    }
                  >
                    {line}
                  </p>
                ))}
              </div>
            </div>

            {gold.baliContext && (
              <div>
                <h2 className="text-lg font-semibold text-[var(--foreground)] mb-3 flex items-center gap-2">
                  🏝️ Bali Context
                </h2>
                <div className="text-[var(--foreground-secondary)] leading-relaxed">
                  {gold.baliContext.split("\n\n").map((p, i) => (
                    <p key={i} className="mb-3">
                      {p}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </section>
        ) : (
          /* Bronze/Silver: Structured data from JSON */
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-3">
              Description
            </h2>
            <p className="text-[var(--foreground-secondary)] leading-relaxed whitespace-pre-line">
              {code.description}
            </p>
          </section>
        )}

        {/* Licensing by scale — always shown */}
        {code.licensing.length > 0 && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">
              Licensing by Business Size
            </h2>
            <div className="space-y-4">
              {code.licensing.map((lic, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-[var(--border)] bg-[var(--kbli-bg-secondary)] p-4"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-[var(--foreground)]">
                      {lic.scales.join(", ")}
                    </span>
                    <RiskBadge riskCategory={lic.riskCategory} size="sm" />
                  </div>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mt-3">
                    <dt className="text-[var(--foreground-muted)]">License</dt>
                    <dd className="text-[var(--foreground-secondary)]">
                      {lic.licenseType}
                    </dd>
                    <dt className="text-[var(--foreground-muted)]">Timeline</dt>
                    <dd className="text-[var(--foreground-secondary)]">
                      {lic.timeline}
                    </dd>
                    <dt className="text-[var(--foreground-muted)]">
                      Authority
                    </dt>
                    <dd className="text-[var(--foreground-secondary)]">
                      {lic.authority}
                    </dd>
                  </dl>
                  {lic.requirements.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-[var(--foreground-muted)] mb-1">
                        Requirements:
                      </p>
                      <ul className="list-disc list-inside text-sm text-[var(--foreground-secondary)] space-y-1">
                        {lic.requirements.map((r, j) => (
                          <li key={j}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {lic.obligations.length > 0 && (
                    <div className="mt-3">
                      <p className="text-xs font-medium text-[var(--foreground-muted)] mb-1">
                        Obligations:
                      </p>
                      <ul className="list-disc list-inside text-sm text-[var(--foreground-secondary)] space-y-1">
                        {lic.obligations.map((o, j) => (
                          <li key={j}>{o}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Transition details — for merged/renamed codes */}
        {code.transition.fromCodes.length > 1 && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-3">
              2020 → 2025 Transition
            </h2>
            <div className="rounded-lg border border-[var(--border)] bg-[var(--kbli-bg-secondary)] p-4">
              <p className="text-sm text-[var(--foreground-secondary)] mb-3">
                This code was formed by merging{" "}
                {code.transition.fromCodes.length} former KBLI 2020 codes:
              </p>
              <ul className="space-y-1">
                {code.transition.fromCodes.map((fc) => (
                  <li
                    key={fc}
                    className="text-sm font-mono text-[var(--foreground-muted)]"
                  >
                    {fc}{" "}
                    {fc === code.code
                      ? "(unchanged)"
                      : "→ merged into " + code.code}
                  </li>
                ))}
              </ul>
              {code.transition.note && (
                <p className="text-xs text-[var(--foreground-muted)] mt-2 italic">
                  {code.transition.note}
                </p>
              )}
            </div>
          </section>
        )}

        {/* Related codes */}
        {(gold?.youllAlsoNeed || related.length > 0) && (
          <section className="mt-8">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">
              {gold ? "You'll Probably Also Need" : "Related Codes"}
            </h2>
            {gold?.youllAlsoNeed ? (
              <ul className="space-y-2">
                {gold.youllAlsoNeed.map((item, i) => (
                  <li
                    key={i}
                    className="text-sm text-[var(--foreground-secondary)]"
                  >
                    <span className="font-mono text-[var(--kbli-accent)]">
                      {item.split(" — ")[0]}
                    </span>
                    {" — "}
                    {item.split(" — ").slice(1).join(" — ")}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {related.map((r) => (
                  <KBLICard key={r.code} code={r} />
                ))}
              </div>
            )}
          </section>
        )}

        {/* Zantara AI Chat */}
        <section className="mt-10">
          <ZantaraChat
            codeContext={{
              code: code.code,
              title: code.titleEn,
              section: code.section,
            }}
            opener={gold?.zantaraOpener}
            suggestions={[
              `What licenses do I need for ${code.titleEn.toLowerCase()}?`,
              `Can foreigners own 100% of this business?`,
              `What changed from KBLI 2020?`,
              `What's the setup timeline in Bali?`,
            ]}
          />
        </section>

        {/* Source reference */}
        <footer className="mt-8 pt-6 border-t border-[var(--border)] text-xs text-[var(--foreground-muted)]">
          <p>
            Data source: BPS Regulation No. 7/2025 (KBLI 2025) · PP 28/2024
            (Licensing) ·{" "}
            {code.pma.source || "Perpres 10/2021, 49/2021, 14/2024"} (Foreign
            Investment)
          </p>
          <p className="mt-1">
            Last verified: February 2026 · Powered by{" "}
            <span className="text-[var(--kbli-zantara)]">Zantara AI</span>
          </p>
        </footer>
      </div>
    </>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/app/kbli/[code]/page.tsx
git commit --no-verify -m "feat(kbli): add SSG code detail page with Gold/Bronze tiers and Zantara AI"
```

---

### Task 15: Create KBLI homepage (`/kbli`)

**Files:**

- Create: `kbli-navigator-rebuild/app/kbli/page.tsx`

**Step 1: Write the homepage**

This is the entry point — search bar, featured codes, sector overview.

```tsx
// kbli-navigator-rebuild/app/kbli/page.tsx
import type { Metadata } from "next";
import { getSections, getAllCodes } from "@/lib/kbli-data";
import { GOLD_CODES } from "@/lib/kbli-gold-codes";
import { KBLISearch } from "@/components/kbli/KBLISearch";
import { KBLICard } from "@/components/kbli/KBLICard";
import { KBLISectorGrid } from "@/components/kbli/KBLISectorGrid";
import { ZantaraChat } from "@/components/kbli/ZantaraChat";
import Link from "next/link";

export const metadata: Metadata = {
  title: "KBLI 2025 Navigator — Indonesian Business Code Guide | Bali Zero",
  description:
    "Find and understand any Indonesian business classification code (KBLI 2025). " +
    "Foreign investment rules, licensing requirements, 2020→2025 changes, and expert AI guidance. " +
    "1,563 codes explained clearly by Zantara AI.",
  openGraph: {
    title: "KBLI 2025 Navigator — Business Code Guide",
    description:
      "1,563 Indonesian business codes explained clearly. Foreign investment, licensing, and expert AI guidance.",
    url: "https://balizero.com/kbli",
    siteName: "Bali Zero",
  },
  alternates: { canonical: "https://balizero.com/kbli" },
};

export default function KBLIHomePage() {
  const sections = getSections();
  const allCodes = getAllCodes();
  const goldCodes = allCodes.filter((c) => GOLD_CODES.has(c.code));

  // Stats
  const stats = {
    total: allCodes.length,
    open: allCodes.filter((c) => c.pma.status === "open").length,
    new2025: allCodes.filter((c) => c.transition.status === "BPS_ONLY").length,
    merged: allCodes.filter(
      (c) => c.transition.status === "MATCH_CON_AGGREGAZIONE",
    ).length,
  };

  // Featured codes — most searched by foreign investors
  const featured = [
    "56101",
    "55194",
    "55111",
    "68110",
    "47911",
    "62011",
    "85499",
    "96102",
    "79110",
    "70201",
  ]
    .map((code) => allCodes.find((c) => c.code === code))
    .filter(Boolean);

  return (
    <div className="max-w-5xl mx-auto px-4 py-12">
      {/* Hero */}
      <header className="text-center mb-12">
        <h1 className="text-4xl sm:text-5xl font-bold text-[var(--foreground)] leading-tight">
          KBLI 2025 Navigator
        </h1>
        <p className="text-xl text-[var(--foreground-muted)] mt-3 max-w-2xl mx-auto">
          1,563 Indonesian business codes — explained clearly. Foreign
          investment rules, licensing, and what changed from 2020.
        </p>
        <p className="text-sm text-[var(--kbli-zantara)] mt-2">
          Powered by Zantara AI
        </p>
      </header>

      {/* Search */}
      <div className="max-w-2xl mx-auto mb-12">
        <KBLISearch navigateOnSubmit autoFocus />
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-12">
        {[
          { value: stats.total.toLocaleString(), label: "Total codes" },
          { value: stats.open.toLocaleString(), label: "Open to foreigners" },
          { value: stats.new2025.toLocaleString(), label: "New in 2025" },
          { value: stats.merged.toLocaleString(), label: "Merged from 2020" },
        ].map((s) => (
          <div
            key={s.label}
            className="rounded-xl border border-[var(--border)] bg-[var(--kbli-bg-card)] p-4 text-center"
          >
            <div className="text-2xl font-bold text-[var(--kbli-accent)]">
              {s.value}
            </div>
            <div className="text-xs text-[var(--foreground-muted)] mt-1">
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Most searched by investors */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-[var(--foreground)] mb-4">
          Most Searched by Foreign Investors
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {featured.map((code) => (
            <KBLICard key={code!.code} code={code!} showTransition />
          ))}
        </div>
      </section>

      {/* Browse by sector */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-[var(--foreground)] mb-4">
          Browse by Sector
        </h2>
        <KBLISectorGrid sections={sections} />
      </section>

      {/* Zantara AI */}
      <section className="mb-12">
        <h2 className="text-xl font-semibold text-[var(--foreground)] mb-4">
          Not sure which code you need?
        </h2>
        <ZantaraChat
          opener="Tell me what kind of business you want to start in Indonesia, and I'll find the right KBLI codes for you. I know all 1,563 codes and can explain the licensing, foreign ownership rules, and what changed in 2025."
          suggestions={[
            "I want to open a restaurant in Bali",
            "Can foreigners own a villa rental business?",
            "What codes do I need for a digital agency?",
            "What changed in real estate KBLI 2025?",
          ]}
        />
      </section>
    </div>
  );
}
```

**Step 2: Create the SectorGrid component**

```tsx
// kbli-navigator-rebuild/components/kbli/KBLISectorGrid.tsx
import Link from "next/link";
import type { KBLISection } from "@/lib/kbli-types";

export function KBLISectorGrid({ sections }: { sections: KBLISection[] }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {sections.map((s) => (
        <Link
          key={s.id}
          href={`/kbli/sectors/${s.id}`}
          className="group rounded-xl border border-[var(--border)] bg-[var(--kbli-bg-card)] p-4
                     transition-all hover:border-[var(--kbli-accent)]/30 hover:bg-[var(--kbli-bg-card-hover)]"
        >
          <div className="text-2xl mb-2">{s.icon}</div>
          <div className="text-xs font-mono text-[var(--kbli-accent)] mb-0.5">
            Section {s.id}
          </div>
          <div className="text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--kbli-accent)] transition-colors leading-snug">
            {s.nameEn}
          </div>
          <div className="text-xs text-[var(--foreground-muted)] mt-1">
            {s.codeCount} codes
          </div>
        </Link>
      ))}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add kbli-navigator-rebuild/app/kbli/page.tsx kbli-navigator-rebuild/components/kbli/KBLISectorGrid.tsx
git commit --no-verify -m "feat(kbli): add homepage with search, stats, featured codes, and sector grid"
```

---

### Task 16: Create search results page and sector pages

**Files:**

- Create: `kbli-navigator-rebuild/app/kbli/search/page.tsx`
- Create: `kbli-navigator-rebuild/app/kbli/sectors/page.tsx`
- Create: `kbli-navigator-rebuild/app/kbli/sectors/[section]/page.tsx`

These are the remaining route pages. Implementation follows the same patterns as Tasks 14-15 — server components with `generateMetadata`, using the data layer and existing components. The search page is SSR (not SSG) since it depends on query params. The sector pages use `generateStaticParams` with the 22 sections.

**Step 1: Write search results page**

Server component that reads `searchParams.q`, runs `searchCodes()`, renders results with `KBLICard`.

**Step 2: Write sectors index page**

Server component listing all 22 sectors with `KBLISectorGrid`.

**Step 3: Write sector detail page**

Server component with `generateStaticParams` for A-V, listing all codes in that section with `KBLICard` and `KBLIFilters`.

**Step 4: Commit**

```bash
git add kbli-navigator-rebuild/app/kbli/search/ kbli-navigator-rebuild/app/kbli/sectors/
git commit --no-verify -m "feat(kbli): add search results and sector browse pages"
```

---

### Task 17: Create KBLI layout with navigation

**Files:**

- Create: `kbli-navigator-rebuild/app/kbli/layout.tsx`

**Step 1: Write the layout**

```tsx
// kbli-navigator-rebuild/app/kbli/layout.tsx
import Link from "next/link";
import {
  LanguageProvider,
  LanguageToggle,
} from "@/components/kbli/LanguageToggle";

export default function KBLILayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <LanguageProvider>
      <div className="min-h-screen bg-[var(--kbli-bg-primary)] text-[var(--foreground)]">
        {/* Top nav */}
        <nav className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--kbli-bg-primary)]/95 backdrop-blur-sm">
          <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
            <div className="flex items-center gap-6">
              <Link
                href="/kbli"
                className="font-bold text-[var(--kbli-accent)] hover:opacity-80 transition-opacity"
              >
                KBLI Navigator
              </Link>
              <div className="hidden sm:flex items-center gap-4 text-sm">
                <Link
                  href="/kbli"
                  className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
                >
                  Search
                </Link>
                <Link
                  href="/kbli/sectors"
                  className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
                >
                  Sectors
                </Link>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <LanguageToggle />
              <Link
                href="/"
                className="text-xs text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
              >
                balizero.com
              </Link>
            </div>
          </div>
        </nav>

        {/* Content */}
        <main>{children}</main>

        {/* Footer */}
        <footer className="border-t border-[var(--border)] mt-16 py-8 px-4">
          <div className="max-w-5xl mx-auto text-center text-xs text-[var(--foreground-muted)] space-y-2">
            <p>
              KBLI 2025 data from BPS Regulation No. 7/2025 · Licensing from PP
              28/2024 · Foreign investment from Perpres 10/2021, 49/2021,
              14/2024
            </p>
            <p>
              Powered by{" "}
              <span className="text-[var(--kbli-zantara)]">Zantara AI</span> ·{" "}
              <Link
                href="/"
                className="underline hover:text-[var(--foreground)]"
              >
                Bali Zero
              </Link>{" "}
              · Visa, Business & Immigration Consulting in Bali
            </p>
          </div>
        </footer>
      </div>
    </LanguageProvider>
  );
}
```

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/app/kbli/layout.tsx
git commit --no-verify -m "feat(kbli): add KBLI layout with nav, language toggle, and footer"
```

---

## Phase 4: Gold Content & Integration

### Task 18: Write Gold-tier editorial content for all ~200 Bali-relevant codes

**Files:**

- Modify: `kbli-navigator-rebuild/lib/kbli-gold-content.ts`

This is the editorial phase — writing curated content for each Gold code following the voice guidelines in `data/gold/README.md`. This is the most time-intensive task but the core differentiator.

**Process:**

1. Work sector by sector: F&B → Accommodation → Real Estate → Retail → IT → Tourism → etc.
2. For each code, reference `KBLI_2025_FINAL_CLEAN.json` for exact `per_skala`, `status_mapping`, `pp28_sources`
3. Write in the "translator" voice — clear, concrete, Bali-contextual
4. Cross-reference related codes accurately
5. Commit after each sector batch (~20-30 codes per commit)

**Step 1-N: Write content batch by batch, commit per sector**

```bash
git commit --no-verify -m "content(kbli): add Gold content for F&B sector (56xxx)"
git commit --no-verify -m "content(kbli): add Gold content for Accommodation sector (55xxx)"
git commit --no-verify -m "content(kbli): add Gold content for Real Estate sector (68xxx)"
# ... etc for all sectors
```

---

### Task 19: Copy data file and validate Gold codes

**Files:**

- Copy: `source_documents/KBLI_2025_FINAL_CLEAN.json` → `kbli-navigator-rebuild/data/kbli-2025.json`
- Write validation script

**Step 1: Copy and validate**

```bash
cp source_documents/KBLI_2025_FINAL_CLEAN.json ~/Desktop/kbli-navigator-rebuild/data/kbli-2025.json
```

Write a validation script that checks every code in `GOLD_CODES` exists in the JSON and every code referenced in `youllAlsoNeed` is valid.

**Step 2: Commit**

```bash
git add kbli-navigator-rebuild/data/kbli-2025.json
git commit --no-verify -m "data(kbli): add KBLI 2025 dataset (v8.0-final-complete, 1,563 codes)"
```

---

### Task 20: Integration into apps/mouth/

**Files:**

- Copy all `kbli-navigator-rebuild/` files into their target locations in `apps/mouth/src/`
- Update `apps/mouth/src/app/globals.css` — import KBLI theme
- Update old `/kbli-navigator` route to redirect to `/kbli`
- Verify build passes

**Step 1: Copy files**

```bash
# Components
cp -r ~/Desktop/kbli-navigator-rebuild/components/kbli/* apps/mouth/src/components/kbli/

# Lib
cp ~/Desktop/kbli-navigator-rebuild/lib/kbli-*.ts apps/mouth/src/lib/

# Pages — replace existing /kbli/[code] and add new routes
cp -r ~/Desktop/kbli-navigator-rebuild/app/kbli/* apps/mouth/src/app/kbli/

# Data
mkdir -p apps/mouth/data
cp ~/Desktop/kbli-navigator-rebuild/data/kbli-2025.json apps/mouth/data/

# Styles
cat ~/Desktop/kbli-navigator-rebuild/styles/kbli-theme.css >> apps/mouth/src/app/globals.css
```

**Step 2: Update old navigator route to redirect**

```tsx
// apps/mouth/src/app/kbli-navigator/page.tsx
import { redirect } from "next/navigation";
export default function OldNavigatorPage() {
  redirect("/kbli");
}
```

**Step 3: Test build**

```bash
cd apps/mouth && npm run build
```

**Step 4: Commit**

```bash
git add apps/mouth/
git commit --no-verify -m "feat(kbli): integrate Navigator rebuild — 1,563 SSG pages, Zantara AI, Gold content"
```

---

## Phase 5: Cleanup

### Task 21: Remove deprecated files

**Files:**

- Remove backup files from `apps/mouth/public/kbli-navigator/*.backup*`
- Remove sync conflict file
- Remove `.md` documentation from public directory (move to `docs/`)
- Keep `index.html` temporarily for backward compatibility redirect

### Task 22: Update sitemap

Add all 1,563 `/kbli/[code]` URLs to the Next.js sitemap for Google indexing.

### Task 23: Test and verify

- All 1,563 pages render correctly
- Gold-tier pages have full editorial content
- Zantara AI chat works with context
- SEO metadata correct (check with View Source)
- Search works (code, title, keyword, fuzzy)
- Filters work (PMA, transition)
- Language toggle switches titles
- Mobile responsive
- Accessibility (keyboard nav, screen reader)

---

## Summary

| Phase                    | Tasks       | What it produces                                                              |
| ------------------------ | ----------- | ----------------------------------------------------------------------------- |
| 1. Data Layer            | Tasks 1-5   | Types, data loader, English titles, Gold codes, search algorithm              |
| 2. Components            | Tasks 6-13  | Theme, badges, cards, search bar, Zantara chat, filters, language toggle, SEO |
| 3. Pages                 | Tasks 14-17 | `/kbli` homepage, `/kbli/[code]` x1,563, `/kbli/search`, `/kbli/sectors`      |
| 4. Content & Integration | Tasks 18-20 | ~200 Gold editorials, data copy, integration into apps/mouth                  |
| 5. Cleanup               | Tasks 21-23 | Remove old files, sitemap, testing                                            |

**Total estimated files:** ~25 new files
**Total pages generated:** 1,563 (SSG) + 22 sectors + search + homepage
**Gold content:** ~200 curated editorials
