// =============================================================================
// KBLI Cover Design DNA — deterministic, editorial, zero-external-request
// =============================================================================
//
// Replaces the Unsplash hotlink hero system with a generated visual identity
// derived purely from data already on hand: the KBLI section (A-U/V) picks a
// muted, print-editorial palette + abstract motif, and the 5-digit code itself
// is turned into a unique "fingerprint" composition (bars/arcs whose geometry
// encodes the digits). Same code -> same fingerprint, always; different codes
// -> visually distinct fingerprints. No network calls, no committed rasters —
// every renderer (OG image, hero canvas) derives pixels from these pure
// functions at request/build time.

/** Abstract motif family rendered behind/around the fingerprint bars. */
export type CoverMotif =
  | "organic"
  | "grid"
  | "waves"
  | "circuit"
  | "arc"
  | "strata"
  | "scatter";

/** Palette + motif assigned to a KBLI section letter. */
export interface SectionVisual {
  /** Gradient start — deep, desaturated, dark-editorial. */
  hueA: string;
  /** Gradient end — subtly warmer/cooler counterpoint to hueA. */
  hueB: string;
  /** Accent used for the fingerprint bars/arcs and small marks. */
  accent: string;
  motif: CoverMotif;
  /** Short section label used on the cover (e.g. "MANUFACTURING"). */
  label: string;
}

// -----------------------------------------------------------------------------
// Section visuals — every KBLI section (A-U) plus the catch-all V.
// Dark backgrounds only, one muted accent per section, never neon.
// -----------------------------------------------------------------------------

export const SECTION_VISUALS: Record<string, SectionVisual> = {
  A: {
    hueA: "#0f1c14",
    hueB: "#1c2e1f",
    accent: "#5c8a5c",
    motif: "organic",
    label: "Agriculture, Forestry & Fishing",
  },
  B: {
    hueA: "#1c1610",
    hueB: "#2e2418",
    accent: "#a67c52",
    motif: "strata",
    label: "Mining & Quarrying",
  },
  C: {
    hueA: "#14161a",
    hueB: "#242a30",
    accent: "#8a9aa8",
    motif: "grid",
    label: "Manufacturing",
  },
  D: {
    hueA: "#171408",
    hueB: "#2b2410",
    accent: "#c9a227",
    motif: "circuit",
    label: "Electricity & Gas Supply",
  },
  E: {
    hueA: "#0c1a1c",
    hueB: "#152e30",
    accent: "#4f9a9e",
    motif: "waves",
    label: "Water Supply & Waste Management",
  },
  F: {
    hueA: "#1a1208",
    hueB: "#2e2110",
    accent: "#c6893e",
    motif: "arc",
    label: "Construction",
  },
  G: {
    hueA: "#1a100c",
    hueB: "#2e1c14",
    accent: "#b9633f",
    motif: "scatter",
    label: "Wholesale & Retail Trade",
  },
  H: {
    hueA: "#0c1420",
    hueB: "#152438",
    accent: "#5c86b0",
    motif: "waves",
    label: "Transportation & Storage",
  },
  I: {
    hueA: "#1c1108",
    hueB: "#2e1c0e",
    accent: "#d4845a",
    motif: "waves",
    label: "Accommodation & Food Service",
  },
  J: {
    hueA: "#120e1c",
    hueB: "#20182e",
    accent: "#7d6bb0",
    motif: "circuit",
    label: "Information & Communication",
  },
  K: {
    hueA: "#0a1614",
    hueB: "#132824",
    accent: "#3f9e8a",
    motif: "grid",
    label: "Financial & Insurance Activities",
  },
  L: {
    hueA: "#1a140c",
    hueB: "#2e2414",
    accent: "#b08a52",
    motif: "arc",
    label: "Real Estate Activities",
  },
  M: {
    hueA: "#101318",
    hueB: "#1e232c",
    accent: "#7a8ba0",
    motif: "circuit",
    label: "Professional, Scientific & Technical",
  },
  N: {
    hueA: "#141018",
    hueB: "#241d2c",
    accent: "#9a7ab0",
    motif: "grid",
    label: "Administrative & Support Services",
  },
  O: {
    hueA: "#141414",
    hueB: "#262626",
    accent: "#a8a29a",
    motif: "grid",
    label: "Public Administration & Defence",
  },
  P: {
    hueA: "#0c1420",
    hueB: "#182a3e",
    accent: "#5a8fc4",
    motif: "arc",
    label: "Education",
  },
  Q: {
    hueA: "#0c1810",
    hueB: "#152a1c",
    accent: "#5aab6e",
    motif: "waves",
    label: "Human Health & Social Work",
  },
  R: {
    hueA: "#180c16",
    hueB: "#2c1626",
    accent: "#b0608f",
    motif: "scatter",
    label: "Arts, Entertainment & Recreation",
  },
  S: {
    hueA: "#160c1a",
    hueB: "#28162e",
    accent: "#9a6bb0",
    motif: "scatter",
    label: "Other Service Activities",
  },
  T: {
    hueA: "#181410",
    hueB: "#2c2418",
    accent: "#b09a6b",
    motif: "organic",
    label: "Household Activities",
  },
  U: {
    hueA: "#0a1218",
    hueB: "#14222c",
    accent: "#6b93b0",
    motif: "circuit",
    label: "Extraterritorial Organizations",
  },
  V: {
    hueA: "#141414",
    hueB: "#242424",
    accent: "#8a8a8a",
    motif: "scatter",
    label: "Activities Not Yet Classified",
  },
};

/** Fallback visual for an unrecognized/null section — kept in the family. */
export const DEFAULT_SECTION_VISUAL: SectionVisual = {
  hueA: "#0c0c0e",
  hueB: "#1c1c1e",
  accent: "#d4845a",
  motif: "grid",
  label: "Business Classification",
};

export function getSectionVisual(section: string | null | undefined): SectionVisual {
  if (!section) return DEFAULT_SECTION_VISUAL;
  return SECTION_VISUALS[section.toUpperCase()] ?? DEFAULT_SECTION_VISUAL;
}

// -----------------------------------------------------------------------------
// Code fingerprint — deterministic abstract composition from the 5 digits
// -----------------------------------------------------------------------------

/** One bar of the fingerprint: a vertical bar (or arc segment) with position/size. */
export interface FingerprintBar {
  /** Which digit (0-4, left to right) this bar encodes. */
  digitIndex: number;
  /** The literal digit value (0-9) this bar encodes. */
  digit: number;
  /** Height as a fraction of the available height, 0.12-1.0. */
  heightFrac: number;
  /** Horizontal position as a fraction of available width, 0-1. */
  xFrac: number;
  /** Corner radius in px-equivalent units (renderer scales as needed). */
  radius: number;
  /** Rotation in degrees, small deterministic jitter derived from the hash. */
  rotationDeg: number;
}

/** Full deterministic geometry for a KBLI code — renderer-agnostic data. */
export interface CodeFingerprint {
  code: string;
  /** One bar per digit, left to right. */
  bars: FingerprintBar[];
  /** A stable 0-1 float derived from the code, for seeded micro-variation
   * (used for e.g. overall composition offset, dot-scatter positions). */
  seed: number;
  /** Small integer 0-359, deterministic rotation for motif overlays. */
  motifRotation: number;
}

/**
 * Tiny deterministic string hash (djb2 variant). Pure, stable across runs —
 * NOT for security, only for seeding visual variation.
 */
function hashString(input: string): number {
  let hash = 5381;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 33) ^ input.charCodeAt(i);
  }
  // Force unsigned 32-bit.
  return hash >>> 0;
}

/**
 * Derive a deterministic visual fingerprint from a KBLI code string.
 * Same code always yields the same geometry (pure function of `code`).
 */
export function codeFingerprint(code: string): CodeFingerprint {
  const digits = code
    .split("")
    .filter((ch) => ch >= "0" && ch <= "9")
    .map((ch) => Number(ch));

  const hash = hashString(code);
  const seed = (hash % 10000) / 10000;

  const bars: FingerprintBar[] = digits.map((digit, i) => {
    // Height: spread digit 0-9 across a legible visual range so no bar
    // collapses to invisible nor blows past the frame.
    const heightFrac = 0.12 + (digit / 9) * 0.88;
    const xFrac = digits.length > 1 ? i / (digits.length - 1) : 0.5;
    // Per-bar jitter derived from a distinct slice of the hash so adjacent
    // digits with the same value still look subtly different.
    const barHash = hashString(`${code}:${i}`);
    const radius = 2 + (barHash % 6);
    const rotationDeg = ((barHash % 700) / 100) * (i % 2 === 0 ? 1 : -1);
    return { digitIndex: i, digit, heightFrac, xFrac, radius, rotationDeg };
  });

  const motifRotation = hash % 360;

  return { code, bars, seed, motifRotation };
}

/**
 * Sample distinctness check helper: true if two fingerprints are
 * geometrically identical (used only in tests, not production code paths).
 */
export function fingerprintsEqual(a: CodeFingerprint, b: CodeFingerprint): boolean {
  if (a.bars.length !== b.bars.length) return false;
  return a.bars.every(
    (bar, i) =>
      bar.heightFrac === b.bars[i].heightFrac &&
      bar.xFrac === b.bars[i].xFrac &&
      bar.radius === b.bars[i].radius &&
      bar.rotationDeg === b.bars[i].rotationDeg,
  );
}

// -----------------------------------------------------------------------------
// Gradient helper — shared by OG route + hero canvas
// -----------------------------------------------------------------------------

export function sectionGradient(visual: SectionVisual, angleDeg = 135): string {
  return `linear-gradient(${angleDeg}deg, ${visual.hueA} 0%, ${visual.hueB} 100%)`;
}
