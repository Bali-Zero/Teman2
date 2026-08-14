import type { KBLIProvenance } from "./kbli-types";

// =============================================================================
// kbli-pma-source.ts — attribute the PMA ownership verdict to the instrument
// the RECORD actually names, not to a hardcoded default.
//
// `kbli-faq.ts`'s `pmaSourceNote` and `KBLIStructuredData.tsx`'s
// `pmaAttribution` both hardcoded "(Source: Perpres 10/2021 as amended by
// Perpres 49/2021 ...)" onto EVERY code, visible answer AND FAQPage/Article
// JSON-LD alike. That was correct for the 1,553 codes whose `pma_source`
// really is the Perpres residual-open default — and wrong for the six
// insurance/reinsurance codes this fix-pack cures to `PP 14/2018 Pasal 5(1)
// jo. PP 3/2020 (sector law — Perpres 10/2021 Pasal 11(2) carve-out)`: their
// pages attributed the 80% cap to the wrong instrument, in the visible FAQ
// answer and in the JSON-LD Google ingests. `code.pma.source` (mapped 1:1
// from canonical's `pma_source` by `kbli-data.server.ts`, compiler-gated —
// never hand-edited) already carries the right answer per code; the bug was
// that neither presenter read it.
//
// One classifier, shared by both surfaces, for the same reason
// `kbli-pma-shape.ts` exists: a rule that decides one fact belongs in ONE
// module, not reinvented per call-site.
// =============================================================================

/**
 * The FAQ-prose PMA source note, appended verbatim to the visible answer
 * (and, via the same builder, the FAQPage JSON-LD).
 *
 * - Perpres-sourced with BPS ancestry: the existing note verbatim, crosswalk
 *   caveat included.
 * - Perpres-sourced without BPS ancestry: cite the instrument and the explicit
 *   BPS gap, never claim that a crosswalk audit is in progress.
 * - Any other named source (the six sector-law-adjudicated insurance codes
 *   today; open to any future per-code primary-source adjudication): cite
 *   that source directly. If its BPS basis is untraceable, append the same
 *   explicit BPS-gap caveat already emitted by the JSON-LD surface.
 * - No recorded source at all (`null` — not observed live today, but the
 *   field is nullable): no note, rather than a fabricated one.
 */
export function pmaSourceNoteFaq(
  source: string | null,
  provenanceStatus: KBLIProvenance["pma"]["status"],
): string {
  if (provenanceStatus === "declared_gap") {
    return source
      ? ` (Instrument context recorded as ${source}, but no adjudicated per-code official basis and vintage currently verify this verdict; confirm it at oss.go.id before relying on it.)`
      : " (No adjudicated per-code official basis and vintage currently verify this verdict; confirm it at oss.go.id before relying on it.)";
  }
  if (!source) return "";
  return ` (Source: ${source}.)`;
}

/**
 * The structured-data PMA attribution clause, appended to `pmaLabel` in
 * `KBLICodeJsonLd`. Same source-aware branching as `pmaSourceNoteFaq`, worded
 * as a clause rather than a parenthetical sentence to match the surrounding
 * `pmaLabel` string it is spliced into.
 */
export function pmaSourceAttributionStructured(
  source: string | null,
  provenanceStatus: KBLIProvenance["pma"]["status"],
): string {
  if (provenanceStatus === "declared_gap") {
    return " — no adjudicated per-code official basis and vintage currently verify this verdict; confirm it at oss.go.id";
  }
  if (!source) return "";
  return ` per ${source}`;
}
