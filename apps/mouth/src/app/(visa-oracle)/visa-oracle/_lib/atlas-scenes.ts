/**
 * Visa Oracle atlas — pure scene projection for the approved production
 * presentation (ORACLE-PROD-20260927, BUILD-SPEC §2).
 *
 * Ported from the frozen prototype's `scenes.js`. Presentation only:
 * scenery never decides or implies eligibility, never gates navigation, and
 * never reads anything the reducer (`flow.ts`) does not already expose.
 *
 * Pure TS, no React, no side effects — a scene is a deterministic function
 * of (current node, facts, hovered/preview category).
 */
import type { Language, OracleNode } from "./flow";
import { CATEGORY_KEYS, type CategoryKey, type OracleFacts } from "./tree";

export const ATLAS_ASSET_BASE = "/static/visa-oracle/atlas/";

/** The 19 approved WebPs, byte-exact copies of the frozen prototype's
 * `public/assets/*.webp` (BUILD-SPEC §1). Never a PNG. */
export const ATLAS_ASSETS = [
  "retirement.webp",
  "watershed.webp",
  "work.webp",
  "business.webp",
  "confluence.webp",
  "diaspora.webp",
  "family.webp",
  "identity.webp",
  "invest.webp",
  "other.webp",
  "remote.webp",
  "second_home.webp",
  "study.webp",
  "tourism.webp",
  "indonesia.webp",
  "world.webp",
  "permit-paper.webp",
  "permit-depth.webp",
  "logo.webp",
] as const;

const CATEGORY_KEY_SET = new Set<string>(CATEGORY_KEYS);

/** Exported so components (`OracleScenery`, `AtlasRoute`, `OracleShell`)
 * can validate a loosely-typed `facts.category`/preview string without each
 * re-implementing the same set lookup. */
export function isAtlasCategoryKey(
  value: string | null | undefined,
): value is CategoryKey {
  return typeof value === "string" && CATEGORY_KEY_SET.has(value);
}

function isCategoryKey(value: string | null | undefined): value is CategoryKey {
  return isAtlasCategoryKey(value);
}

/** One branch's decorative identity: which "family" of shapes it belongs to
 * (used only for grouping/visual language, never for eligibility), the
 * glyph's SVG path `d` (verbatim from `P/src/scenes.js`'s `BRANCHES`), and
 * its landscape asset filename. */
export interface AtlasBranch {
  family: "Crossing" | "Terraces" | "Courtyards";
  glyph: string;
  asset: string;
}

export const ATLAS_BRANCHES: Record<CategoryKey, AtlasBranch> = {
  tourism: {
    family: "Crossing",
    glyph: "M8 65 Q38 5 63 49 T112 24",
    asset: "tourism.webp",
  },
  business: {
    family: "Terraces",
    glyph: "M8 69 H30 V47 H57 V25 H84 V12 H112",
    asset: "business.webp",
  },
  work: {
    family: "Terraces",
    glyph: "M8 72 L28 52 H46 V34 H67 V18 H112",
    asset: "work.webp",
  },
  invest: {
    family: "Terraces",
    glyph: "M8 66 L60 43 L112 66 M8 44 L60 21 L112 44 M8 22 L60 0 L112 22",
    asset: "invest.webp",
  },
  remote: {
    family: "Terraces",
    glyph: "M8 55 H88 Q110 55 110 28 M42 55 V74",
    asset: "remote.webp",
  },
  family: {
    family: "Courtyards",
    glyph: "M8 68 Q8 22 34 22 Q60 22 60 60 Q60 22 86 22 Q112 22 112 68",
    asset: "family.webp",
  },
  retirement: {
    family: "Courtyards",
    glyph: "M8 35 Q60 5 112 35 M8 53 H112 M25 70 H96",
    asset: "retirement.webp",
  },
  second_home: {
    family: "Courtyards",
    glyph: "M8 47 L60 15 L112 47 M25 48 V72 H95 V48",
    asset: "second_home.webp",
  },
  study: {
    family: "Crossing",
    glyph: "M15 72 V14 Q34 5 45 17 V72 M55 72 V14 Q74 5 85 17 V72 M95 72 V14",
    asset: "study.webp",
  },
  diaspora: {
    family: "Courtyards",
    glyph: "M8 65 Q45 65 60 36 Q75 7 112 7 M8 75 Q65 75 70 40 Q80 16 112 18",
    asset: "diaspora.webp",
  },
  other: {
    family: "Crossing",
    glyph: "M8 72 Q48 72 60 40 M60 40 Q72 10 110 10 M60 40 Q90 40 112 59",
    asset: "other.webp",
  },
};

/** `undefined` for an unrecognised/absent category — callers fall back to
 * the "other" glyph themselves (matches the prototype's `BRANCHES.other`
 * fallback in `Glyph`). */
export function atlasBranchFor(
  category: string | null | undefined,
): AtlasBranch | undefined {
  return isAtlasCategoryKey(category) ? ATLAS_BRANCHES[category] : undefined;
}

export type AtlasSceneId =
  | "entry"
  | "world"
  | "paper"
  | "watershed"
  | "identity"
  | "stay"
  | "confluence"
  | CategoryKey;

export type AtlasSceneLayout = "stage" | "landscape";

/** Every key ever handed to `atlasCopy`. Branch name/line keys are
 * templated over `CategoryKey` so every one of the 11 branches carries
 * both without hand-enumerating 22 literals. */
export type AtlasCopyKey =
  | "tools.route"
  | "tools.pause"
  | "tools.resume"
  | "tools.route_close"
  | "tools.route_heading"
  | "tools.explore"
  | "tools.change"
  | "tools.change_labeled"
  | "tools.empty_ledger"
  | "scene.watershed"
  | "scene.identity"
  | "scene.stay_here"
  | "scene.stay_planning"
  | "scene.review_gate"
  | "scene.confirmation"
  | "scene.verdict"
  | "scene.follow_up"
  | "hub.line"
  | "place.indonesia"
  | `branch.${CategoryKey}.name`
  | `branch.${CategoryKey}.line`;

export interface AtlasScene {
  id: AtlasSceneId;
  layout: AtlasSceneLayout;
  /** Bare filename under `ATLAS_ASSET_BASE`, e.g. "world.webp". */
  asset: string;
  labelKey: AtlasCopyKey | null;
}

/**
 * Mirrors `P/src/scenes.js`'s `projectScene` exactly (BUILD-SPEC §2).
 * Scenery never decides or implies eligibility: this function only reads
 * where the interview already is, never what it should recommend. Unknown
 * or invalid category values (a stale preview, a facts value from a build
 * this file has never heard of) fall back safely — this never throws.
 */
export function projectAtlasScene(
  node: OracleNode,
  facts: OracleFacts,
  previewCategory?: string | null,
): AtlasScene {
  if (node.kind === "framing") {
    return {
      id: "entry",
      layout: "stage",
      asset: "indonesia.webp",
      labelKey: null,
    };
  }
  if (node.kind === "confirmation") {
    return {
      id: "confluence",
      layout: "landscape",
      asset: "confluence.webp",
      labelKey: "scene.confirmation",
    };
  }
  if (node.kind === "verdict") {
    return {
      id: "confluence",
      layout: "landscape",
      asset: "confluence.webp",
      labelKey: "scene.verdict",
    };
  }

  const questionId = node.questionId;

  if (questionId === "in_indonesia") {
    return {
      id: "world",
      layout: "stage",
      asset: "world.webp",
      labelKey: null,
    };
  }
  if (questionId === "holds_stay_permit") {
    return {
      id: "paper",
      layout: "stage",
      asset: "permit-paper.webp",
      labelKey: null,
    };
  }
  if (questionId === "category") {
    const previewAsset = isCategoryKey(previewCategory)
      ? ATLAS_BRANCHES[previewCategory].asset
      : "watershed.webp";
    return {
      id: "watershed",
      layout: "landscape",
      asset: previewAsset,
      labelKey: "scene.watershed",
    };
  }
  if (questionId === "review_gate") {
    return {
      id: "confluence",
      layout: "landscape",
      asset: "confluence.webp",
      labelKey: "scene.review_gate",
    };
  }
  if (
    questionId === "nationalities" ||
    questionId === "birth_date" ||
    questionId === "guardian_consent"
  ) {
    return {
      id: "identity",
      layout: "landscape",
      asset: "identity.webp",
      labelKey: "scene.identity",
    };
  }
  if (isCategoryKey(facts.category)) {
    const category = facts.category;
    return {
      id: category,
      layout: "landscape",
      asset: ATLAS_BRANCHES[category].asset,
      labelKey: `branch.${category}.name`,
    };
  }
  return {
    id: "stay",
    layout: "landscape",
    asset: "permit-paper.webp",
    labelKey:
      facts.in_indonesia === "yes" ? "scene.stay_here" : "scene.stay_planning",
  };
}

/** Decorative island labels shown over the entry (stage) scene. Positions
 * (percent left/top) verbatim from `P/src/App.jsx`'s `islandLabels`. Text
 * is identical EN/ID except Java/Jawa. */
export const ISLAND_LABELS: Record<
  Language,
  readonly (readonly [string, number, number])[]
> = {
  en: [
    ["Sumatra", 15.7, 44.5],
    ["Kalimantan", 41.5, 49],
    ["Sulawesi", 56, 52.5],
    ["Java", 35, 66],
    ["Bali", 48.5, 66],
    ["Papua", 92, 56.5],
  ],
  id: [
    ["Sumatra", 15.7, 44.5],
    ["Kalimantan", 41.5, 49],
    ["Sulawesi", 56, 52.5],
    ["Jawa", 35, 66],
    ["Bali", 48.5, 66],
    ["Papua", 92, 56.5],
  ],
};

/** Decorative continent labels shown over the world (stage) scene.
 * Positions verbatim from `P/src/App.jsx`'s `worldLabels`. */
export const WORLD_LABELS: Record<
  Language,
  readonly (readonly [string, number, number])[]
> = {
  en: [
    ["NORTH AMERICA", 15, 44],
    ["SOUTH AMERICA", 26, 65],
    ["EUROPE", 50.5, 43],
    ["AFRICA", 49.5, 61],
    ["ASIA", 72, 47],
    ["AUSTRALIA", 86, 80],
  ],
  id: [
    ["AMERIKA UTARA", 15, 44],
    ["AMERIKA SELATAN", 26, 65],
    ["EROPA", 50.5, 43],
    ["AFRIKA", 49.5, 61],
    ["ASIA", 72, 47],
    ["AUSTRALIA", 86, 80],
  ],
};

type AtlasCopyTable = Record<AtlasCopyKey, string>;

const EN: AtlasCopyTable = {
  "tools.route": "Your route",
  "tools.pause": "Pause motion",
  "tools.resume": "Resume motion",
  "tools.route_close": "Close your route",
  "tools.route_heading": "The way you came.",
  "tools.explore": "Explore another direction",
  "tools.change": "Change",
  "tools.change_labeled": "Change: {q}",
  "tools.empty_ledger": "No answers yet.",
  "scene.watershed": "Choose your direction",
  "scene.identity": "A little about you",
  "scene.stay_here": "Here, in Indonesia",
  "scene.stay_planning": "Planning ahead",
  "scene.review_gate": "One last check",
  "scene.confirmation": "Your route",
  "scene.verdict": "Your next chapter",
  "scene.follow_up": "One more detail",
  "hub.line": "Many directions. One beginning.",
  "place.indonesia": "Indonesia",
  "branch.tourism.name": "A little further",
  "branch.tourism.line": "Across islands. Into possibility.",
  "branch.business.name": "Room for ideas",
  "branch.business.line": "Where conversations become possibilities.",
  "branch.work.name": "Build your next chapter",
  "branch.work.line": "A different horizon for your working life.",
  "branch.invest.name": "Ground to build on",
  "branch.invest.line": "An idea takes shape, one layer at a time.",
  "branch.remote.name": "Work, with a wider horizon",
  "branch.remote.line": "Connected to your work. Open to somewhere new.",
  "branch.family.name": "Closer, together",
  "branch.family.line": "Two paths. A place to meet.",
  "branch.retirement.name": "A different rhythm",
  "branch.retirement.line": "More room for the life ahead.",
  "branch.second_home.name": "A place to return to",
  "branch.second_home.line": "Your own corner of a wider world.",
  "branch.study.name": "A world to discover",
  "branch.study.line": "New perspectives begin here.",
  "branch.diaspora.name": "A thread that leads home",
  "branch.diaspora.line": "Where your story finds another connection.",
  "branch.other.name": "A path of your own",
  "branch.other.line": "Let’s find the shape of your journey.",
};

const ID: AtlasCopyTable = {
  "tools.route": "Rute Anda",
  "tools.pause": "Jeda animasi",
  "tools.resume": "Lanjutkan animasi",
  "tools.route_close": "Tutup rute Anda",
  "tools.route_heading": "Jalan yang Anda tempuh.",
  "tools.explore": "Jelajahi arah lain",
  "tools.change": "Ubah",
  "tools.change_labeled": "Ubah: {q}",
  "tools.empty_ledger": "Belum ada jawaban.",
  "scene.watershed": "Pilih arah Anda",
  "scene.identity": "Sedikit tentang Anda",
  "scene.stay_here": "Di sini, di Indonesia",
  "scene.stay_planning": "Merencanakan ke depan",
  "scene.review_gate": "Satu pemeriksaan terakhir",
  "scene.confirmation": "Rute Anda",
  "scene.verdict": "Babak Anda berikutnya",
  "scene.follow_up": "Satu detail lagi",
  "hub.line": "Banyak arah. Satu awal.",
  "place.indonesia": "Indonesia",
  "branch.tourism.name": "Sedikit lebih jauh",
  "branch.tourism.line": "Melintasi pulau. Menuju kemungkinan.",
  "branch.business.name": "Ruang untuk gagasan",
  "branch.business.line": "Tempat percakapan menjadi peluang.",
  "branch.work.name": "Bangun babak berikutnya",
  "branch.work.line": "Cakrawala baru bagi kehidupan kerja Anda.",
  "branch.invest.name": "Landasan untuk membangun",
  "branch.invest.line": "Sebuah gagasan terbentuk, lapis demi lapis.",
  "branch.remote.name": "Bekerja, dengan cakrawala lebih luas",
  "branch.remote.line":
    "Tetap terhubung dengan pekerjaan. Terbuka pada tempat baru.",
  "branch.family.name": "Lebih dekat, bersama",
  "branch.family.line": "Dua jalan. Satu tempat bertemu.",
  "branch.retirement.name": "Irama yang berbeda",
  "branch.retirement.line": "Ruang lebih lapang untuk hidup ke depan.",
  "branch.second_home.name": "Tempat untuk kembali",
  "branch.second_home.line": "Sudut Anda sendiri di dunia yang lebih luas.",
  "branch.study.name": "Dunia untuk dijelajahi",
  "branch.study.line": "Perspektif baru dimulai di sini.",
  "branch.diaspora.name": "Benang yang menuntun pulang",
  "branch.diaspora.line": "Tempat kisah Anda menemukan ikatan lain.",
  "branch.other.name": "Jalan Anda sendiri",
  "branch.other.line": "Mari temukan bentuk perjalanan Anda.",
};

export const ATLAS_COPY: Record<Language, AtlasCopyTable> = { en: EN, id: ID };

const ATLAS_VAR_RE = /\{(\w+)\}/g;

/** `translate()`'s sibling for the atlas's own copy table — deliberately
 * separate from `i18n.ts` (never touched by this build, invariant §0.1):
 * this table's keys are internal to the atlas presentation and pin nothing
 * any existing test already depends on. `{q}` interpolation only (no
 * pluralization escape hatch — nothing here needs one). Missing keys
 * return the raw key, same fail-visibly contract as `translate()`. */
export function atlasCopy(
  language: Language,
  key: AtlasCopyKey,
  vars?: Record<string, string>,
): string {
  const value = ATLAS_COPY[language][key] ?? key;
  if (!vars) return value;
  return value.replace(ATLAS_VAR_RE, (match, name: string) =>
    Object.prototype.hasOwnProperty.call(vars, name) ? vars[name] : match,
  );
}
