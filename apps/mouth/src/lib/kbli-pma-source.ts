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

/** The Perpres 10/2021 residual-open default and its 49/2021 amendment — the
 * only source for which the crosswalk-pending caveat is true. Matched by
 * substring rather than equality: `pma_source` embeds this instrument name
 * inside a longer string on the sector-law-carved-out codes too (e.g. "...not
 * the Perpres 10/2021/49/2021 annexes)"), and the caveat must NOT fire there —
 * `isPerpresSource` below checks a stricter prefix shape than a bare
 * substring test would, so that longer, sector-law-citing string is excluded. */
function isPerpresSource(source: string | null): boolean {
  if (!source) return false;
  // The Perpres-default string always OPENS with "Perpres 10/2021" (optionally
  // followed by ", 49/2021"). Every sector-law override observed in the
  // catalogue instead OPENS with the sector instrument's own name (e.g. "PP
  // 14/2018, PP 3/2020 ...") and only MENTIONS the Perpres later as the
  // carve-out it was routed away from — so anchoring at the start is what
  // keeps this from re-triggering on that mention.
  return /^Perpres 10\/2021\b/.test(source.trim());
}

const PERPRES_CROSSWALK_NOTE_FAQ =
  " (Source: Perpres 10/2021 as amended by Perpres 49/2021 — the investment-list annexes predate KBLI 2025; per-code crosswalk audit in progress.)";

const PERPRES_CROSSWALK_NOTE_STRUCTURED =
  " per Perpres 10/2021 as amended (crosswalk to KBLI 2025 pending)";

/**
 * The FAQ-prose PMA source note, appended verbatim to the visible answer
 * (and, via the same builder, the FAQPage JSON-LD).
 *
 * - Perpres-sourced (1,553 of 1,559 codes, unchanged behaviour): the existing
 *   note verbatim, crosswalk caveat included.
 * - Any other named source (the six sector-law-adjudicated insurance codes
 *   today; open to any future per-code primary-source adjudication): cite
 *   that source directly, with no crosswalk caveat — the caveat is specific
 *   to the Perpres annexes predating KBLI 2025, and asserting it about an
 *   unrelated instrument would be a new, unverified claim.
 * - No recorded source at all (`null` — not observed live today, but the
 *   field is nullable): no note, rather than a fabricated one.
 */
export function pmaSourceNoteFaq(source: string | null): string {
  if (!source) return "";
  if (isPerpresSource(source)) return PERPRES_CROSSWALK_NOTE_FAQ;
  return ` (Source: ${source}.)`;
}

/**
 * The structured-data PMA attribution clause, appended to `pmaLabel` in
 * `KBLICodeJsonLd`. Same source-aware branching as `pmaSourceNoteFaq`, worded
 * as a clause rather than a parenthetical sentence to match the surrounding
 * `pmaLabel` string it is spliced into.
 */
export function pmaSourceAttributionStructured(source: string | null): string {
  if (!source) return "";
  if (isPerpresSource(source)) return PERPRES_CROSSWALK_NOTE_STRUCTURED;
  return ` per ${source}`;
}
