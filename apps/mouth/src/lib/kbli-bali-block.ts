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

/**
 * The per-code adjudication of `TERTUTUP` the comment above says is required.
 *
 * A CODE list, not a status rule, because the status cannot carry the answer:
 * censused on the live catalogue, the 68 `TERTUTUP` records split into 8 whose
 * reason names a national legal basis, 2 that say "in Bali" explicitly, and
 * 58 — every one of them — whose reason is "medium-high/high risk → not blocked
 * by moratorium (verify per address)". That sentence answers whether the
 * MORATORIUM TEST fired; it never says where the closure applies. So for 58
 * codes the record does not hold the fact, and no rule over `l4_bali` can
 * invent it. They keep the Bali framing, which understates rather than
 * misdirects, and fixing them means fixing the DATA — a lane of its own.
 *
 * Each entry below was read individually and carries the instrument that closes
 * it nationwide. None is a guess from the code number or the title:
 */
const NATIONAL_CLOSURE_CODES = new Map<string, string>([
  [
    "01287",
    "narcotics/medicinal-plant cultivation — TERTUTUP/0% at the national level",
  ],
  [
    "47111",
    "minimarket/supermarket retail — reserved to Indonesian citizens (WNI)",
  ],
  [
    "47112",
    "minimarket/supermarket retail — reserved to Indonesian citizens (WNI)",
  ],
  ["59131", "film/video distribution — TERTUTUP/0% at the national level"],
  [
    "69102",
    "legal consultancy — reserved to Indonesian-licensed advocates, UU 18/2003",
  ],
  [
    "69104",
    "notary/PPAT — a personal State office, WNI only, UU 30/2004 as am. UU 2/2014",
  ],
  [
    "86201",
    "solo doctor's practice — closed to foreign nationals under Kemenkes health law",
  ],
  [
    "86202",
    "solo specialist practice — closed to foreign nationals under Kemenkes health law",
  ],
]);

/** Why this code is closed nationwide, or null when it is not (audit surface). */
export function nationalClosureBasis(code?: string | null): string | null {
  return NATIONAL_CLOSURE_CODES.get(code ?? "") ?? null;
}

export function isNationalClosure(
  status?: string | null,
  code?: string | null,
): boolean {
  return (
    NATIONAL_CLOSURE_STATUSES.has(status ?? "") ||
    NATIONAL_CLOSURE_CODES.has(code ?? "")
  );
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
    // Held pending verification, not an applied closure: only the Governor's
    // Jan-2026 letter names the low/medium-low risk tier — OSS itself never
    // closed on that basis. Dated language removed 2026-09-15 (W-J B1): the
    // one date this repo could verify is the applied closure's (CHIUSO_BALI),
    // not this one.
    case "BLOCCATO_CLASSE_RISCHIO":
    case "CHIUSO_MORATORIA_BALI":
      return "blocked for a PT PMA under the 2026 Bali request to close low/medium-low-risk PMA (held as a conservative posture)";
    case "CHIUSO_PMA_NO_BESAR":
      return "reserved for micro/small/medium enterprises and closed to a PT PMA";
    case "TERTUTUP":
      return "closed to a PT PMA by an ownership restriction on the activity itself — not by the Bali moratorium";
    case "CHIUSO_REGOLATORE_SETTORIALE":
      return "closed to private and foreign capital by the sector's own regulator";
    case "CHIUSO_BALI":
      // The one dated closure this repo can actually verify (Pemprov Bali
      // press release, 24 Jul 2026): OSS closed 18 named business fields to
      // new PMA licensing since the third week of May 2026.
      return "closed to new PMA licensing in Bali: OSS closed for 18 business fields since the third week of May 2026";
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
 * The caveat that follows `baliBlockClause` for a CHIUSO_BALI closure
 * disclosed on its own sourced evidence (review F1, added 2026-09-16). A
 * bare "closed to new PMA licensing" overstates the record in two
 * independent ways this function guards against:
 *
 *  - A SCOPED closure (the hotel rows — `closure.scopeQualifier`, e.g.
 *    "building area under 6,000 m²") bars only that slice of the code, not
 *    the whole thing. Every surface stating the closure must name the
 *    scope, never imply a blanket bar.
 *  - A record whose confidence is not HIGH, or is flagged `needsReview` (16
 *    MEDIUM codes, e.g. 47211 — a 2025 code that merges several KBLI-2020
 *    activities, only some of which are on Bali's 18-field list), is Bali
 *    Zero's own conservative reading applied to the WHOLE code. That is a
 *    posture, not a certainty, and every surface stating the closure must
 *    say so.
 *
 * Scope wins when both apply — it is the more specific, actionable fact.
 */
export function baliClosureQualifier(
  l4?: {
    confidence?: string | null;
    needsReview?: boolean | null;
    closure?: { scopeQualifier?: string | null } | null;
  } | null,
): string {
  const scope = l4?.closure?.scopeQualifier;
  if (scope) return ` for ${scope}`;
  if (l4?.confidence !== "HIGH" || l4?.needsReview) {
    return " (conservative reading: this 2025 code also covers activities not on Bali's list)";
  }
  return "";
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
 *  - **Cause.** Of 1,559 codes, 135 are blocked: 72 TERTUTUP (an ownership
 *    restriction on the activity itself), 40 CHIUSO_BALI (Pemprov closure),
 *    14 held for further adjudication, 7 CHIUSO_PMA_NO_BESAR (genuinely
 *    allocated to Koperasi/UMKM by Perpres 49/2021 Lampiran II), 2 closed by
 *    their sector's own regulator. The remaining 383 codes show "tier-only"
 *    (unverified or insufficient licensing data — see "verify on OSS"). This
 *    breakdown is derived from #6597, 2026-09-15.
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
  census?: ReadonlyArray<{ status: string; blocked: boolean }>,
): string {
  // Added 2026-09-16 (W-J B1 disclose) — a SEPARATE, additive reading, never
  // touching the doc comment above (which still describes the no-`census`
  // path accurately and is owned by another window's in-flight edit).
  //
  // `codes` alone answers "how many SERVED pages currently say so" — the
  // per-code disclosure gate (`discloseBaliL4`) withholds `baliL4` on most
  // unlocated records, so `codes`'s own population understates the true
  // count. `census` (`getBaliCensus()`) is the CANONICAL Bali status
  // population, ungated by per-code disclosure, so the two numbers now
  // answer different questions and this sentence states both explicitly
  // instead of silently picking the smaller one (as the /kbli index page did
  // until now: "14 of 1559" when the working census was already 135).
  if (census) {
    const censusBlocked = census.filter((c) => c.blocked);
    const applied = censusBlocked.filter(
      (c) => c.status === "CHIUSO_BALI",
    ).length;
    const moratorium = censusBlocked.filter((c) =>
      MORATORIUM_STATUSES.has(c.status),
    ).length;
    const other = censusBlocked.length - applied - moratorium;
    // The served subset: codes whose OWN page currently discloses the block
    // (a strict subset of `censusBlocked` — the rest are still "PMA status
    // not yet verified" pending the national tuple or a sourced closure).
    const shown = codes.filter((c) => c.baliL4?.blocked === true).length;

    const clauses: string[] = [];
    if (applied > 0) {
      clauses.push(
        `${applied} by Bali's own 2026 closure of specific business fields`,
      );
    }
    if (moratorium > 0) {
      clauses.push(
        `${moratorium} held under Bali Zero's conservative reading of the 2026 Bali risk-tier request pending verification`,
      );
    }
    if (other > 0) {
      // Review F4: naming "a national closure" here asserted a specific
      // cause for the whole `other` group — the same over-attribution the
      // no-census path below (see NOTE at line ~430) already refuses to
      // make. `baliBlockClause` states the real one per code, on the page
      // that has the code in front of it.
      clauses.push(
        `${other} for other reasons stated individually on each code's page`,
      );
    }
    const causeList =
      clauses.length <= 1
        ? clauses.join("")
        : clauses.length === 2
          ? clauses.join(" and ")
          : `${clauses.slice(0, -1).join(", ")}, and ${clauses[clauses.length - 1]}`;

    return (
      `${censusBlocked.length} of ${census.length} codes are treated as closed to a foreign-owned company ` +
      `(PT PMA) in Bali in our working census${causeList ? ` — ${causeList}.` : "."} ` +
      `${shown} of them state the closure and its cause on the code's own page; the others are marked ` +
      `"PMA status not yet verified" there until the national record is adjudicated. A working assessment, ` +
      `not a certified legal determination.`
    );
  }

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
  // Dated wording removed 2026-09-15 (W-J B1): "the 13 May 2026 moratorium"
  // named a date this repo never verified for a blanket risk-tier block. The
  // low/medium-low tier request is the Governor's own letter, not an applied
  // closure — so these codes are held pending verification, never asserted
  // closed on that basis alone. `other` still names no specific cause (see
  // the note above): it may be a national closure, Bali's own applied closure
  // of specific business fields, or something else — `baliBlockClause` states
  // the real one per code, on the page that has the code in front of it.
  const causes =
    other > 0
      ? `${moratorium} of them held under Bali Zero's conservative reading of the 2026 Bali risk-tier ` +
        `request, pending verification; the other ${other} for reasons that have nothing to do with that ` +
        `request — a national closure, Bali's applied closure of specific business fields, or another cause ` +
        `stated individually on each code's page.`
      : `all of them held under Bali Zero's conservative reading of the 2026 Bali risk-tier request, ` +
        `pending verification.`;

  return (
    `${blocked.length} of ${codes.length} codes are treated as closed to a foreign-owned company ` +
    `(PT PMA) in Bali — ${causes} A working assessment, not a certified legal determination.`
  );
}
