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
 * sponsor nationalities), plus the three `holds_stay_permit = yes` walks.
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
    return id === "birth_date" ? "2000-11-11" : "2026-12-31";
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
