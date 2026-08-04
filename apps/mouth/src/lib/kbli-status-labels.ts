/**
 * Canonical enum → human-label map for the KBLI navigator.
 *
 * WHY THIS FILE EXISTS (measured 2026-07-25 on the 1,559-code canonical):
 * the editorial layer (`intel_2026.editorial`) was authored by narrating the
 * JSON record, so internal pipeline enums reached the client verbatim —
 * `Bali status: OK_or_HIGHER_RISK` on 908 "By the numbers" cells across 1,141
 * codes (73% of the catalog), plus 725 occurrences inside editorial prose.
 * `OK_or_HIGHER_RISK` is not vocabulary; it is a pipeline symbol.
 *
 * The human labels already existed — in `BaliStatusBadge` and `TransitionBadge`.
 * They were simply not reachable from the editorial renderer. This module is
 * the single source of truth both badges and the editorial renderer now share,
 * so a status can never be spelled two ways on the same page.
 *
 * BOUNDARY — this is a PRESENTATION mapping, never a fact change. The symbol
 * and its label denote exactly the same verdict; nothing is added, softened or
 * inferred. The underlying data debt (the editorial layer narrating raw fields
 * such as `l4_bali_blocked`) stays visible internally and is measured by
 * `kbli-internal-leak.test.ts`, which ratchets it down and never up.
 *
 * MATCHING DISCIPLINE (cicatrix superscar #3 — guard over-match): resolution is
 * EXACT-KEY only for structured values and WORD-BOUNDARY-anchored for prose.
 * Never a bare substring: `TERTUTUP` must not eat `TERTUTUP_CANDIDATE`, and an
 * unknown symbol must fall through verbatim rather than be guessed at.
 */

export type BaliStatusTone = "ok" | "warn" | "block";

export interface BaliStatusConfig {
  label: string;
  icon: string;
  tone: BaliStatusTone;
}

/**
 * L4 Bali status — the sovereign-local layer. National PMA openness (L2) is not
 * Bali registrability (L4). Source: schema-v2 `l4_bali` (moratorium 2026-05-13,
 * Gubernur letter B.27.000/642/PM/DPMPTSP).
 */
export const BALI_STATUS_CONFIG: Record<string, BaliStatusConfig> = {
  OK_or_HIGHER_RISK: { label: "Registrable in Bali", icon: "✅", tone: "ok" },
  // Nationally TERBUKA and the Besar scale is Menengah-Tinggi/Tinggi → survives the
  // Bali risk-class moratorium → registrable by a PT PMA in Bali (#1814 risk-tier pass).
  APERTO_BALI_RISCHIO_ALTO: {
    label: "Open in Bali (high-risk tier)",
    icon: "✅",
    tone: "ok",
  },
  BLOCCATO_CLASSE_RISCHIO: {
    label: "Blocked in Bali (risk-class moratorium)",
    icon: "🚫",
    tone: "block",
  },
  // Nationally TERBUKA but the Besar scale is Rendah/Menengah-Rendah → blocked by the
  // 2026 Bali PMA moratorium (Gov. letter B.27.000/642). Resolved by #1814 risk-tier pass.
  CHIUSO_MORATORIA_BALI: {
    label: "Closed in Bali (2026 moratorium)",
    icon: "🚫",
    tone: "block",
  },
  // Closed by a national sector regulator regardless of risk tier (e.g. Bank Indonesia,
  // BAPETEN) — structurally closed to private/PMA capital. Resolved by #1814.
  CHIUSO_REGOLATORE_SETTORIALE: {
    label: "Closed (sector regulator)",
    icon: "🚫",
    tone: "block",
  },
  // Besar-scale risk is low on some ruang lingkup but higher on others: OSS computes
  // risk per (code × scope × scale), so registrability depends on the declared scope.
  // (deep research 2026-06-20: rejection is on "tingkat risiko", not on the code.)
  BLOCCATO_DIPENDE_SCOPE: {
    label: "Conditional in Bali — depends on declared scope",
    icon: "⚠️",
    tone: "warn",
  },
  // The activity is ALLOCATED to cooperatives/MSME by name in Perpres 10/2021 as
  // amended by 49/2021, Lampiran II (the `dialokasikan` column) — a PT PMA cannot
  // take that bidang usaha.
  //
  // Corrected 2026-08-03: this comment used to derive the status from "no Usaha
  // Besar scale row in OSS", and 32 of the then-39 codes carried it on that basis
  // alone. Permeninves/BKPM 5/2025 Pasal 26(1) inverts the inference — a PT PMA is
  // Usaha Besar as a CONSEQUENCE of foreign ownership, so a missing Besar row is a
  // licensing-data gap, never an ownership bar. The status now means only what the
  // annex says, and reaches 7 codes.
  CHIUSO_PMA_NO_BESAR: {
    label: "Reserved for MSME — closed to PT PMA",
    icon: "🚫",
    tone: "block",
  },
  // No OSS-RBA risk scope at all (404): special/sectoral regime — finance (OJK/BI),
  // pharma (BPOM), and other sensitive activities licensed outside the ordinary RBA
  // flow. Not mechanically caught by the low-risk Bali block → verify case-by-case.
  NEEDS_REVIEW_NO_OSS_SCOPE: {
    label: "Special regime — verify case-by-case",
    icon: "❓",
    tone: "warn",
  },
  CHIUSO_BALI: { label: "Closed for PMA in Bali", icon: "🚫", tone: "block" },
  CHIUSO_BALI_PROPOSTO: {
    label: "Closure proposed (Bali)",
    icon: "⚠️",
    tone: "warn",
  },
  TERTUTUP: { label: "Closed to foreigners", icon: "🚫", tone: "block" },
  TERBATAS: { label: "Restricted (foreign cap)", icon: "⚠️", tone: "warn" },
  TERTUTUP_CANDIDATE: {
    label: "Likely closed — verify",
    icon: "❓",
    tone: "warn",
  },
  TERBATAS_CANDIDATE: {
    label: "Likely restricted — verify",
    icon: "❓",
    tone: "warn",
  },
  // GARUDA-FILIERA Fase-1 cure #4 (2026-07-17): the risk tier this verdict
  // depended on was carried over from a different activity through a
  // code-number collision and has been detached — the moratorium
  // applicability is genuinely unresolved, not "verify a special regime"
  // (NEEDS_REVIEW_NO_OSS_SCOPE) or a known ok/blocked verdict.
  NON_CLASSIFICABILE: {
    label: "Bali status not classifiable — verify",
    icon: "❓",
    tone: "warn",
  },
};

/** KBLI 2020 → 2025 crosswalk verdict, as labelled by `TransitionBadge`. */
export const MAPPING_STATUS_LABELS: Record<string, string> = {
  MATCH_LANGSUNG: "Direct Match",
  CODICE_RINUMERATO: "Renumbered",
  MATCH_CON_AGGREGAZIONE: "Aggregated",
  BPS_ONLY: "New in 2025",
};

/**
 * Indonesian regulatory terms of art. These are NOT internal symbols: they are
 * the words the investment annexes, OSS and every Bali Zero surface use, and the
 * product deliberately teaches them alongside their English gloss. Translating
 * them here would make the same page say "TERBUKA" in a badge and "Open" in the
 * sidebar — and would silently drop the reader's link to the official wording.
 */
const TERMS_OF_ART = new Set(["TERBUKA", "TERTUTUP", "TERBATAS"]);

/**
 * Every internal symbol that must never reach a reader, mapped to the label the
 * product already uses for it elsewhere. Terms of art are excluded by design.
 */
export const INTERNAL_ENUM_LABELS: Record<string, string> = Object.fromEntries([
  ...Object.entries(BALI_STATUS_CONFIG)
    .filter(([key]) => !TERMS_OF_ART.has(key))
    .map(([key, cfg]) => [key, cfg.label] as const),
  ...Object.entries(MAPPING_STATUS_LABELS),
]);

/**
 * Humanise a STRUCTURED value (e.g. an `editorial.byTheNumbers` cell).
 * Exact-key resolution after trimming; anything unrecognised — including a term
 * of art, a number, a free-text cell — is returned byte-identical.
 */
export function humanizeStatValue(value: string): string {
  const label = INTERNAL_ENUM_LABELS[value.trim()];
  return label ?? value;
}

// Longest-first so a longer symbol is offered before any shorter one that shares
// its prefix; the trailing boundary makes this belt-and-braces, not the guard.
const ENUM_TOKEN_RE = new RegExp(
  `(?<![A-Za-z0-9_])(${Object.keys(INTERNAL_ENUM_LABELS)
    .sort((a, b) => b.length - a.length)
    .join("|")})(?![A-Za-z0-9_])`,
  "g",
);

/**
 * Humanise internal symbols appearing inside PROSE (editorial body, standfirst,
 * pull-quote). Word-boundary anchored on both sides and `_`-aware, so
 * `TERTUTUP_CANDIDATE` resolves as itself and never as `TERTUTUP` + `_CANDIDATE`.
 * Prose that contains no known symbol is returned unchanged.
 */
export function humanizeInternalEnums(text: string): string {
  if (!text) return text;
  return text.replace(ENUM_TOKEN_RE, (match) => INTERNAL_ENUM_LABELS[match]);
}

/**
 * Keys under `intel_2026` whose strings are NOT prose shown to a reader, and so
 * must survive byte-identical. Kept as a DENY list, deliberately: an allow list
 * of prose fields silently misses the next field somebody adds — `whoThisIsFor`
 * (1,186 records, rendered on the code page) was exactly that miss, caught by
 * the adversarial review of this change. Deny-listing makes new fields covered
 * by default, and `kbli-internal-leak.test.ts` walks the block generically so a
 * field that should have been denied fails the gate instead of leaking.
 *
 *  - `_l3_regen` — regeneration provenance (model, source, fact_gate). Machine
 *    metadata: a symbol there is a record OF the pipeline, not a message to a
 *    reader, and rewriting it would falsify the audit trail.
 *  - `coverImage` — an asset path.
 */
const INTEL_NON_READER_KEYS = new Set(["_l3_regen", "coverImage"]);

/**
 * Humanise every reader-facing string inside an `intel_2026` block, at the data
 * loader, so a symbol cannot survive by reaching a surface nobody remembered to
 * wrap. Walks the WHOLE block — prose fields, `editorial`, `byTheNumbers` cells,
 * `tkaInfo`, arrays, any future nesting — skipping `INTEL_NON_READER_KEYS`.
 * Non-strings pass through untouched and the input is never mutated.
 *
 * Idempotent: a label contains no symbol, so re-applying is a no-op — the
 * component-level calls in `KBLIEditorial` remain valid defence in depth.
 */
export function humanizeIntelBlock<T>(intel: T): T {
  return humanizeDeep(intel) as T;
}

function humanizeDeep(node: unknown): unknown {
  if (typeof node === "string") return humanizeInternalEnums(node);
  if (Array.isArray(node)) return node.map(humanizeDeep);
  if (node && typeof node === "object") {
    const src = node as Record<string, unknown>;
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(src)) {
      out[key] = INTEL_NON_READER_KEYS.has(key) ? value : humanizeDeep(value);
    }
    return out;
  }
  return node;
}
