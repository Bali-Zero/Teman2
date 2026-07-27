/**
 * Single resolver for a KBLI record's foreign-ownership cap.
 *
 * Why this file exists: the cap was read in TWO places with DIFFERENT defaults —
 * `kbli-data.ts` used `raw.pma_max_asing` bare, while `kbli-data.server.ts`
 * used `raw.pma_max_asing || 0`. The two readers disagreed about the same
 * record, so one of them had to be lying; both were.
 *
 * On the one record that carries no cap field — `01122` "Pertanian Padi
 * Inbrida", `pma_status: TERBUKA`, i.e. fully open to foreign ownership —
 * each reader produced its own wrong answer: `undefined` from the bare read,
 * `0` from the coercion, on a code that is 100% open.
 *
 * Which reader feeds which surface was verified against the live page, not
 * assumed: `/kbli/[code]/page.tsx` imports `getCode` from `kbli-data.ts`
 * (it takes only `getGoldContent`/`getKbliDatasetLastModified` from the
 * `.server` module), so the **1,559 detail pages are on the bare read** and
 * prod rendered the self-contradicting string **"undefined% Open"**. The
 * `|| 0` reader feeds the sitemap and the `/api/kbli/gold` routes, where the
 * same record reported a flat `0`.
 *
 * (An earlier version of this comment had those two roles swapped and named
 * the symptom as "0% Open". The fix was right and covers both readers; the
 * attribution was wrong, and a wrong attribution sends the next reader
 * grepping for a string that was never on the page.)
 *
 * A rule that decides one fact belongs in ONE module, and the interaction is
 * what gets tested — not each reader in isolation.
 *
 * The fallback is status-driven and deliberately narrow: `pma_status` is
 * unambiguous only at its two extremes. TERBATAS ("limited") spans 0%, 49%,
 * 100% and a non-percentage regime, so it can never be turned into a figure —
 * inventing one is precisely the defect this resolver exists to prevent.
 */

/** Structural shape — both raw record interfaces satisfy it. */
export interface PmaCapSource {
  pma_status?: string | null;
  pma_max_asing?: number | string | null;
}

export function resolvePmaCap(
  raw: PmaCapSource | null | undefined,
): number | "special" {
  const raw_cap = raw?.pma_max_asing;

  // Note the `!== "boolean"` guard is unnecessary in TS but the JSON is
  // untyped at runtime; a boolean would otherwise arithmetic-coerce.
  if (typeof raw_cap === "number" && Number.isFinite(raw_cap)) {
    return raw_cap;
  }
  if (typeof raw_cap === "string") {
    const trimmed = raw_cap.trim();
    if (trimmed === "special") return "special";
    if (/^\d+$/.test(trimmed)) return Number(trimmed);
  }

  // No adjudicated figure on the record.
  if (raw?.pma_status === "TERBUKA") return 100;
  if (raw?.pma_status === "TERTUTUP") return 0;

  // Limited, with no percentage on the record: there is no honest number to
  // return, so we return the value that asserts none. Does not occur in the
  // current catalogue (pinned by test) — this is the guard, not a code path.
  return "special";
}
