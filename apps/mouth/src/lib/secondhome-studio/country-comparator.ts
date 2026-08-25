/**
 * Second Home Studio — Country Comparator: DATA CONTRACT ONLY.
 *
 * This module renders nothing and is imported by nothing. That is
 * deliberate: the hard and dangerous part of this feature is which claims
 * may be published and with what provenance, and that deserves to land, be
 * reviewed, and be tested on its own before any pixel depends on it. See
 * `__tests__/country-comparator.test.ts` for the structural guards that
 * make the exclusions below unfalsifiable, not just a comment the next
 * contributor deletes.
 *
 * SOURCE OF TRUTH: research/visa/2026-08-24-second-home-country-comparison.md
 * §2 "What is safe to publish" — and ONLY that section. That document's own
 * adversarial review returns NOT PUBLISHABLE for the document as a
 * standalone grading memo (missing the underlying generator sheet's full
 * table + five-point section, some orphan figures) — that verdict is about
 * the memo, not about §2's safe-list, which is separately reasoned and is
 * what this file encodes.
 *
 * INDONESIA COLUMN — SSOT is research/secondhome/e33-fact-registry.json,
 * not the comparator research (which explicitly did not re-grade Indonesia
 * — "not re-graded per mandate (SSOT already governs it)"). Every Indonesia
 * cell below cites a fact-registry id via `factRef()`. No conflict between
 * the two documents was found for any value used here — the research's own
 * cross-check (its Axis 2 Indonesia note) found its one Indonesia mention
 * (the 55/60 age ambiguity) matches the registry's `age_55_59_ambiguity_e33e`
 * entry exactly.
 *
 * HARD EXCLUSIONS (guarded structurally in the test file, not just here):
 *  1. SRRV Smile's discontinuation is never stated as settled fact — this
 *     file omits Smile entirely (the safer of the two options the mandate
 *     allowed).
 *  2. SRRV Courtesy deposit figures are never quoted — omitted entirely
 *     (PRA's live page table markup was garbled at that row).
 *  3. Malaysia's "no naturalisation pathway" claim never appears — out of
 *     scope, unverified, citizenship policy rather than visa mechanics.
 *  4. Thailand's "17% tax cap" never applies to the Wealthy Pensioner /
 *     Wealthy Global Citizen categories used here — they get an EXEMPTION
 *     on foreign-sourced income; 17% is a distinct Highly-Skilled-
 *     Professional benefit this comparison does not use. (The data below
 *     states the correction WITHOUT the literal digits, so the test file's
 *     absence-check can be a clean, strict substring guard rather than a
 *     claim-pattern heuristic.)
 *  5. Portugal D7's income floor is a FORMULA (Portaria n.º 1563/2007 Art.
 *     2.º(2)), never a frozen euro figure — see `PORTUGAL_D7_INCOME_FORMULA`.
 *     The 2026 RMMG value is carried as its own separate, dated field.
 *  6. "Own-name asset custody" is CONFIRMED only for Indonesia (SSOT).
 *     Every other programme's ownership wording is `"unverified"` —
 *     plausible (fixed-deposit/fund-unit products conventionally register
 *     to the account holder) but not independently source-checked this
 *     research pass.
 *  7. No Bali Zero price anywhere in this file — this is a comparison of
 *     foreign government programmes, not a Bali Zero offer.
 *
 * A judgement call worth surfacing rather than burying: §2 lists the
 * Thailand tax-exemption sentence (point 4 of "Where the Alternatives Beat
 * Indonesia", corrected) as safe to publish, but the research's own
 * adversarial review (finding 2) flags that specific tax mechanism as an
 * "orphan figure" — asserted without an identified source/date for the tax
 * claim itself (distinct from the LTR income thresholds, which ARE
 * primary-confirmed against ltr.boi.go.th). This file follows the mandate's
 * instruction to take what §2 marks safe, but encodes the tax-exemption and
 * work-rights claims at `"secondary_consensus"` confidence rather than
 * `"primary_confirmed"`, with a caveat — the honest middle between silently
 * upgrading it and silently dropping a §2-safe item.
 */

/** Every cell that carries a comparator value MUST carry these four things
 *  structurally. A residency-programme figure with no date is unusable —
 *  this shape makes an undated or unsourced cell impossible to construct
 *  without either lying in the literal or failing the test file's runtime
 *  shape check (TypeScript alone doesn't stop `as any`). */
export interface SourcedCell<T> {
  value: T;
  /** Government/gazette URL, or a repo-relative `factRef()` pointer into
   *  the E33 fact registry for Indonesia cells (no single canonical
   *  imigrasi.go.id URL exists in this repo — see fact-registry `source`
   *  fields, which cite fetch events, not stable page URLs). Never
   *  fabricated. */
  sourceUrl: string;
  /** ISO date (YYYY-MM-DD) this research pass verified/fetched sourceUrl
   *  (or, for Indonesia, the fact registry's own `source_date`). */
  capturedDate: string;
  /** The SOURCE's own stamped last-updated/effective date, when it
   *  publishes one (e.g. mm2h.gov.my's page-footer "Last Update:
   *  10/02/2026" — DD/MM/YYYY, so 2026-02-10 — or a gazette instrument's
   *  effective date). `null` when the source carries no such stamp of its
   *  own (a live-clock page, an undated checklist page). */
  sourceLastUpdated: string | null;
  confidence: ConfidenceTag;
  /** A caveat that MUST travel with this value wherever it is displayed —
   *  e.g. a BERSYARAT condition, an ambiguity disclosure, or "not
   *  independently confirmed". */
  caveat?: string;
}

export type ConfidenceTag =
  /** Government/gazette source fetched directly this research pass and the
   *  figure matched. */
  | "primary_confirmed"
  /** The government source was unreachable; independent secondary sources
   *  (law firms, relocation aggregators) agree with each other. Plausible,
   *  not primary-verified. */
  | "secondary_consensus"
  /** Not independently checked this research pass, or checked and found
   *  genuinely unresolved. Must not be presented as settled fact. */
  | "unverified";

/** Base cell constructor — every specialised `*Cell()` factory below is a
 *  thin, source-pinned wrapper over this, so a programme's cells never
 *  repeat the same sourceUrl/date/confidence quadruple by hand. */
function cell<T>(
  value: T,
  sourceUrl: string,
  capturedDate: string,
  sourceLastUpdated: string | null,
  confidence: ConfidenceTag,
  caveat?: string,
): SourcedCell<T> {
  return caveat === undefined
    ? { value, sourceUrl, capturedDate, sourceLastUpdated, confidence }
    : { value, sourceUrl, capturedDate, sourceLastUpdated, confidence, caveat };
}

const FACT_REGISTRY_PATH = "research/secondhome/e33-fact-registry.json";
const RESEARCH_DOC =
  "research/visa/2026-08-24-second-home-country-comparison.md";
/** This research pass's own fetch/verification date — the comparator
 *  research's frontmatter `date`. */
const CAPTURED = "2026-08-24";

/** Indonesia cells: repo-relative pointer into the E33 fact registry SSOT
 *  (never a fabricated imigrasi.go.id URL), captured as of the registry's
 *  own `source_date` for that fact. */
function factCell<T>(
  value: T,
  factId: string,
  sourceDate: string,
  caveat?: string,
): SourcedCell<T> {
  return cell(
    value,
    `${FACT_REGISTRY_PATH}#${factId}`,
    sourceDate,
    null,
    "primary_confirmed",
    caveat,
  );
}

const LTR_URL = "https://ltr.boi.go.th/";
function ltrCell<T>(value: T, caveat?: string): SourcedCell<T> {
  return cell(value, LTR_URL, CAPTURED, null, "primary_confirmed", caveat);
}

/** mm2h.gov.my's own page-footer stamp, "Last Update: 10/02/2026"
 *  (DD/MM/YYYY, Malaysian date format — 10 February 2026), present on all
 *  five category pages fetched. */
const MM2H_LAST_UPDATED = "2026-02-10";
function mm2hCell<T>(
  value: T,
  sourceUrl: string,
  caveat?: string,
): SourcedCell<T> {
  return cell(
    value,
    sourceUrl,
    CAPTURED,
    MM2H_LAST_UPDATED,
    "primary_confirmed",
    caveat,
  );
}

const PORTUGAL_GAZETTE_LEI_23_2007 =
  "https://diariodarepublica.pt/dr/legislacao-consolidada/lei/2007-34544675";
/** Consolidated to its last relevant amendment, Lei n.º 9/2025 (13 Feb 2025). */
const LEI_23_2007_LAST_AMENDED = "2025-02-13";
function pgvCell<T>(value: T, caveat?: string): SourcedCell<T> {
  return cell(
    value,
    PORTUGAL_GAZETTE_LEI_23_2007,
    CAPTURED,
    LEI_23_2007_LAST_AMENDED,
    "primary_confirmed",
    caveat,
  );
}

const PORTARIA_1563_2007 = "https://diariodarepublica.pt/dr";
function portariaCell<T>(
  value: T,
  sourceLastUpdated: string | null,
  caveat?: string,
): SourcedCell<T> {
  return cell(
    value,
    PORTARIA_1563_2007,
    CAPTURED,
    sourceLastUpdated,
    "primary_confirmed",
    caveat,
  );
}

const PRA_SRRVISA = "https://pra.gov.ph/SRRVisa";
function pratCell<T>(value: T, caveat?: string): SourcedCell<T> {
  return cell(value, PRA_SRRVISA, CAPTURED, null, "primary_confirmed", caveat);
}

// ---------------------------------------------------------------------------
// Custody / lock axis — §4 of the mandate: "the page's actual
// differentiator" — led with here as its own type, not flattened into prose.
// Neither structure is objectively better — the type intentionally carries
// no "winner" value. Malaysia's holder ends up owning real property;
// Indonesia's holder keeps 100% liquidity-free capital, but as cash.
// ---------------------------------------------------------------------------

export type LockStructure =
  /** Indonesia: the full deposit stays locked, in the applicant's own name,
   *  for the visa term, with no mandatory secondary purchase. */
  | "full_lock_no_secondary_purchase"
  /** Malaysia: the deposit is partially withdrawable (after MM2H approval),
   *  but a separate, compulsory, unsellable-for-10-years property purchase
   *  is required alongside it. */
  | "partial_withdrawal_plus_compulsory_property"
  /** Thailand's income-test route and Portugal's routes (Golden Visa and
   *  D7) as described: no lockup on the described route. */
  | "no_lockup"
  /** The lock/withdrawal terms of this programme's capital instrument were
   *  not verified in this research pass — do not state as locked or
   *  unlocked. */
  | "not_verified_this_session";

export type OwnNameCustodyStatus =
  /** Indonesia only — SSOT-confirmed. */
  | "confirmed"
  /** Every other programme — plausible, not independently source-checked. */
  | "unverified"
  /** The programme has no capital asset held at all (e.g. Portugal D7 is a
   *  pure income test) — the question does not apply. */
  | "not_applicable";

export interface CustodyProfile {
  lockStructure: SourcedCell<LockStructure>;
  /** Factual structural description — never editorialised as
   *  "better"/"worse". */
  structureNote: SourcedCell<string>;
  assetOwnNameStatus: SourcedCell<OwnNameCustodyStatus>;
}

export interface CapitalInstrument {
  /** Human label distinguishing this instrument from siblings on the same
   *  programme (e.g. Indonesia has a deposit AND a property alternative). */
  label: string;
  cell: SourcedCell<string>;
}

export type ProgrammeId =
  | "indonesia_e33_base"
  | "indonesia_e33e_senior"
  | "thailand_ltr_wealthy_pensioner"
  | "malaysia_mm2h"
  | "portugal_golden_visa"
  | "portugal_d7"
  | "philippines_srrv_classic";

export interface CountryProgramme {
  id: ProgrammeId;
  country: string;
  programmeName: string;
  custody: CustodyProfile;
  capitalInstruments: readonly CapitalInstrument[];
  firstGrantValidity: SourcedCell<string>;
  /** Only Indonesia has an explicit cumulative-stay cap in the source
   *  material reviewed here. */
  cumulativeCap?: SourcedCell<string>;
  incomeRequirement?: SourcedCell<string>;
  workRights?: SourcedCell<string>;
  taxTreatment?: SourcedCell<string>;
}

/** Not independently source-checked this research pass for any competitor
 *  — reused verbatim on every non-Indonesia `assetOwnNameStatus` cell so
 *  the caveat can never drift between programmes (hard exclusion #6). */
const UNVERIFIED_OWN_NAME_CAVEAT =
  "Not independently source-checked this research pass; consistent with how fixed-deposit/fund-unit products conventionally register, but not confirmed.";

function unverifiedOwnName(
  sourceUrl: string,
): SourcedCell<OwnNameCustodyStatus> {
  return cell(
    "unverified",
    sourceUrl,
    CAPTURED,
    null,
    "unverified",
    UNVERIFIED_OWN_NAME_CAVEAT,
  );
}

// ---------------------------------------------------------------------------
// Indonesia — SSOT: research/secondhome/e33-fact-registry.json
// ---------------------------------------------------------------------------

const INDONESIA_E33_BASE: CountryProgramme = {
  id: "indonesia_e33_base",
  country: "Indonesia",
  programmeName: "E33 Second Home Visa (base deposit/property route)",
  custody: {
    lockStructure: factCell(
      "full_lock_no_secondary_purchase",
      "e33_base_deposit_amount",
      "2026-07-19",
    ),
    structureNote: cell(
      "The full USD 130,000 deposit (or USD 1,000,000 qualifying property) stays in the applicant's own name for the visa term, with no mandatory secondary purchase — the sharpest structural contrast in this comparator; no competitor programme reviewed claims a comparably absolute lock.",
      `${RESEARCH_DOC}#2-what-is-safe-to-publish`,
      CAPTURED,
      null,
      "primary_confirmed",
    ),
    assetOwnNameStatus: factCell(
      "confirmed",
      "e33_base_deposit_amount",
      "2026-07-19",
    ),
  },
  capitalInstruments: [
    {
      label: "Deposit (own-name, state-owned/BUMN bank)",
      cell: factCell("USD 130,000", "e33_base_deposit_amount", "2026-07-19"),
    },
    {
      label: "Property alternative (completed strata unit / apartment only)",
      cell: factCell(
        "USD 1,000,000",
        "e33_base_property_alternative",
        "2026-08-23",
        "BERSYARAT: off-plan and leasehold do NOT qualify — completed strata unit only. The qualifying legal title type remains unresolved (BELUM_DIATUR_PUBLIK) and must not be asserted.",
      ),
    },
  ],
  firstGrantValidity: factCell(
    "Up to 5 years first grant",
    "e33_first_grant_duration",
    "2026-07-19",
  ),
  cumulativeCap: factCell(
    "First grant <5y -> 6-year cumulative cap; first grant >=5y -> 10-year cumulative cap (Permenkumham 22/2023 Pasal 113)",
    "pasal_113_cumulative_caps",
    "2026-07-21",
  ),
  workRights: factCell(
    "Pure residence permit — does NOT authorize employment; paid work needs a separate work permit/KITAS.",
    "e33_not_work_visa",
    "2026-07-21",
  ),
};

const INDONESIA_E33E_SENIOR: CountryProgramme = {
  id: "indonesia_e33e_senior",
  country: "Indonesia",
  programmeName: "E33E senior/retirement 5-year golden visa",
  custody: {
    lockStructure: factCell(
      "full_lock_no_secondary_purchase",
      "e33e_requirements",
      "2026-07-19",
    ),
    structureNote: factCell(
      "Same full-lock, own-name structure as the base route, applied to the senior deposit.",
      "e33e_requirements",
      "2026-07-19",
    ),
    assetOwnNameStatus: factCell(
      "confirmed",
      "e33e_requirements",
      "2026-07-19",
    ),
  },
  capitalInstruments: [
    {
      label: "Deposit (own-name, state-owned bank)",
      cell: factCell(
        "USD 50,000",
        "e33e_requirements",
        "2026-07-19",
        "BERSYARAT: the 55-59 age band is disputed within Permenkumham 11/2024 itself (Pasal 33(2)(j)(4) says 55, Pasal 33(10)(d) still reads 60) — disclose the ambiguity, never assert the band as uncontested. Financial figures themselves are not disputed.",
      ),
    },
  ],
  firstGrantValidity: factCell(
    "5-year validity",
    "e33e_requirements",
    "2026-07-19",
  ),
  incomeRequirement: factCell(
    "USD 3,000/month income, in addition to the deposit",
    "e33e_requirements",
    "2026-07-19",
  ),
};

// ---------------------------------------------------------------------------
// Thailand LTR — Wealthy Pensioner / Wealthy Global Citizen
// ---------------------------------------------------------------------------

const RESEARCH_WEAK_SOURCE_CAVEAT =
  "The comparator research's own adversarial review flags this claim as lacking an identified source/date for the specific mechanism (distinct from the LTR income thresholds, which ARE primary-confirmed against ltr.boi.go.th). Directionally correct per §2's safe-to-publish corrected excerpt; not primary-confirmed.";

function researchDocCell(value: string, caveat?: string): SourcedCell<string> {
  return cell(
    value,
    `${RESEARCH_DOC}#3-corrected-excerpt`,
    CAPTURED,
    null,
    "secondary_consensus",
    caveat,
  );
}

const THAILAND_LTR: CountryProgramme = {
  id: "thailand_ltr_wealthy_pensioner",
  country: "Thailand",
  programmeName:
    "LTR (Long-Term Resident) — Wealthy Pensioner / Wealthy Global Citizen",
  custody: {
    lockStructure: ltrCell(
      "no_lockup",
      "The income test itself creates no investment/lockup requirement. A separate condition (health insurance >= USD 50,000 coverage OR USD 100,000 bank account) still applies; the lock/escrow status of that bank-account alternative was NOT confirmed this session — do not state it as locked or unlocked.",
    ),
    structureNote: ltrCell(
      "Qualification is via an income test (or income + Thailand investment), not a locked deposit.",
    ),
    assetOwnNameStatus: unverifiedOwnName(`${RESEARCH_DOC}#axis-3`),
  },
  capitalInstruments: [
    { label: "Passive income (option A)", cell: ltrCell("USD 80,000/year") },
    {
      label: "Passive income + Thailand investment (option B)",
      cell: ltrCell("USD 40,000-80,000/year + USD 250,000 Thailand investment"),
    },
    {
      label: "Health insurance / bank-account alternative condition",
      cell: ltrCell(
        "USD 50,000 minimum insurance coverage, OR USD 100,000 bank account",
      ),
    },
  ],
  firstGrantValidity: ltrCell("10 years total (5 + 5, renewable)"),
  workRights: researchDocCell(
    "Digital Work Permit route via the Board of Investment's One-Stop Service Center.",
    RESEARCH_WEAK_SOURCE_CAVEAT,
  ),
  taxTreatment: researchDocCell(
    "Exemption from Thai tax on foreign-sourced income for the Wealthy Pensioner / Wealthy Global Citizen categories used in this comparison. A separate flat-rate benefit exists for the LTR's Highly-Skilled Professional category only, which is out of scope for this comparator and must never be attributed to the categories compared here.",
    `${RESEARCH_WEAK_SOURCE_CAVEAT} The flat-rate-cap exclusion (hard exclusion #4) is independent of this confidence tag: that rate must never be stated for these categories regardless.`,
  ),
};

// ---------------------------------------------------------------------------
// Malaysia MM2H — five-tier table
// ---------------------------------------------------------------------------

export interface MalaysiaTier {
  tierName: string;
  depositUsd: SourcedCell<number>;
  /** `null` for the SEZ/SFZ tiers — the compulsory-property price is not a
   *  fixed figure in the source material (tied to Forest City, Johor
   *  development pricing, described only as "SEZ-priced-as-set"). */
  compulsoryPropertyRm: SourcedCell<number | null>;
  validityYears: SourcedCell<number>;
}

const COMPULSORY_PROPERTY_CAVEAT =
  "Compulsory in addition to the deposit; unsellable for 10 years.";
const SEZ_PROPERTY_CAVEAT =
  'Tied to Forest City, Johor property; the source describes it only as "SEZ-priced-as-set", not a fixed figure.';

function mm2hTier(
  tierName: string,
  urlSlug: string,
  depositUsd: number,
  compulsoryPropertyRm: number | null,
  propertyCaveat: string | undefined,
  validityYears: number,
): MalaysiaTier {
  const url = `https://www.mm2h.gov.my/category/${urlSlug}`;
  return {
    tierName,
    depositUsd: mm2hCell(depositUsd, url),
    compulsoryPropertyRm: mm2hCell(compulsoryPropertyRm, url, propertyCaveat),
    validityYears: mm2hCell(validityYears, url),
  };
}

export const MALAYSIA_MM2H_TIERS: readonly MalaysiaTier[] = [
  mm2hTier(
    "Platinum",
    "platinum",
    1_000_000,
    2_000_000,
    COMPULSORY_PROPERTY_CAVEAT,
    20,
  ),
  mm2hTier("Gold", "gold", 500_000, 1_000_000, COMPULSORY_PROPERTY_CAVEAT, 15),
  mm2hTier("Silver", "silver", 150_000, 600_000, COMPULSORY_PROPERTY_CAVEAT, 5),
  mm2hTier("SEZ/SFZ (age 21-49)", "sez", 65_000, null, SEZ_PROPERTY_CAVEAT, 10),
  mm2hTier("SEZ/SFZ (age 50+)", "sez", 32_000, null, SEZ_PROPERTY_CAVEAT, 10),
];

const MALAYSIA_MM2H: CountryProgramme = {
  id: "malaysia_mm2h",
  country: "Malaysia",
  programmeName: "MM2H (Malaysia My Second Home)",
  custody: {
    lockStructure: mm2hCell(
      "partial_withdrawal_plus_compulsory_property",
      "https://www.mm2h.gov.my/category/overview",
    ),
    structureNote: mm2hCell(
      "Maximum withdrawal of 50% of the principal fixed-deposit value is allowed after MM2H-participant approval has been obtained (not tied to a 1-year mark) — for purchasing a residence, education, medical, or tourism activities in Malaysia. The purchased property is COMPULSORY, separate from the deposit, and cannot be sold for 10 years. A real structural difference from Indonesia's E33, which requires only the one wholly-locked, wholly-owned deposit with no mandatory secondary purchase. Neither structure is objectively better: Malaysia's holder ends up owning real property, Indonesia's holder keeps 100% liquidity-free capital, as cash.",
      "https://www.mm2h.gov.my/category/overview",
    ),
    assetOwnNameStatus: unverifiedOwnName(`${RESEARCH_DOC}#axis-3`),
  },
  // Deposit + compulsory-property figures live in MALAYSIA_MM2H_TIERS
  // (five tiers, two-instrument-each) rather than squeezed into a flat
  // list here — see that export.
  capitalInstruments: [],
  firstGrantValidity: mm2hCell(
    "5 / 15 / 20 years by tier (Silver / Gold / Platinum), renewable; SEZ/SFZ tiers 10 years, renewable",
    "https://www.mm2h.gov.my/category/overview",
  ),
};

// ---------------------------------------------------------------------------
// Portugal — Golden Visa
// ---------------------------------------------------------------------------

const PORTUGAL_GOLDEN_VISA: CountryProgramme = {
  id: "portugal_golden_visa",
  country: "Portugal",
  programmeName: "Golden Visa (ARI)",
  custody: {
    lockStructure: pgvCell("no_lockup"),
    structureNote: pgvCell(
      'Real-estate route permanently eliminated since 7 October 2023 (Lei n.º 56/2023, "Mais Habitação") — Art. 3.º n.º 5 of the consolidated text states the surviving investment routes "não se podem destinar, direta ou indiretamente, ao investimento imobiliário" ("may not be directed, directly or indirectly, at real-estate investment"). This review did not locate an AIMA Golden Visa page through its own site search or the paths tested (0 search results for "golden visa"); the primary source used is the official gazette.',
    ),
    assetOwnNameStatus: unverifiedOwnName(`${RESEARCH_DOC}#axis-3`),
  },
  capitalInstruments: [
    {
      label: "Job creation",
      cell: pgvCell(">=10 jobs created (no fixed capital figure)"),
    },
    { label: "Scientific research", cell: pgvCell("EUR 500,000") },
    {
      label: "Cultural heritage / artistic production",
      cell: pgvCell("EUR 250,000"),
    },
    {
      label: "Non-real-estate fund units",
      cell: pgvCell(
        "EUR 500,000 (>=5-year fund maturity, >=60% invested in Portuguese-domiciled companies)",
      ),
    },
    {
      label: "Company incorporation with jobs",
      cell: pgvCell(
        "EUR 500,000 + 5 permanent jobs (or capital reinforcement creating 5 jobs / retaining 10, min. 5 permanent, over a 3-year minimum)",
      ),
    },
  ],
  firstGrantValidity: cell(
    "Renewable residence permit; validity/renewal term and citizenship-eligibility timelines not verified this research pass",
    PORTUGAL_GAZETTE_LEI_23_2007,
    CAPTURED,
    LEI_23_2007_LAST_AMENDED,
    "unverified",
    "This research pass verified the investment-route legal basis only — do not state the renewal term or a citizenship-eligibility timeline as confirmed from this file.",
  ),
  workRights: researchDocCell(
    "Open employment and business establishment permitted.",
  ),
};

// ---------------------------------------------------------------------------
// Portugal — D7 (income-based route)
// ---------------------------------------------------------------------------

/** Portaria n.º 1563/2007, Art. 2.º(2) — the subsistence-means FORMULA D7
 *  inherits via Lei n.º 23/2007 Art. 52.º(1)(d). Deliberately NOT a frozen
 *  euro figure (hard exclusion #5): the RMMG value below is a separate,
 *  dated field that changes annually — only IT needs updating when the
 *  RMMG changes; the formula percentages do not. */
export interface PortugalD7IncomeFormula {
  legalBasis: SourcedCell<string>;
  principalPercentOfRmmg: SourcedCell<number>;
  additionalAdultPercentOfRmmg: SourcedCell<number>;
  dependentChildPercentOfRmmg: SourcedCell<number>;
  rmmg2026MonthlyEur: SourcedCell<number>;
}

export const PORTUGAL_D7_INCOME_FORMULA: PortugalD7IncomeFormula = {
  legalBasis: portariaCell(
    "Portaria n.º 1563/2007, Art. 2.º(2), still in force",
    null,
  ),
  principalPercentOfRmmg: portariaCell(100, null),
  additionalAdultPercentOfRmmg: portariaCell(50, null),
  dependentChildPercentOfRmmg: portariaCell(30, null),
  rmmg2026MonthlyEur: portariaCell(
    920,
    "2026-01-01",
    "Effective 1 January 2026; the recital of Decreto-Lei n.º 29-A/2026 (30 Jan 2026, Diário da República n.º 21/2026) cites Decreto-Lei n.º 139/2025 (29 Dec 2025) as the instrument that actually fixed this figure. Re-set annually — do not hardcode a future year against this value.",
  ),
};

const PORTUGAL_D7: CountryProgramme = {
  id: "portugal_d7",
  country: "Portugal",
  programmeName: "D7 (passive-income residence visa)",
  custody: {
    lockStructure: pgvCell("no_lockup"),
    structureNote: pgvCell(
      "Zero capital lockup — D7 is a pure income test, no deposit or investment instrument.",
    ),
    assetOwnNameStatus: pgvCell(
      "not_applicable",
      "D7 holds no capital asset at all — the own-name-custody question does not apply.",
    ),
  },
  capitalInstruments: [],
  firstGrantValidity: cell(
    "Renewable residence permit; exact first-grant term not verified this research pass",
    PORTUGAL_GAZETTE_LEI_23_2007,
    CAPTURED,
    LEI_23_2007_LAST_AMENDED,
    "unverified",
  ),
  incomeRequirement: portariaCell(
    "Formula, not a frozen figure: 100% of the RMMG (statutory minimum wage) for the principal applicant, +50% per additional adult, +30% per dependent child. Resolves to EUR 920.00/month for a single applicant at the 2026 RMMG. See PORTUGAL_D7_INCOME_FORMULA for the structured formula and the separately dated RMMG value.",
    "2026-01-01",
  ),
  workRights: researchDocCell(
    "Open employment and business establishment permitted.",
  ),
};

// ---------------------------------------------------------------------------
// Philippines — SRRV Classic
//
// SRRV Smile (discontinued, unsourceable as fact) and SRRV Courtesy
// (garbled source markup) are deliberately OMITTED — hard exclusions #1/#2.
// ---------------------------------------------------------------------------

const PENSION_INCOME_CAVEAT =
  "Additionally requires proof of a lifetime pension >= USD 800/month (single) or >= USD 1,000/month (with dependents).";

const PHILIPPINES_SRRV_CLASSIC: CountryProgramme = {
  id: "philippines_srrv_classic",
  country: "Philippines",
  programmeName: "SRRV Classic (Special Resident Retiree's Visa)",
  custody: {
    lockStructure: cell(
      "not_verified_this_session",
      PRA_SRRVISA,
      CAPTURED,
      null,
      "unverified",
      "The lock/withdrawal terms of the SRRV Special Time Deposit were not verified in this research pass — do not state as locked or unlocked.",
    ),
    structureNote: cell(
      "Deposit-tier route with an additional pension-income floor for pensioner applicants; withdrawal/lock mechanics of the Special Time Deposit itself were not part of this research pass's scope.",
      PRA_SRRVISA,
      CAPTURED,
      null,
      "unverified",
    ),
    assetOwnNameStatus: unverifiedOwnName(`${RESEARCH_DOC}#axis-3`),
  },
  capitalInstruments: [
    {
      label: "Pensioner deposit (age 50+)",
      cell: pratCell("USD 15,000", PENSION_INCOME_CAVEAT),
    },
    {
      label: "Pensioner deposit (age 40-49)",
      cell: pratCell("USD 25,000", PENSION_INCOME_CAVEAT),
    },
    { label: "Non-pensioner deposit (age 50+)", cell: pratCell("USD 30,000") },
    {
      label: "Non-pensioner deposit (age 40-49)",
      cell: pratCell("USD 50,000"),
    },
  ],
  firstGrantValidity: pratCell(
    "Principal applicants must be age 40+ (standardised across the tier table, effective 1 September 2025 per regional legal-publisher sources).",
    "The 1 September 2025 effective date is corroborated by ACCRALAW and Chambers and Partners (regional legal publishers), not fetched directly from a PRA circular this session — secondary_consensus in spirit; the age-40 floor itself IS primary-confirmed on the live pra.gov.ph/SRRVisa table.",
  ),
  workRights: researchDocCell(
    "Domestic employment permitted for holders who obtain a DOLE Alien Employment Permit.",
  ),
};

export const COUNTRY_PROGRAMMES: readonly CountryProgramme[] = [
  INDONESIA_E33_BASE,
  INDONESIA_E33E_SENIOR,
  THAILAND_LTR,
  MALAYSIA_MM2H,
  PORTUGAL_GOLDEN_VISA,
  PORTUGAL_D7,
  PHILIPPINES_SRRV_CLASSIC,
];

// ---------------------------------------------------------------------------
// Fairness — §2/§4 require BOTH directions publishable, never just the
// flattering one. Only points this research pass directly source-checked
// are encoded here; the underlying generator sheet's full five-point
// "Where the Alternatives Beat Indonesia" section is NOT reproduced beyond
// what §3's corrected excerpt actually gives verbatim (work rights + the
// Thailand tax correction, both on the programme rows above) plus the two
// numeric entry-capital gaps below, which §2 states with citable figures.
// ---------------------------------------------------------------------------

export type FairnessDirection = "favors_alternative" | "favors_indonesia";

export interface FairnessHighlight {
  id: string;
  direction: FairnessDirection;
  claim: SourcedCell<string>;
}

export const FAIRNESS_HIGHLIGHTS: readonly FairnessHighlight[] = [
  {
    id: "custody_lock_favors_indonesia",
    direction: "favors_indonesia",
    claim: cell(
      "Indonesia's 100% capital lock with no mandatory secondary purchase is the sharpest true differentiator against every competitor reviewed — no other programme claims a comparably absolute lock.",
      `${RESEARCH_DOC}#2-what-is-safe-to-publish`,
      CAPTURED,
      null,
      "primary_confirmed",
    ),
  },
  {
    id: "portugal_d7_income_floor_favors_alternative",
    direction: "favors_alternative",
    claim: cell(
      "Portugal D7's income floor (~EUR 920/month for a single applicant, 2026 RMMG) is dramatically below Indonesia E33E's USD 3,000/month senior-income requirement (in addition to E33E's USD 50,000 deposit).",
      `${RESEARCH_DOC}#2-what-is-safe-to-publish`,
      CAPTURED,
      null,
      "primary_confirmed",
    ),
  },
  {
    id: "philippines_srrv_entry_deposit_favors_alternative",
    direction: "favors_alternative",
    claim: cell(
      "The Philippines SRRV Classic pensioner-with-pension entry point (USD 15,000, age 50+) sits at exactly 30% of Indonesia E33E's USD 50,000 deposit alone — before E33E's separate USD 3,000/month senior-income requirement is even added.",
      `${RESEARCH_DOC}#adversarial-review`,
      CAPTURED,
      null,
      "primary_confirmed",
      "The 30% ratio (USD 15,000 / USD 50,000) is verified arithmetic per the research's own adversarial-review pass, not a restated editorial claim.",
    ),
  },
];
