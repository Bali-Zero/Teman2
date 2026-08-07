import fs from "fs";
import path from "path";

/**
 * Codes where the gold editorial prose and the OSS record disagree on the
 * risk tier — the `/kbli/82990` disease: the licensing panel printed
 * "High (Tinggi)" from the record while the editorial two sections up said
 * "low risk at every scale", and nothing on the page admitted they disagree.
 *
 * This module does NOT detect anything. The detection (closed tier
 * vocabulary, clause-level negation/hedge/conditional/other-code guards,
 * zero-overlap AND universal-quantifier semantics) lives in
 * `scripts/kbli_filiera/gold_risk_dispute_relation.py` with its own
 * guilt/innocence corpus, and re-implementing it here would make two writers
 * of one verdict (W105). That script emits `data/kbli-risk-disputes.json`; a
 * pytest freshness check recomputes the population and fails when the
 * artifact is stale, so a NEW contradiction cannot reach the page without
 * its disclosure riding along.
 *
 * RENDER CONTRACT: the page may state the RECORD tiers (structured data),
 * the dispute `kind`, and `baliDependsOnTier` — all structured, compiler-
 * computed. It must never enumerate the editorial side's tiers — prose
 * evidence can carry junk, and a disclosure listing wrong tiers would be a
 * new client-facing lie. The artifact's `editorial_mentions` is audit
 * evidence for humans, deliberately not exposed by this reader.
 *
 * FAIL-CLOSED (round-3 BLOCKER: a corrupt/missing artifact used to degrade
 * to `{}` silently — every code would read as "no dispute" and the page
 * would ASSERT undisputed facts about codes the compiler had flagged
 * disputed, exactly the class of lie this module exists to prevent). A
 * missing file, unparseable JSON, or a payload without a `disputes` key now
 * THROWS at first read, naming the `--emit` command that fixes it — the
 * freshness gate (fix #1 of this same round) guarantees the artifact is
 * always present and current on any branch that can reach this code, so a
 * throw here means the checkout itself is broken, not a normal empty state.
 * The per-entry filter for a dispute with no record side is UNCHANGED and
 * stays silent — that one is a documented semantic filter (an empty
 * disclosure would render nothing anyway), not a sign of corruption.
 */
export interface KBLIRiskDispute {
  /** Distinct kategori_risiko values the record's per_skala rows hold. */
  recordTiers: string[];
  /**
   * Which rule convicted this code (gold_risk_dispute_relation.py):
   * `zero_overlap` — the editorial prose's claimed tier(s) share NOTHING
   * with the record's tier set (the editorial tier is simply wrong).
   * `universal_claim` — the editorial prose claims ONE tier applies at
   * EVERY business scale; false as soon as the record holds any other tier,
   * even when the claimed tier is ALSO among the record's tiers (the
   * editorial tier is not wrong, its claimed UNIVERSALITY is). The two
   * kinds are false in different ways and MUST render different sentences
   * — round-3 finding: a frame that always says "describes a different
   * tier" is itself a lie for `universal_claim` codes.
   */
  kind: "zero_overlap" | "universal_claim";
  /**
   * true when the record's `l4_bali.status` is one of the statuses DERIVED
   * from the risk tier itself (computed by the compiler from `l4_bali`, not
   * from prose — see `bali_depends_on_tier()` in
   * gold_risk_dispute_relation.py, which derives this from the shared
   * `_l4bali_basis.RISK_DERIVED_STATUSES` SSOT). 32 of the 33 disputes carry
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

type RawDispute = {
  record?: string[];
  kind?: string;
  baliDependsOnTier?: boolean;
};

let _cache: Record<string, KBLIRiskDispute> | null = null;

function load(): Record<string, KBLIRiskDispute> {
  if (_cache) return _cache;

  let raw: string;
  try {
    raw = fs.readFileSync(DISPUTES_PATH, "utf-8");
  } catch (err) {
    throw new Error(
      `[kbli] cannot read risk-dispute artifact at ${DISPUTES_PATH} — run ` +
        `\`python3 scripts/kbli_filiera/gold_risk_dispute_relation.py --emit\` ` +
        `(${err instanceof Error ? err.message : String(err)})`,
    );
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    throw new Error(
      `[kbli] risk-dispute artifact at ${DISPUTES_PATH} is not valid JSON — ` +
        `run \`python3 scripts/kbli_filiera/gold_risk_dispute_relation.py --emit\` ` +
        `(${err instanceof Error ? err.message : String(err)})`,
    );
  }

  const disputesRaw = (parsed as { disputes?: unknown } | null)?.disputes;
  if (
    disputesRaw === undefined ||
    disputesRaw === null ||
    typeof disputesRaw !== "object" ||
    Array.isArray(disputesRaw)
  ) {
    throw new Error(
      `[kbli] risk-dispute artifact at ${DISPUTES_PATH} has no "disputes" ` +
        `object — run \`python3 scripts/kbli_filiera/gold_risk_dispute_relation.py --emit\``,
    );
  }

  const disputes = disputesRaw as Record<string, RawDispute>;
  _cache = Object.fromEntries(
    Object.entries(disputes)
      // A dispute with no record side would render an empty disclosure —
      // treat it as absent rather than inventing a sentence around nothing.
      // This is a documented semantic filter, distinct from the corruption
      // cases above: it fires only per-entry, on a well-formed artifact.
      .filter(([, d]) => Array.isArray(d.record) && d.record.length > 0)
      .map(([code, d]) => [
        code,
        {
          recordTiers: d.record as string[],
          kind:
            d.kind === "universal_claim" ? "universal_claim" : "zero_overlap",
          baliDependsOnTier: d.baliDependsOnTier === true,
        } satisfies KBLIRiskDispute,
      ]),
  );
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
