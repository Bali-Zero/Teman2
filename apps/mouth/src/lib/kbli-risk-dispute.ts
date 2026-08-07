import fs from "fs";
import path from "path";

/**
 * Codes where the gold editorial prose and the OSS record disagree on the
 * risk tier — the `/kbli/82990` disease: the licensing panel printed
 * "High (Tinggi)" from the record while the editorial two sections up said
 * "low risk at every scale", and nothing on the page admitted they disagree.
 *
 * This module does NOT detect anything. The detection (closed tier
 * vocabulary, sentence-level negation/hedge/other-code guards, zero-overlap
 * semantics) lives in `scripts/kbli_filiera/gold_risk_dispute_relation.py`
 * with its own guilt/innocence corpus, and re-implementing it here would make
 * two writers of one verdict (W105). That script emits
 * `data/kbli-risk-disputes.json`; a pytest freshness check recomputes the
 * population and fails when the artifact is stale, so a NEW contradiction
 * cannot reach the page without its disclosure riding along.
 *
 * RENDER CONTRACT: the page may state the RECORD tiers (structured data) and
 * the FACT of divergence. It must never enumerate the editorial side's tiers
 * — prose evidence can carry junk, and a disclosure listing wrong tiers would
 * be a new client-facing lie. The artifact's `editorial_mentions` is audit
 * evidence for humans, deliberately not exposed by this reader.
 *
 * Missing or unreadable file ⇒ every code returns `null` and the page renders
 * as before — the disclosure is additive; its absence costs a reader a
 * warning, whereas a fabricated one would accuse healthy pages.
 */
export interface KBLIRiskDispute {
  /** Distinct kategori_risiko values the record's per_skala rows hold. */
  recordTiers: string[];
  /**
   * true when the record's `l4_bali.status` is one of the statuses DERIVED
   * from the risk tier itself (computed by the compiler from `l4_bali`, not
   * from prose — see `bali_depends_on_tier()` in
   * gold_risk_dispute_relation.py). 29 of the 30 zero_overlap disputes carry
   * this: a page cannot show a Bali verdict as settled fact while calling
   * the tier it is derived from disputed.
   */
  baliDependsOnTier: boolean;
}

const DISPUTES_PATH = path.join(
  process.cwd(),
  "data",
  "kbli-risk-disputes.json",
);

let _cache: Record<string, KBLIRiskDispute> | null = null;

function load(): Record<string, KBLIRiskDispute> {
  if (_cache) return _cache;
  try {
    const parsed = JSON.parse(fs.readFileSync(DISPUTES_PATH, "utf-8"));
    const disputes: Record<
      string,
      { record?: string[]; baliDependsOnTier?: boolean }
    > = parsed.disputes ?? {};
    _cache = Object.fromEntries(
      Object.entries(disputes)
        // A dispute with no record side would render an empty disclosure —
        // treat it as absent rather than inventing a sentence around nothing.
        .filter(([, d]) => Array.isArray(d.record) && d.record.length > 0)
        .map(([code, d]) => [
          code,
          {
            recordTiers: d.record as string[],
            baliDependsOnTier: d.baliDependsOnTier === true,
          },
        ]),
    );
  } catch {
    process.stderr.write(
      `[kbli] no risk-dispute artifact at ${DISPUTES_PATH} — pages render without the divergence disclosure\n`,
    );
    _cache = {};
  }
  return _cache;
}

/** The risk-tier divergence for a code, or null when the two sources agree. */
export function riskDispute(code: string): KBLIRiskDispute | null {
  return load()[code] ?? null;
}

/** Test-only: drop the module cache so a test can point at a fresh file. */
export function _resetRiskDisputeCache(): void {
  _cache = null;
}
