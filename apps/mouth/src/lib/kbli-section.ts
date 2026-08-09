// =============================================================================
// KBLI section derivation — single source of truth
// =============================================================================
//
// Extracted from kbli-data.ts (Mandate 12, 2026-08-09 — PENDING-ARMS.md,
// "sektor_id is not a malformed KBLI section" finding). Both kbli-data.ts
// (client-facing) and kbli-data.server.ts (server/sitemap) derive a code's
// KBLI/ISIC section the same way: from the 2-digit code prefix against the
// standard BPS A-U scheme — NEVER from `sektor_id`, which is a PP28/2025
// Lampiran (annex) locator, not a section, and collapses almost every code
// onto the single letter "I" if read as one (see dossier_pull.py for its
// real semantics).
//
// Same discipline as kbli-derive.ts's other pure, dependency-free helpers
// (resolvePmaCap, perpresCitation, riskDispute, perpresSlice): ONE
// implementation, imported by both readers, so they cannot diverge (W105).

/** KBLI section letter -> 2-digit code prefixes */
export const SECTION_PREFIX_MAP: Record<string, string[]> = {
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

/**
 * Derive a code's real KBLI/ISIC section letter (A-U) from its 2-digit
 * prefix. Returns null on an unmapped prefix — an honest "unknown", never a
 * silent default to any specific letter (in particular never "I", which is
 * what a `sektor_id`-derived read collapses onto almost universally).
 */
export function getSectionFromCode(code: string): string | null {
  const prefix = code.substring(0, 2);
  return PREFIX_TO_SECTION[prefix] ?? null;
}
