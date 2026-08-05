// =============================================================================
// Why a Bali block is a block — derived from the verdict, never defaulted
//
// `LicensingSection` frames the national licensing steps with "in Bali this is
// blocked for a PT PMA because …". That clause used to be a BINARY: one status
// (`CHIUSO_PMA_NO_BESAR`) was special-cased and EVERY other blocking status fell
// through to "under the 13 May 2026 moratorium". Measured on the canonical of
// 2026-07-27, blocked codes carry SIX distinct statuses, and only two of them
// are the moratorium — so 72 pages asserted a cause that was not theirs.
//
// It was not a cosmetic slip. The same sentence splices `l4_bali.reason` in
// right after the clause, and on 58 of those 72 the reason ends with
// "→ not blocked by moratorium" — so the page read, verbatim on prod:
//
//   "blocked for a PT PMA under the 13 May 2026 moratorium — OSS risk at
//    scale Besar is Menengah-Tinggi/Tinggi → not blocked by moratorium."
//
// A reader is told the cause and its denial in one breath. And the direction of
// the error matters commercially: a moratorium reads as temporary, so a
// permanent statutory reservation (a notary office is reserved to Indonesian
// citizens by UU 30/2004) reads as "wait it out", while `79110` — travel agency,
// one of the most-requested PT PMA activities in Bali — was told its closure was
// in force when the record says it is only PROPOSED.
// =============================================================================

/** The blocking statuses `l4_bali.status` can carry (exhaustive, live census). */
export type BaliBlockStatus =
  | "BLOCCATO_CLASSE_RISCHIO"
  | "CHIUSO_MORATORIA_BALI"
  | "CHIUSO_PMA_NO_BESAR"
  | "TERTUTUP"
  | "CHIUSO_REGOLATORE_SETTORIALE"
  | "CHIUSO_BALI"
  | "CHIUSO_BALI_PROPOSTO";

/**
 * A closure that has been ANNOUNCED but is not yet in force.
 *
 * `blocked: true` on such a record is INTENTIONAL conservatism, the same posture
 * the rest of the L4 layer takes, and it is what the Bali badge and the JSON-LD
 * read straight from the data — so this must not be quietly downgraded here.
 * Suppressing the frame on one surface while the badge above it still says
 * blocked would manufacture exactly the self-contradiction this file exists to
 * remove. The honest fix is to keep the frame and SAY the closure is announced
 * rather than in force, which `baliBlockClause` does.
 */
export function isProposalOnly(status?: string | null): boolean {
  return status === "CHIUSO_BALI_PROPOSTO";
}

/**
 * The closure is NATIONAL, even though it is recorded in a Bali-scoped field.
 *
 * `l4_bali` is where the L4 layer records its verdict, and for some codes that
 * verdict has nothing to do with Bali: the activity is shut everywhere in
 * Indonesia. Nothing downstream could tell the two apart, because the only
 * national signals the renderer read — `pma_status` / `pma_max_asing` — are the
 * ABSENCE-from-the-annex default fill and still say `TERBUKA` / `100` on every
 * one of these records. So the banner rendered "National procedure — does not
 * apply to a PT PMA in Bali" and the FAQ published, in the FAQPage JSON-LD that
 * Google ingests, "Outside Bali it is open to a PT PMA with no local partner
 * required" — on the central bank, on radioactive-waste collection, and on seven
 * bidang usaha a presidential annex allocates to Koperasi/UMKM nationwide.
 *
 * Two statuses, and only two, are national by their own recorded reason —
 * verified one by one on the live catalogue (all 9, `confidence: HIGH`,
 * `needs_review: false`, each with a locator):
 *
 *   CHIUSO_REGOLATORE_SETTORIALE (2) — a sectoral regulator or State monopoly:
 *     `64110` Bank Sentral (Bank Indonesia), `38122` radioactive waste (BAPETEN).
 *   CHIUSO_PMA_NO_BESAR (7) — allocated to Koperasi/UMKM by Perpres 49/2021
 *     Lampiran II, "a PT PMA cannot take this bidang usaha", with page and entry.
 *
 * DELIBERATELY NOT `TERTUTUP`, and this is the whole reason the rule is a named
 * SET rather than a "closed-sounding status" test. That status is MIXED on the
 * live catalogue: `01287` reads "closed to foreign ownership at the national
 * level", but `01111` reads "closed to PMA registration IN BALI" and `11010`
 * carries a sentence that is not a closure at all. Convicting all 68 on the
 * strength of the name would be judging the FORM of the status instead of the
 * entity it records — the same move that produced the defect above. The
 * nationally-closed members of `TERTUTUP` need per-code adjudication; until then
 * they keep the Bali framing, which understates rather than misdirects.
 */
const NATIONAL_CLOSURE_STATUSES = new Set<string>([
  "CHIUSO_REGOLATORE_SETTORIALE",
  "CHIUSO_PMA_NO_BESAR",
]);

export function isNationalClosure(status?: string | null): boolean {
  return NATIONAL_CLOSURE_STATUSES.has(status ?? "");
}

/**
 * The clause completing "In Bali, this activity is currently …".
 *
 * Total over the statuses above. The fallback is deliberately CAUSE-FREE: an
 * unrecognised status means we do not know why it is blocked, and naming a
 * plausible cause is exactly the defect this replaces. A declared gap beats a
 * confident wrong answer (kbli-navigator corner §0).
 */
export function baliBlockClause(status?: string | null): string {
  switch (status) {
    case "BLOCCATO_CLASSE_RISCHIO":
    case "CHIUSO_MORATORIA_BALI":
      return "blocked for a PT PMA under the 13 May 2026 moratorium";
    case "CHIUSO_PMA_NO_BESAR":
      return "reserved for micro/small/medium enterprises and closed to a PT PMA";
    case "TERTUTUP":
      return "closed to a PT PMA by an ownership restriction on the activity itself — not by the Bali moratorium";
    case "CHIUSO_REGOLATORE_SETTORIALE":
      return "closed to private and foreign capital by the sector's own regulator";
    case "CHIUSO_BALI":
      return "closed to PMA registration under Bali's announced sectoral closures";
    case "CHIUSO_BALI_PROPOSTO":
      // Announced, NOT in force. Stated as a conservative posture rather than a
      // settled bar, so a reader is not turned away from an activity that is
      // still registrable today.
      return "treated as closed to a PT PMA on a conservative reading: a sectoral closure has been proposed for this activity but is not yet in force";
    default:
      return "not open to a PT PMA";
  }
}

/**
 * Is the risk-tier moratorium the ACTUAL basis of this code's Bali verdict?
 *
 * `l4_bali.moratorium.rule` is not per-code evidence: it is one constant string
 * stamped on all 1,559 records ("Bali province blocks ALL Low + Medium-Low risk
 * KBLI for PMA"). The provenance panel cited it as the SOURCE of every Bali
 * verdict and described every one as "derived from the risk tier" — true for the
 * moratorium statuses, false for the 98 codes blocked by something else.
 * Verified on prod 2026-07-27: `/kbli/38122` (radioactive-waste collection,
 * closed by its sector's own regulator) and `/kbli/11010` (alcohol distilling,
 * closed by an ownership restriction) both served exactly that attribution.
 *
 * A code that is NOT blocked is `true` here on purpose: the risk-tier test is
 * genuinely what cleared it, so the existing wording stays right for it.
 */
export function isMoratoriumBasis(
  blocked: boolean | undefined,
  status?: string | null,
): boolean {
  if (!blocked) return true;
  return MORATORIUM_STATUSES.has(status ?? "");
}

// A reason that answers "did the moratorium test fire?" rather than "why is this
// blocked?". Machine-generated by resolve_kbli_l4_needs_review.py, so the phrase
// is stable and can be anchored at the end of the string rather than sniffed for
// loosely. Splicing it after a NON-moratorium clause is what produced the
// self-contradiction above; after a moratorium clause it is coherent, so the
// suppression is conditional on the cause, never unconditional.
const MORATORIUM_TEST_NOTE = /not\s+blocked\s+by\s+moratorium\s*\.?\s*$/i;

const MORATORIUM_STATUSES = new Set([
  "BLOCCATO_CLASSE_RISCHIO",
  "CHIUSO_MORATORIA_BALI",
]);

/**
 * Should the record's own `reason` be shown after the clause?
 *
 * Yes when it explains the bar — those are the valuable ones ("Legal services
 * are reserved for Indonesian-licensed advocates (UU 18/2003)", "for PMA use
 * 86103 (klinik, TERBATAS 67%)"). No when it is the moratorium-test note on a
 * code the moratorium did not block: there it contradicts the clause it follows.
 */
export function shouldShowReason(
  status?: string | null,
  reason?: string | null,
): boolean {
  const text = (reason ?? "").trim();
  if (!text) return false;
  if (containsItalian(text)) return false;
  if (MORATORIUM_STATUSES.has(status ?? "")) return true;
  return !MORATORIUM_TEST_NOTE.test(text);
}

// `l4_bali.reason` is an INTERNAL field and part of it was authored in Italian.
// It reaches a client verbatim through the frame above: `/kbli/69104` serves, in
// visible text today, "Notaio/PPAT è ufficio personale e statale, solo WNI (UU
// 30/2004 mod. UU 2/2014). PMA impossibile", and `/kbli/79110` serves "travel
// agency: proposto chiusura".
//
// Suppressing costs a real citation (69104's UU 30/2004), and that is the right
// trade: the derived clause already states the cause, while Italian in a
// client-facing English page is a defect with no upside. Word-boundary anchored
// on function words that cannot appear in the English corpus — never a bare
// substring (superscar #3).
//
// The marker list was VALIDATED against all 518 blocked reasons, not guessed,
// and the first draft was wrong in exactly the way this codebase keeps being
// wrong: it included `\bsolo\b`, which flagged `86201`/`86202` — English
// sentences ("a foreign specialist cannot open a solo practice; for PMA use
// 86103, klinik, TERBATAS 67%") carrying the most useful referral in the whole
// corpus. The measured list flags 2 of 518, and both are genuinely Italian.
// Innocence is pinned by test, so re-adding a word that eats an English reason
// fails CI rather than a client's page.
const ITALIAN_MARKER_RE =
  /(\bè\b|\bproposto\b|\bchiusura\b|\bufficio\b|\bstatale\b|\bimpossibile\b|\bdella\b|\bdello\b|\bdegli\b)/i;

export function containsItalian(text: string): boolean {
  return ITALIAN_MARKER_RE.test(text);
}

// =============================================================================
// A walkthrough that narrates a licensing route the page says has no basis
//
// When a collision cure detaches a code's licensing rows, `KeyFacts` says so —
// "Licensing Route: No verified basis — divergence documented". The gold
// editorial walkthrough rendered below it was never given the same knowledge, so
// `/kbli/86202` (specialist medical practice) serves, today, "Licensing Route:
// No verified basis" and then, further down: "NIB + Standard Certificate (Micro
// / Small / Medium / Large, Medium-High risk) — Authority: Bupati/Walikota — 25
// Hari". The tier, the issuing authority and the timeline all come from the row
// the cure disowned. Step 1 of that same walkthrough was already corrected to
// "local, WNI"; step 3 was not.
//
// Measured: 217 records serve ZERO licensing rows, 44 of them are masked by a
// gold walkthrough, and 8 of those 44 narrate a concrete route anyway — 72101,
// 75001, 75002, 75009 (veterinary), 86109, 86202, 86203 (medical), 91222. The
// other 36 already read as honest gaps, which is why this fires on the NARRATION
// and not merely on "no rows": framing all 44 would paste a redundant warning
// onto 36 pages that are already right.
// =============================================================================

/** An OSS risk-tier NAME, in either language the corpus uses. */
const TIER_NAME_RE =
  /\b(Menengah\s+(Tinggi|Rendah)|Medium[- ](High|Low)\s+risk|High\s+risk|Low\s+risk|Risiko\s+\w+)\b/i;

/** A procedural specific: who issues it, or how long it takes. */
const ROUTE_SPECIFIC_RE =
  /\bAuthority:|\bBupati\b|\bWali\s*ko?ta\b|\bMenteri\b|\bGubernur\b|\d+\s*Hari\b/i;

/**
 * Does this gold walkthrough state a licensing route while the page serves no
 * verified row to support it?
 *
 * Both halves are required. A tier name alone can appear in an honest sentence
 * ("the correct risk tier is not yet defined"), and an authority alone can
 * belong to a sectoral note. It is the PAIR — a tier plus who issues it or how
 * long it takes — that reads as a route a client can follow.
 */
export function narratesUnverifiedRoute(
  servedLicensingRows: number,
  goldWhatYouNeed?: string | null,
): boolean {
  if (servedLicensingRows > 0) return false;
  const text = (goldWhatYouNeed ?? "").trim();
  if (!text) return false;
  return TIER_NAME_RE.test(text) && ROUTE_SPECIFIC_RE.test(text);
}

/**
 * The "Blocked in Bali" trust-bar hint on /kbli.
 *
 * It used to be one hardcoded sentence attributing the whole percentage to the
 * 13 May 2026 risk-tier moratorium: "low and medium-low-risk activities are
 * treated as closed to foreign-owned companies (PT PMA)". That is the SAME
 * over-attribution `isMoratoriumBasis` exists to prevent one surface away — the
 * per-code page was cured on 2026-07-27 and this card was missed, so the index
 * kept telling readers that the risk tier is why every blocked code is blocked.
 *
 * Two things were wrong with it, both measured on the served dataset:
 *
 *  - **Cause.** Of 518 blocked codes, 420 are moratorium-based
 *    (BLOCCATO_CLASSE_RISCHIO 372 + CHIUSO_MORATORIA_BALI 48) and **98 are
 *    not** — 68 TERTUTUP (an ownership restriction on the activity itself),
 *    17 NON_CLASSIFICABILE (we hold no licensing rows, so no Bali position can
 *    be stated), 7 CHIUSO_PMA_NO_BESAR (genuinely allocated to Koperasi/UMKM
 *    by Perpres 49/2021 Lampiran II), 2 closed by their sector's own regulator,
 *    2 scope-dependent, 2 by Bali's announced sectoral closures. That 98 is the
 *    same figure this module's own comment already names.
 *
 *    Was 407/111 with 39 CHIUSO_PMA_NO_BESAR until 2026-08-03. The old figure
 *    counted an INFERENCE, not a reservation: 32 of the 39 were closed because
 *    OSS holds no Usaha Besar scale row for them, which Permeninves/BKPM
 *    5/2025 Pasal 26(1) inverts — a PT PMA is Usaha Besar as a CONSEQUENCE of
 *    being foreign-owned, so the absence of that row says nothing about
 *    foreign ownership. Each was adjudicated against the annex; seven survived.
 *
 *  - **Rule.** Read as a rule, "low and medium-low-risk activities are treated
 *    as closed" is far wider than what we do: 405 codes carry only low or
 *    medium-low risk and 22 of them render closed under the scale status.
 *
 * So the counts are DERIVED here rather than restated in prose, and the
 * qualifier that made the old sentence honest — a working assessment, not a
 * certified legal determination — is kept verbatim. Deriving them also means
 * the sentence cannot go stale the next time the overlay moves, which is how
 * the original became wrong.
 */
export function baliBlockedHint(
  codes: ReadonlyArray<{
    baliL4?: { status?: string | null; blocked?: boolean } | null;
  }>,
): string {
  if (codes.length === 0) return "";

  const blocked = codes.filter((c) => c.baliL4?.blocked);
  const moratorium = blocked.filter((c) =>
    MORATORIUM_STATUSES.has(c.baliL4?.status ?? ""),
  ).length;
  const other = blocked.length - moratorium;

  // NOTE the deliberate absence of a cause LIST for the `other` group.
  //
  // The first version of this function enumerated them — "an ownership
  // restriction on the activity, no Usaha Besar scale row, or a sector
  // regulator's own closure" — which named three of the FIVE statuses that
  // actually occur, silently dropping CHIUSO_BALI (70209) and
  // CHIUSO_BALI_PROPOSTO (79110). An adversarial review caught it before ship.
  //
  // That is the same failure as the sentence being replaced, one turn later: a
  // NEW claim written while correcting an old one, and never verified against
  // the data (superscar #6 / W113). A hand-written enumeration is a claim with
  // an expiry date — it silently becomes wrong the next time a status is added,
  // which is exactly how the original text rotted. So the count is derived and
  // the causes are not asserted here at all; `baliBlockClause` already states
  // the right one per code, on the page that has the code in front of it.
  //
  // CHIUSO_BALI_PROPOSTO is the sharpest reason not to summarise: that closure
  // is proposed and NOT in force, so listing it beside settled bars would be a
  // third wrong statement, not a more complete one.
  const causes =
    other > 0
      ? `${moratorium} of them under Bali Zero's conservative reading of the 13 May 2026 provincial ` +
        `risk-tier moratorium, pending clearer national guidance; the other ${other} for reasons that ` +
        `have nothing to do with the risk tier, stated individually on each code's page.`
      : `all of them under Bali Zero's conservative reading of the 13 May 2026 provincial risk-tier ` +
        `moratorium, pending clearer national guidance.`;

  return (
    `${blocked.length} of ${codes.length} codes are treated as closed to a foreign-owned company ` +
    `(PT PMA) in Bali — ${causes} A working assessment, not a certified legal determination.`
  );
}
