/**
 * Generator for the interview-walk corpus consumed by the backend census test
 * `apps/backend-rag/backend/tests/services/visa_engine/test_interview_walk_census.py`.
 *
 * The corpus is DATA, never hand-written: it is produced by driving the REAL
 * interview state machine — `computeNextNode` from `flow.ts` (which itself
 * calls `getCategoryQuestionIds` to expand each category branch) and the REAL
 * `mapOracleFactsToApplicantFacts` from `fact-mapper.ts`. Every question is
 * answered with its FIRST option; typed questions get one fixed synthetic
 * identity (see `answerFor`), notably 121 stay-days, so the walk depends only
 * on the tree and not on the answers.
 *
 * The enumerated scenarios are the two-arm spine (offshore / onshore) crossed
 * with the eleven `CATEGORY_KEYS`, plus the sub-branches that exist today
 * (`invest` × 6 vehicles, `retirement` × 5 bases, `second_home` × 2 bases,
 * and — because `getCategoryQuestionIds` now serves `familyQuestionIds`
 * VERBATIM on both tiles — `family` AND `diaspora`, each × 7 relations × 2
 * sponsor nationalities), plus the three `holds_stay_permit = yes` walks,
 * plus 6 more `retirement` walks (the 5 offshore bases + the one onshore
 * neutral walk) re-run at `RETIREMENT_AGE_64_BIRTH_DATE` — every other walk
 * still applies at `YOUNG_APPLICANT_BIRTH_DATE`, since `birth_date` is a
 * spine question no branch reads (see `answerFor`).
 *
 * Diaspora is crossed rather than sampled once because its wire facts are
 * NOT a copy of the family arm's: `mapDisclosureFlags` adds
 * `ACTIVITY_BOUNDARY` on `category === "diaspora"` alone, so the two tiles
 * can reach different outcomes from the same relation. A tile that shares a
 * branch still needs its own walks.
 *
 * Regenerate with:
 *
 *     npm run visa-oracle:walk-corpus -w apps/mouth
 *
 * A PR that changes the interview tree (a new question, a new branch, a
 * reordered spine) MUST regenerate the corpus in that same PR and update
 * `EXPECTED_OUTCOME` / `WALK_DEAD_END_ALLOWLIST` in the census test to match.
 * `walk-corpus-determinism.test.ts` fails whenever the committed corpus and
 * this generator's output disagree by a single byte.
 */

import { mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { format } from "prettier";

import {
  CATEGORY_KEYS,
  QUESTIONS,
  type OracleFacts,
} from "../../src/app/(visa-oracle)/visa-oracle/_lib/tree";
import {
  computeNextNode,
  type OracleNode,
} from "../../src/app/(visa-oracle)/visa-oracle/_lib/flow";
import { mapOracleFactsToApplicantFacts } from "../../src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper";

const HERE = dirname(fileURLToPath(import.meta.url));

/** Where the census test reads the corpus from. */
export const DEFAULT_OUT_DIR = resolve(
  HERE,
  "../../../backend-rag/backend/tests/services/visa_engine/gold_coverage/fixtures/walks",
);

/**
 * Frozen interview clock. NOT the wall clock: `computeNextNode` compares
 * `permit_expiry` against it to decide the expired/current permit arm, so a
 * moving clock would silently re-shape two of the 43 walks.
 */
export const CORPUS_TODAY = new Date("2026-09-06T00:00:00Z");

/** Fixed synthetic assessment id — the mapper needs one and never emits it. */
const ASSESSMENT_ID = "x";

/**
 * The synthetic identity's birth date for every walk except the age-64
 * retirement variants below: 25 on `CORPUS_TODAY`, comfortably clear of
 * every age-gated rule in the pack.
 */
const YOUNG_APPLICANT_BIRTH_DATE = "2000-11-11";

/**
 * Birth date for the 6 age-64 retirement walks. `_derive_age_years`
 * (`fact_registry.py`) is birthday-inclusive against `effective_at`; both
 * `CORPUS_TODAY` and the highest signed pack's `signed_at` land on
 * 2026-09-06, so this clears the `hf.e33e.age-below-55` /
 * `hf.e33f.age-below-55` floor with margin while staying deliberately OUTSIDE
 * `el.e33e.age-55-59-disputed-band` (55-59) — that band carries its own
 * reason code and its own legal claim, and deserves a walk of its own rather
 * than a silent absorption into this one.
 */
const RETIREMENT_AGE_64_BIRTH_DATE = "1961-11-11";

/** Runaway guard: no real walk is anywhere near this long. */
const MAX_STEPS = 200;

export interface WalkFixture {
  /** Human-readable walk path, e.g. `offshore/family/SPOUSE/spNat=IT`. */
  label: string;
  /** Question ids in the order `computeNextNode` asked them. */
  asked: string[];
  /** The exact wire facts this walk produced, straight from the mapper. */
  overrides: Record<string, unknown>;
}

interface Scenario {
  label: string;
  overrides: Record<string, string>;
}

/**
 * The answer this driver gives to `id`. Scenario overrides win; otherwise a
 * typed question gets its fixed synthetic value and every other question gets
 * its FIRST option.
 */
export function answerFor(
  id: string,
  overrides: Record<string, string>,
): string {
  if (overrides[id] !== undefined) return overrides[id];
  const question = QUESTIONS[id];
  if (!question) throw new Error(`unknown question ${id}`);
  if (question.kind === "date") {
    return id === "birth_date" ? YOUNG_APPLICANT_BIRTH_DATE : "2026-12-31";
  }
  if (question.kind === "number") {
    if (id === "overstay_days") return "0";
    if (id === "stay_days") return "121";
    return "1000000000";
  }
  if (question.kind === "country-codes") return "IT";
  if (question.kind === "status-code") return "E31A";
  if (question.kind === "review-gate") return "none";
  return question.options[0].key;
}

/** Drive one walk from the framing node to whatever terminal node it reaches. */
export function runWalk(overrides: Record<string, string>): {
  asked: string[];
  facts: OracleFacts;
} {
  const facts: OracleFacts = {};
  const asked: string[] = [];
  let node: OracleNode = { kind: "framing" };
  for (let step = 0; step < MAX_STEPS; step += 1) {
    node = computeNextNode(node, facts, CORPUS_TODAY);
    if (node.kind !== "question") break;
    asked.push(node.questionId);
    facts[node.questionId] = answerFor(node.questionId, overrides);
  }
  return { asked, facts };
}

/**
 * Every distinct walk through the tree AS IT IS TODAY. Adding a branch to
 * `tree.ts` / `getCategoryQuestionIds` means adding it here too — the corpus
 * is only as complete as this enumeration.
 */
export function enumerateScenarios(): Scenario[] {
  const scenarios: Scenario[] = [];

  const INVESTMENT_VEHICLES = [
    "pt_pma",
    "property",
    "bank_deposit",
    "merit",
    "family",
    "undecided",
  ] as const;
  const RETIREMENT_BASES = [
    "bank_deposit",
    "property",
    "passive_income",
    "family_sponsor",
    "undecided",
  ] as const;
  // `second_home` offers exactly the two bases E33 has support rules for
  // (`el.e33.deposit-basis`, `el.e33.property-basis`) — see the
  // `secondhome_basis` question in tree.ts.
  const SECOND_HOME_BASES = ["bank_deposit", "property"] as const;
  const FAMILY_RELATIONS = [
    "SPOUSE",
    "CHILD",
    "PARENT",
    "SIBLING",
    "DEPENDENT",
    // STEPCHILD's option row landed in tree.ts on 2026-09-06; the branch in
    // `getCategoryQuestionIds` (its two evidence questions) had shipped in
    // 2026-08 already, so until now this relation was enumerable here only
    // in theory — the interview could never reach it.
    "STEPCHILD",
    "OTHER",
  ] as const;
  const SPONSOR_NATIONALITIES = ["IT", "ID"] as const;

  for (const category of CATEGORY_KEYS) {
    const base = {
      in_indonesia: "no",
      holds_stay_permit: "no",
      category,
    };
    if (category === "invest") {
      for (const vehicle of INVESTMENT_VEHICLES) {
        scenarios.push({
          label: `offshore/${category}/${vehicle}`,
          overrides: { ...base, investment_vehicle: vehicle },
        });
      }
    } else if (category === "retirement") {
      for (const basis of RETIREMENT_BASES) {
        scenarios.push({
          label: `offshore/${category}/${basis}`,
          overrides: { ...base, retirement_basis: basis },
        });
      }
      // Age dimension (owner mandate, 2026-09-07): the same 5 bases, replayed
      // at RETIREMENT_AGE_64_BIRTH_DATE. `AGE_BELOW_55` excluded E33E/E33F on
      // every walk above regardless of basis, so those 5 never exercised
      // either product's actual eligibility rule — E33E and E33F were never
      // exercised at an age that clears the hard filter.
      for (const basis of RETIREMENT_BASES) {
        scenarios.push({
          label: `offshore/${category}/${basis}/age64`,
          overrides: {
            ...base,
            retirement_basis: basis,
            birth_date: RETIREMENT_AGE_64_BIRTH_DATE,
          },
        });
      }
    } else if (category === "second_home") {
      for (const basis of SECOND_HOME_BASES) {
        scenarios.push({
          label: `offshore/${category}/${basis}`,
          overrides: { ...base, secondhome_basis: basis },
        });
      }
    } else if (category === "family" || category === "diaspora") {
      for (const relation of FAMILY_RELATIONS) {
        for (const nationality of SPONSOR_NATIONALITIES) {
          scenarios.push({
            label: `offshore/${category}/${relation}/spNat=${nationality}`,
            overrides: {
              ...base,
              family_relation: relation,
              family_sponsor_nationalities: nationality,
            },
          });
        }
      }
    } else {
      scenarios.push({ label: `offshore/${category}`, overrides: base });
    }
  }

  // Onshore arm: one neutral walk per category.
  for (const category of CATEGORY_KEYS) {
    scenarios.push({
      label: `onshore/${category}`,
      overrides: {
        in_indonesia: "yes",
        holds_stay_permit: "no",
        category,
      },
    });
    // Age dimension (owner mandate, 2026-09-07): the onshore retirement walk
    // gets its own age-64 sibling too, same reasoning as the offshore loop
    // above.
    if (category === "retirement") {
      scenarios.push({
        label: `onshore/${category}/age64`,
        overrides: {
          in_indonesia: "yes",
          holds_stay_permit: "no",
          category,
          birth_date: RETIREMENT_AGE_64_BIRTH_DATE,
        },
      });
    }
  }

  // The three walks that already hold a stay permit: expired vs current,
  // onshore vs offshore.
  scenarios.push({
    label: "onshore/holdsPermit/expired/tourism",
    overrides: {
      in_indonesia: "yes",
      holds_stay_permit: "yes",
      permit_expiry: "2026-01-01",
      category: "tourism",
    },
  });
  scenarios.push({
    label: "onshore/holdsPermit/current/tourism",
    overrides: {
      in_indonesia: "yes",
      holds_stay_permit: "yes",
      permit_expiry: "2027-01-01",
      category: "tourism",
    },
  });
  scenarios.push({
    label: "offshore/holdsPermit/current/tourism",
    overrides: {
      in_indonesia: "no",
      holds_stay_permit: "yes",
      permit_expiry: "2027-01-01",
      category: "tourism",
    },
  });

  // D3-3/D3-4 (PR-D3, owner ruling SHWEB-20260911): a walk per new branch
  // (spec §3), covering the gate conditions half-1 (D3-1/D3-2) owed and the
  // two new questions this PR adds.
  const base = { in_indonesia: "no", holds_stay_permit: "no" } as const;

  // C1: half-1's `invest` re-route, below the E33 threshold (walks 2/4,
  // 23-PR-D3-SPEC §walk-list). Above-threshold is already the corpus's
  // existing default for `offshore/invest/property`/`bank_deposit`.
  scenarios.push({
    label: "offshore/invest/property/below_threshold",
    overrides: {
      ...base,
      category: "invest",
      investment_vehicle: "property",
      secondhome_property_value_usd: "500000",
    },
  });
  scenarios.push({
    label: "offshore/invest/bank_deposit/below_threshold",
    overrides: {
      ...base,
      category: "invest",
      investment_vehicle: "bank_deposit",
      secondhome_deposit_usd: "50000",
    },
  });

  // C1: half-1's declared-paid-activity route (D3-2), the two negative facts
  // and the negative branch C2 says should deliver C6.
  scenarios.push({
    label: "offshore/other/paid/employer_no",
    overrides: {
      ...base,
      category: "other",
      other_paid_activity: "yes",
      work_payer: "no",
    },
  });
  scenarios.push({
    label: "offshore/other/paid/sponsor_unsure",
    overrides: {
      ...base,
      category: "other",
      other_paid_activity: "yes",
      work_payer: "yes",
      work_sponsor_confirmed: "unsure",
    },
  });
  // C2: the `paid = no` walk that must actually yield C6 (13 → 14 distinct
  // products) — `offshore/other`'s own default now answers `yes` (D3-2), so
  // this is a NEW walk, not a rewording of the existing one.
  scenarios.push({
    label: "offshore/other/no_paid_activity",
    overrides: { ...base, category: "other", other_paid_activity: "no" },
  });

  // D3-3: retirement branches that used to dead-end. `property`'s negative
  // sponsor answer (the age64/sponsor=yes walk is already the corpus's
  // regenerated default for `offshore/retirement/property/age64`).
  scenarios.push({
    label: "offshore/retirement/property/age64/sponsor_no",
    overrides: {
      ...base,
      category: "retirement",
      retirement_basis: "property",
      birth_date: RETIREMENT_AGE_64_BIRTH_DATE,
      family_sponsor_confirmed: "no",
    },
  });
  // `bank_deposit` was the funnel census's LARGEST dead end (30 production
  // walks) — below both the deposit and passive-income thresholds, cured
  // only by the family-sponsor fallback this PR adds.
  scenarios.push({
    label: "offshore/retirement/bank_deposit/age64/below_threshold",
    overrides: {
      ...base,
      category: "retirement",
      retirement_basis: "bank_deposit",
      birth_date: RETIREMENT_AGE_64_BIRTH_DATE,
      secondhome_deposit_usd: "1000",
      // Above el.e33f.retirement's own USD 3,000 floor (fact-mapper.ts
      // comment on ACTIVITY_BOUNDARY_DECIDABLE_ANSWERS.retirement_basis) —
      // deliberately NOT below it, so this walk proves the E33F fallback
      // cures the deposit-below-threshold dead end rather than merely
      // failing both products.
      secondhome_passive_income_usd: "5000",
      family_sponsor_confirmed: "yes",
    },
  });
  // `undecided` becomes a real question. `deposit_or_income` is already the
  // corpus's regenerated default for `offshore/retirement/undecided/age64`
  // (first option); these are its other two answers.
  scenarios.push({
    label: "offshore/retirement/undecided/age64/family_sponsor",
    overrides: {
      ...base,
      category: "retirement",
      retirement_basis: "undecided",
      birth_date: RETIREMENT_AGE_64_BIRTH_DATE,
      retirement_undecided_basis: "family_sponsor",
    },
  });
  scenarios.push({
    label: "offshore/retirement/undecided/age64/still_unsure",
    overrides: {
      ...base,
      category: "retirement",
      retirement_basis: "undecided",
      birth_date: RETIREMENT_AGE_64_BIRTH_DATE,
      retirement_undecided_basis: "still_unsure",
    },
  });

  // D3-4: STEPCHILD sponsor-permit answers. `yes` is already the corpus's
  // regenerated default for the existing STEPCHILD walks (first option);
  // these are `no` and `unsure`.
  scenarios.push({
    label: "offshore/family/STEPCHILD/spNat=ID/sponsor_permit_no",
    overrides: {
      ...base,
      category: "family",
      family_relation: "STEPCHILD",
      family_sponsor_nationalities: "ID",
      family_stepchild_sponsor_permit_confirmed: "no",
    },
  });
  scenarios.push({
    label: "offshore/family/STEPCHILD/spNat=ID/sponsor_permit_unsure",
    overrides: {
      ...base,
      category: "family",
      family_relation: "STEPCHILD",
      family_sponsor_nationalities: "ID",
      family_stepchild_sponsor_permit_confirmed: "unsure",
    },
  });

  return scenarios;
}

/** `offshore/family/SPOUSE/spNat=IT` -> `offshore_family_SPOUSE_spNat_IT`. */
export function fileNameFor(label: string): string {
  return `${label.replace(/[^A-Za-z0-9_]+/g, "_")}.json`;
}

/** The whole corpus as objects, keyed by file name, sorted by file name. */
export function buildWalkCorpus(): Map<string, WalkFixture> {
  const corpus = new Map<string, WalkFixture>();
  for (const scenario of enumerateScenarios()) {
    const { asked, facts } = runWalk(scenario.overrides);
    const wire = mapOracleFactsToApplicantFacts(facts, {
      assessmentId: ASSESSMENT_ID,
      collectedAt: CORPUS_TODAY,
    });
    const name = fileNameFor(scenario.label);
    if (corpus.has(name)) {
      throw new Error(`duplicate walk file name ${name} (${scenario.label})`);
    }
    corpus.set(name, {
      label: scenario.label,
      asked,
      overrides: wire.facts as unknown as Record<string, unknown>,
    });
  }
  return new Map([...corpus].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
}

/**
 * The corpus as the exact file BYTES. Prettier is called with an explicit
 * option set and no config resolution, so the rendering does not depend on
 * which directory the files are written to — the determinism test writes them
 * to a temp dir outside the repo and still gets byte-identical output.
 *
 * The input is COMPACT `JSON.stringify` on purpose. Prettier's json printer
 * preserves an object's first line break, so feeding it pre-indented JSON
 * would freeze every fact envelope in expanded form; from one line, printWidth
 * alone decides, which is what `npm run format:check` at the repo root expects.
 */
export async function renderWalkCorpus(): Promise<Map<string, string>> {
  const rendered = new Map<string, string>();
  for (const [name, fixture] of buildWalkCorpus()) {
    rendered.set(
      name,
      await format(JSON.stringify(fixture), { parser: "json" }),
    );
  }
  return rendered;
}

export interface WriteResult {
  written: string[];
  /** `.json` files already in `outDir` that this generator no longer emits. */
  orphans: string[];
}

/** Render the corpus and write it to `outDir`, creating the dir if needed. */
export async function writeWalkCorpus(outDir: string): Promise<WriteResult> {
  const rendered = await renderWalkCorpus();
  mkdirSync(outDir, { recursive: true });
  const written: string[] = [];
  for (const [name, text] of rendered) {
    writeFileSync(join(outDir, name), text, "utf8");
    written.push(name);
  }
  const existing = readdirSync(outDir).filter((f) => f.endsWith(".json"));
  const orphans = existing.filter((f) => !rendered.has(f)).sort();
  return { written, orphans };
}

async function main(argv: string[]): Promise<void> {
  const outIndex = argv.indexOf("--out");
  const outDir =
    outIndex >= 0 && argv[outIndex + 1]
      ? resolve(argv[outIndex + 1])
      : DEFAULT_OUT_DIR;
  const { written, orphans } = await writeWalkCorpus(outDir);
  console.log(`wrote ${written.length} walks to ${outDir}`);
  if (orphans.length > 0) {
    // Not deleted on purpose: a stale fixture is a review signal, and the
    // determinism test already fails on it (it compares the file SET too).
    console.error(
      `WARNING: ${orphans.length} stale fixture(s) no longer generated — delete them by hand:\n  ${orphans.join("\n  ")}`,
    );
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
