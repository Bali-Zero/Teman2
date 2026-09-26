/**
 * Second Home Studio — the claim guard's patterns, as a module.
 *
 * Moved VERBATIM out of `__tests__/forbidden-claims.test.ts` (2026-09-26) so
 * the Studio's Facts drawer can run the SAME patterns over the fact registry
 * at render time (`app/visa/second-home/studio/room/shelf-facts.ts`) instead
 * of a copy that would drift. The sweep test imports them from here; nothing
 * was added, removed or loosened in the move.
 */
/**
 * The e33_claim_guard forbidden-pattern list, verbatim from
 * SPEC-secondhome-studio-phaseB.md §6. Case-insensitive by design (the
 * spec calls this out explicitly) — every pattern below carries the `i`
 * flag.
 *
 * `splitDepositEuphemism` and `youreThere` are fix-mandate-round-1
 * additions (P0-C2 / P2-C14), not part of the original spec §6 list:
 * - P0-C2: the FIRST rewrite of `capital.why` dodged `splitDeposit` by
 *   restating the same forbidden concept in a synonym ("deposits divided
 *   across multiple accounts do not qualify") — an under-match
 *   (superscar #3's twin failure mode). This pattern catches that class
 *   directly, independent of the literal word "split".
 * - P2-C14: "and you're there" reads as an eligibility confirmation
 *   (arrival/conclusion idiom) rather than a preliminary fit-check result.
 */
export const FORBIDDEN_PATTERNS: Record<string, RegExp> = {
  priceUsd1500: /US?D?\s*\$?\s*1[,.]?500/i,
  anyBank: /any\s+(Indonesian\s+)?bank/i,
  e33SR: /E33[SR]\b/i,
  workLocallyOrInIndonesia: /work(ing)?\s+(locally|in\s+indonesia)/i,
  automaticItapOrPermanent: /automatic(ally)?\s+.*(ITAP|permanent)/i,
  fiveToTenYears: /5\s*[-–]\s*10\s*years?/i,
  idr2Million: /IDR\s*2[,.]?000[,.]?000\b/i,
  guaranteedOr100PercentApproval: /guarantee[ds]?\s+approval|100%\s+approval/i,
  lps: /\bLPS\b/i,
  bsiOrSharia: /\bBSI\b|sharia/i,
  splitDeposit: /split(ting)?\s+.*deposit/i,
  splitDepositEuphemism:
    /divided\s+across\s+multiple\s+accounts|multiple\s+accounts?\s+do(es)?\s+not\s+qualify/i,
  youreThere: /you'?re\s+there|you\s+are\s+there/i,
};

/** Generalized IDR price-literal check for the JSX source-scan (P2-C13) —
 *  broader than PRICE_LITERAL_PATTERN below (which only pins the two
 *  known historical values, 35M/39M): any IDR figure with 6+ digits
 *  hardcoded directly into a component would bypass usePricingData. */
export const JSX_PRICE_LITERAL_RE = /\bIDR\s*[0-9][0-9.,]{5,}/i;

/** No hardcoded IDR price literal anywhere — the figure renders only from
 *  usePricingData. Covers both the pre-repricing (39M) and current (35M)
 *  values so a future reprice can't silently reintroduce a stale one. */
export const PRICE_LITERAL_PATTERN =
  /35[,.]?000[,.]?000|39[,.]?000[,.]?000|\b39M\b|\b35M\b/i;
