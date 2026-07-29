// =============================================================================
// kbli-pma-shape.ts — what a foreign-ownership cap MEANS, once the extremes are
// taken seriously.
//
// `kbli-pma-cap.ts` is the single resolver for the cap's VALUE, and its header
// already states the hard part:
//
//     "pma_status is unambiguous only at its two extremes. TERBATAS ('limited')
//      spans 0%, 49%, 100% and a non-percentage regime, so it can never be
//      turned into a figure."
//
// That resolver honours it. Every PRESENTER then interpolated the value into
// `Max ${cap}%` without asking whether the figure meant anything, so a range
// the data layer knows is heterogeneous was rendered as if it were uniform.
// Measured on the live site 2026-07-29, after #3186 shipped the v3 titles:
//
//   /kbli/47221  "special" → `Max special%` ×5, one of them VISIBLE body text
//                and two inside JSON-LD ("Restricted to max special% foreign
//                ownership (TERBATAS)"). `KBLIStructuredData` never checked
//                `capSpecial` — the exact recurrence `kbli-faq.ts` already
//                records as having happened once ("the visible answer handled
//                capSpecial, the JSON-LD did not").
//   /kbli/47111  cap 0    → `Max 0%` ×9, and an FAQ answer reading "capped at
//                0% … An Indonesian partner holds the remaining shares".
//   /kbli/79110  cap 100  → `Max 100%` ×7, same trailing clause — which at 100%
//                is not awkward but FALSE, in FAQPage JSON-LD that Google
//                ingests.
//
// Three codes of 1,559. The other seven TERBATAS rows (cap 49) render exactly
// right, which is the point: the formula is correct in its middle and wrong at
// both ends. So the fix is not new phrasing sprinkled per call-site — it is one
// classifier the presenters share, for the same reason `resolvePmaCap` exists:
// a rule that decides one fact belongs in ONE module.
//
// WHAT THIS MODULE DELIBERATELY DOES NOT DO: it never reads `pma_kondisi` /
// `pma.condition`. The condition text is ungated free prose (e.g. "UMKM only");
// promoting it into a <title> or JSON-LD would be a NEW regulatory assertion on
// an indexed surface, which is precisely what `kbli-meta.ts` exists to prevent.
// The shape below is derived only from values the existing provenance gates
// already cover.
// =============================================================================

/**
 * Structural shape, mirroring `PmaCapSource` in kbli-pma-cap.ts: the presenters
 * that need this are split between ones holding a whole `KBLICode` and ones
 * handed only the `pma` sub-object, and a classifier that only half of them can
 * call is how per-call-site phrasing gets reinvented in the first place.
 */
export interface PmaShapeSource {
  maxForeign: number | "special";
  capSpecial: boolean;
  capVerified: boolean;
}

/**
 * What the cap says about foreign capital, independent of how any surface
 * chooses to word it.
 *
 * - `none`        — the ceiling is 0%: no foreign capital, whatever the status
 *                   label says. Outcome-identical to TERTUTUP for a PT PMA.
 * - `partial`     — a real ceiling strictly between 0 and 100. The percentage
 *                   IS the answer; this is the case the v3 formula was written
 *                   for (49% cabotage, and it reads perfectly).
 * - `full`        — the ceiling is 100%: whatever restricts this activity, it
 *                   is not a share of ownership. "Max 100%" restricts nothing.
 * - `conditional` — no usable figure at all: the special-distribution regime,
 *                   or any value that is not a finite number. Never render a
 *                   percentage for this.
 */
export type PmaCapShape = "none" | "partial" | "full" | "conditional";

/**
 * Classify a restricted code's cap.
 *
 * Only meaningful when `kbli.pma.status === "restricted"` — `open` and `closed`
 * carry their answer in the status itself and never reach here.
 *
 * The `typeof !== "number"` arm is load-bearing, not defensive noise. Today
 * `capSpecial` and the `"special"` cap value agree on exactly one record
 * (47221, verified across all 1,559), but they come from two INDEPENDENT raw
 * fields — `pma_cap_special` and `pma_max_asing` — so nothing structurally
 * keeps them in step. If they ever drift, this arm is what stops a literal
 * `Max special%` from reaching a public page again.
 */
export function pmaCapShape(pma: PmaShapeSource): PmaCapShape {
  if (pma.capSpecial) return "conditional";

  const cap = pma.maxForeign;
  if (typeof cap !== "number" || !Number.isFinite(cap)) return "conditional";

  if (cap <= 0) return "none";
  if (cap >= 100) return "full";
  return "partial";
}

/**
 * The compact label the visible badges show for a TERBATAS code.
 *
 * Three call-sites rendered this independently — `LicensingSection` twice and
 * the detail page once — and they had already drifted: the page qualified an
 * unverified cap as `≈N% (unverified)`, the two badges printed a bare `Max N%`
 * for the same record. This adopts the page's (more careful) behaviour for all
 * three. Live delta today is zero: no restricted code carries
 * `pma_cap_verified: false` — the only two rows that do, 02101 and 03120, are
 * TERBUKA and never reach this branch.
 */
export function restrictedCapBadge(pma: PmaShapeSource): string {
  switch (pmaCapShape(pma)) {
    case "none":
      return "Closed (0%)";
    case "full":
    case "conditional":
      return "Conditions apply";
    default:
      return pma.capVerified
        ? `Max ${pma.maxForeign}%`
        : `≈${pma.maxForeign}% (unverified)`;
  }
}
