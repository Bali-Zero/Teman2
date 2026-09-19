/**
 * enumerate-interview-space.ts — Slice B1 (PLAN §3 row B1, criterion G2-a):
 * the enumerator that derives the interview walk SET, and its SIZE, from the
 * REAL graph (`computeNextNode` + `getCategoryQuestionIds`, both imported
 * from `flow.ts`, never re-implemented or copied), instead of a hand list.
 *
 * Model for style: `generate-walk-corpus.ts`. This script REUSES that
 * module's `answerFor` (the single-value default for a question with no
 * override) and `runWalk` (drives one walk from `framing` given an overrides
 * dict) rather than inventing a second execution path — per E6, "do not
 * invent a second way to execute TypeScript".
 *
 * ## Why "the exact count" and "the covering subset" are different numbers
 *
 * A brute-force depth-first walk of the real graph — every declared option
 * at every node, `"unsure"` wherever offered — was measured this session to
 * exceed 50,000,000 branches before even finishing the first few of 11
 * categories (`stopgap measurement, not committed here`). The TRUE count is
 * `walksTotalExact` below: 71,825,497,368,768 (~7.18×10^13), measured via
 * `npm run visa-oracle:enumerate -w apps/mouth -- --dry-run`, computed in
 * under two seconds via memoized DAG-reduction (see `countExactWalks`), not
 * materialized — nothing this large is written to disk or posted live. That
 * number is EXACT, not assumed: `bound: "PROVEN"` means every declared
 * question was reached and `walksTotalExact` was derived by summation, not
 * sampling.
 *
 * `buildCoveringSubset` then derives a SEPARATE, SMALL, deterministic walk
 * SET — one baseline walk plus one targeted walk per still-uncovered
 * `(questionId, answer)` edge — engineered to be small enough for B2 to
 * actually post within its rate budget while still exercising every node,
 * every option and every edge the graph declares at least once. This is the
 * manifest's `coveringSubset` and the thing this script actually WRITES.
 *
 * ## The memoization key (`BRANCH_RELEVANT_FACT_KEYS`) and why it is sound
 *
 * `computeNextNode`/`getCategoryQuestionIds` read a SMALL, fixed subset of
 * facts to decide what comes next — grep-verified against the WHOLE of
 * `flow.ts` (`grep -oE 'facts\.[a-zA-Z_]+' flow.ts | sort -u`, plus the one
 * dynamic `facts[id]` read inside `investmentRouteQuestionIds`). Two walks
 * that agree on every one of those keys have an IDENTICAL future regardless
 * of anything else either walk answered, so their subtree is counted once
 * and reused (`countExactWalks`'s memo). `test_covers_every_relevant_fact_
 * read_in_flow_ts` re-derives this set from the live source text and diffs
 * it against the table below, so a new branching read added to `flow.ts`
 * without a matching addition here fails LOUD (an under-count is a
 * guard-under-match, cicatrix family #3) rather than silently shrinking the
 * proven total.
 *
 * ## `review_gate` is handled outside the graph, on purpose
 *
 * `computeNextNode`'s `"review_gate"` case always returns `{kind:
 * "confirmation"}` — grep-verified, `facts.review_gate` is read NOWHERE in
 * `flow.ts` — so its answer can never change which node comes next. Its real
 * wire domain is not its own declared `options` (`["none","flagged"]`, a UI
 * gate) but `REVIEW_GATE_ITEMS` (13 keys): `fact-mapper.ts:405-406,581`
 * reads `facts.review_gate` as a comma-joined subset of that list. Because
 * it is provably orthogonal to traversal, `countExactWalks` folds its 13
 * values in as a flat multiplier at the leaf (exact arithmetic, not an
 * estimate) and `buildCoveringSubset` covers it with 12 cheap CLONES of the
 * baseline walk (one per non-`"none"` item) instead of 12× more traversal.
 *
 * ## Known gap
 *
 * E3 also asks for "every pair the tree's own branching conditions read
 * together". `flow.ts` has exactly two such joint reads outside a single
 * fact's own multi-value branch (grep: `grep -n 'facts\.' flow.ts | grep -E
 * '&&|\|\|'`): `wants_onshore_conversion` OR the `stay_days` > 360 boundary
 * (`businessExplorerQuestionIds`), and `investment_vehicle` (via
 * `isSecondHomeRoute`) AND `sponsor_category === "GOVERNMENT"` (the invest
 * branch). Both combinations already land inside the edge-covering set as a
 * SIDE EFFECT of `answerFor`'s own declared-first-option defaults (verified
 * this session: a walk targeting `stay_days=361` defaults
 * `wants_onshore_conversion` to its first option, `"yes"`, so `(yes, >360)`
 * is covered without a dedicated walk) — but no walk here is labelled or
 * asserted as covering them ON PURPOSE. A follow-up slice should name these
 * two pairs explicitly and assert their coverage rather than relying on
 * this incidental side effect.
 *
 * Usage (from `apps/mouth`, matching `generate-walk-corpus.ts`'s own):
 *
 *     npm run visa-oracle:enumerate -w apps/mouth -- --dry-run
 *     npm run visa-oracle:enumerate -w apps/mouth
 *
 * Synthetic personas only — the same placeholder identity
 * `generate-walk-corpus.ts` uses (`ASSESSMENT_ID = "x"`, fixed birth dates),
 * never a realistic name/passport/email.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { format } from "prettier";

import {
  QUESTIONS,
  REVIEW_GATE_ITEMS,
  type OracleFacts,
} from "../../src/app/(visa-oracle)/visa-oracle/_lib/tree";
import {
  computeNextNode,
  type OracleNode,
} from "../../src/app/(visa-oracle)/visa-oracle/_lib/flow";
import {
  mapOracleFactsToApplicantFacts,
  type DisclosedReviewFlagWire,
} from "../../src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper";
import { answerFor, runWalk, CORPUS_TODAY } from "./generate-walk-corpus";

const HERE = dirname(fileURLToPath(import.meta.url));

/** Where the manifest is written by default. */
export const DEFAULT_OUT_PATH = resolve(
  HERE,
  "../../../../research/operations/visa-oracle-interview-space-manifest.json",
);

/** Same frozen clock as the corpus generator, reused rather than redeclared. */
export const ENUMERATOR_TODAY = CORPUS_TODAY;

/** Fixed synthetic assessment id — no realistic identity is ever emitted. */
const ASSESSMENT_ID = "x";

/**
 * Only two typed (`options: []`) questions gate what comes next — see the
 * module docstring's grep evidence. Every other typed question gets ONE
 * representative value (`answerFor`'s own default): its numeric/date/country
 * value cannot change which node is asked next, so a second value would
 * only duplicate an existing walk, never add a new one.
 */
export const REPRESENTATIVE_VALUES: Readonly<
  Record<string, readonly string[]>
> = {
  // Gates `renewal_paid` — `flow.ts`'s `shouldAskRenewalPaid`:
  // `daysRemaining(permit_expiry, today) < 0` (past) vs `>= 0` (current/future).
  // An unparseable/empty value folds into the SAME "unknown" branch as the
  // `notSure` door below (`daysRemaining` returns `null` for both), so a
  // third representative value would not add a new branch.
  permit_expiry: ["2099-12-31", "2020-01-01"],
  // Gates the business-explorer investor sub-branch — `flow.ts`'s
  // `businessExplorerQuestionIds`: `Number(stay_days) > D12_MAX_STAY_DAYS` (360).
  stay_days: ["121", "361"],
};

/**
 * Every fact `flow.ts` reads anywhere to decide what comes next — see the
 * module docstring. `test_covers_every_relevant_fact_read_in_flow_ts`
 * re-derives this list from the live source and fails loud on drift.
 */
export const BRANCH_RELEVANT_FACT_KEYS: readonly string[] = [
  "business_activity",
  "category",
  "family_relation",
  "family_sponsor_nationalities",
  "holds_stay_permit",
  "in_indonesia",
  "investment_capital_market_only",
  "investment_currency",
  "investment_establishes_company",
  "investment_foreign_branch",
  "investment_ikn_subsidiary",
  "investment_pt_pma",
  "investment_vehicle",
  "other_paid_activity",
  "permit_expiry",
  "retirement_basis",
  "retirement_undecided_basis",
  "secondhome_basis",
  "sponsor_category",
  "stay_days",
  "wants_onshore_conversion",
];

/**
 * Every answer this enumerator explores for `questionId`: every declared
 * option, `REPRESENTATIVE_VALUES`'s set for the two branching typed
 * questions, `answerFor`'s single default for every other typed question,
 * `"unsure"` wherever `notSure` is offered, and `REVIEW_GATE_ITEMS` (its real
 * wire domain, not its own two-option UI gate) for `review_gate` alone.
 */
export function answersFor(questionId: string): string[] {
  const question = QUESTIONS[questionId];
  if (!question)
    throw new Error(
      `enumerate-interview-space: unknown question ${questionId}`,
    );
  if (questionId === "review_gate") return [...REVIEW_GATE_ITEMS];

  const declaredOptions = question.options.map((option) => option.key);
  let values: string[];
  if (declaredOptions.length > 0) {
    values = [...declaredOptions];
  } else if (REPRESENTATIVE_VALUES[questionId]) {
    values = [...REPRESENTATIVE_VALUES[questionId]];
  } else {
    values = [answerFor(questionId, {})];
  }
  if (question.notSure && !values.includes("unsure"))
    values = [...values, "unsure"];
  return values;
}

export interface WalkSpaceCount {
  /** Exact total walk count, `review_gate`'s 13-way domain included. */
  walksTotalExact: number;
  maxDepth: number;
  nodesReached: ReadonlySet<string>;
  /** First-DFS-visit override path that reaches each reached question id. */
  witnesses: ReadonlyMap<string, Readonly<Record<string, string>>>;
}

/**
 * Exact count of the full walk space via DAG-reduction memoization: two
 * states (`nextNode`, `factsSoFar`) that agree on every
 * `BRANCH_RELEVANT_FACT_KEYS` value share an identical future (`flow.ts`
 * reads no other fact for branching), so their subtree is counted once.
 * Measured under two seconds on the real graph — "proven, not assumed"
 * means this is a real count, not an estimate or a sample.
 *
 * `computeNext` is injectable so a test can hand it a synthetic node
 * function that loops, to exercise the cycle guard without touching the
 * real (acyclic) production graph — defaults to the real `computeNextNode`.
 */
export function countExactWalks(
  computeNext: typeof computeNextNode = computeNextNode,
  declaredCount: number = Object.keys(QUESTIONS).length,
): WalkSpaceCount {
  const memo = new Map<string, { count: number; maxDepth: number }>();
  const nodesReached = new Set<string>();
  const witnesses = new Map<string, Record<string, string>>();

  function memoKey(node: OracleNode, facts: OracleFacts): string {
    const kindPart =
      node.kind === "question" ? `q:${node.questionId}` : node.kind;
    const relevant = BRANCH_RELEVANT_FACT_KEYS.map((k) => facts[k] ?? "").join(
      "|",
    );
    return `${kindPart}#${relevant}`;
  }

  function countFrom(
    node: OracleNode,
    facts: OracleFacts,
    depth: number,
    overridesSoFar: Readonly<Record<string, string>>,
  ): { count: number; maxDepth: number } {
    if (depth > declaredCount + 5) {
      throw new Error(
        `enumerate-interview-space: depth ${depth} exceeds the declared question ` +
          `count (${declaredCount}) — a cycle, not a real interview path`,
      );
    }
    const next = computeNext(node, facts, ENUMERATOR_TODAY);
    if (next.kind !== "question") return { count: 1, maxDepth: depth };

    nodesReached.add(next.questionId);
    if (!witnesses.has(next.questionId))
      witnesses.set(next.questionId, { ...overridesSoFar });

    if (next.questionId === "review_gate") {
      // Orthogonal: every value is a leaf multiplier, never a new subtree —
      // see the module docstring's grep evidence.
      return { count: REVIEW_GATE_ITEMS.length, maxDepth: depth + 1 };
    }

    const key = memoKey(next, facts);
    const cached = memo.get(key);
    if (cached) return cached;

    let total = 0;
    let deepest = depth;
    for (const value of answersFor(next.questionId)) {
      const sub = countFrom(
        next,
        { ...facts, [next.questionId]: value },
        depth + 1,
        { ...overridesSoFar, [next.questionId]: value },
      );
      total += sub.count;
      if (sub.maxDepth > deepest) deepest = sub.maxDepth;
    }
    const result = { count: total, maxDepth: deepest };
    memo.set(key, result);
    return result;
  }

  // `review_gate` is added to `nodesReached` by the normal recursion above
  // (the `nodesReached.add(next.questionId)` call runs before the
  // `review_gate` early-return special case) — no separate line needed, and
  // none was added: a synthetic graph that never reaches it must show up
  // honestly in `unreachable`, both here and in a degenerate test double.
  const { count, maxDepth } = countFrom({ kind: "framing" }, {}, 0, {});
  return { walksTotalExact: count, maxDepth, nodesReached, witnesses };
}

export interface CoveringWalk {
  label: string;
  asked: string[];
  facts: OracleFacts;
}

export interface CoveringSubset {
  walks: CoveringWalk[];
  edgesTotal: number;
  edgesCovered: number;
}

/**
 * A deterministic, provably total-edge-covering subset — see the module
 * docstring. One baseline walk (every question at `answerFor`'s own
 * default), then one targeted walk per still-uncovered `(questionId,
 * answer)` edge: `runWalk({...witness, [questionId]: answer})` replays the
 * FIRST DFS path that reached `questionId` (proven reachable by
 * `countExactWalks`) and then forces the one answer under test, so every
 * OTHER question on that walk still gets its ordinary default. Finally, 12
 * cheap clones of the baseline cover `review_gate`'s 13-item domain (`"none"`
 * is already the baseline's own default).
 */
export function buildCoveringSubset(space: WalkSpaceCount): CoveringSubset {
  const covered = new Set<string>();
  const walks: CoveringWalk[] = [];

  function record(label: string, overrides: Record<string, string>): void {
    const { asked, facts } = runWalk(overrides);
    walks.push({ label, asked, facts });
    for (const id of asked) {
      const value = facts[id];
      if (value !== undefined) covered.add(`${id}=${value}`);
    }
  }

  record("baseline/all-default", {});

  let edgesTotal = 0;
  const reachedIds = [...space.nodesReached]
    .filter((id) => id !== "review_gate")
    .sort();
  for (const id of reachedIds) {
    for (const value of answersFor(id)) {
      edgesTotal += 1;
      if (covered.has(`${id}=${value}`)) continue;
      const witness = space.witnesses.get(id) ?? {};
      record(`edge/${id}=${value}`, { ...witness, [id]: value });
    }
  }

  const baseline = walks[0];
  for (const item of REVIEW_GATE_ITEMS) {
    if (item === "none") continue;
    walks.push({
      label: `review-gate/${item}`,
      asked: baseline.asked,
      facts: { ...baseline.facts, review_gate: item },
    });
  }

  return { walks, edgesTotal, edgesCovered: covered.size };
}

export interface RenderedWalk {
  label: string;
  asked: string[];
  schema_version: string;
  assessment_id: string;
  collected_at: string;
  facts: Record<string, unknown>;
  disclosed_review_flags?: DisclosedReviewFlagWire[];
}

export function renderCoveringWalks(walks: CoveringWalk[]): RenderedWalk[] {
  return walks.map((walk) => {
    const wire = mapOracleFactsToApplicantFacts(walk.facts, {
      assessmentId: ASSESSMENT_ID,
      collectedAt: ENUMERATOR_TODAY,
    });
    return {
      label: walk.label,
      asked: walk.asked,
      schema_version: wire.schema_version,
      assessment_id: wire.assessment_id,
      collected_at: wire.collected_at,
      facts: wire.facts as unknown as Record<string, unknown>,
      ...(wire.disclosed_review_flags.length > 0
        ? { disclosed_review_flags: [...wire.disclosed_review_flags] }
        : {}),
    };
  });
}

export interface Manifest {
  nodesDeclared: number;
  nodesReached: number;
  unreachable: string[];
  maxDepth: number;
  walksTotalExact: number;
  bound: "PROVEN" | "UNPROVEN";
  coveringSubset: {
    seed: string;
    edgesTotal: number;
    edgesCovered: number;
    walks: RenderedWalk[];
  };
}

export function buildManifest(): Manifest {
  const declaredIds = Object.keys(QUESTIONS);
  const space = countExactWalks();
  const unreachable = declaredIds.filter((id) => !space.nodesReached.has(id));
  const subset = buildCoveringSubset(space);
  return {
    nodesDeclared: declaredIds.length,
    nodesReached: space.nodesReached.size,
    unreachable,
    maxDepth: space.maxDepth,
    walksTotalExact: space.walksTotalExact,
    bound: unreachable.length === 0 ? "PROVEN" : "UNPROVEN",
    coveringSubset: {
      seed: "deterministic (no RNG): declared option order + first-DFS-visit witness paths",
      edgesTotal: subset.edgesTotal,
      edgesCovered: subset.edgesCovered,
      walks: renderCoveringWalks(subset.walks),
    },
  };
}

/** The manifest as exact file bytes — same prettier convention as `generate-walk-corpus.ts`. */
export async function renderManifest(manifest: Manifest): Promise<string> {
  return format(JSON.stringify(manifest), { parser: "json" });
}

async function main(argv: string[]): Promise<void> {
  const manifest = buildManifest();
  if (argv.includes("--dry-run")) {
    console.log(
      `walks=${manifest.walksTotalExact} maxDepth=${manifest.maxDepth} bound=${manifest.bound}`,
    );
    process.exitCode = manifest.bound === "PROVEN" ? 0 : 1;
    return;
  }
  const outIndex = argv.indexOf("--out");
  const outPath =
    outIndex >= 0 && argv[outIndex + 1]
      ? resolve(argv[outIndex + 1])
      : DEFAULT_OUT_PATH;
  mkdirSync(dirname(outPath), { recursive: true });
  writeFileSync(outPath, await renderManifest(manifest), "utf8");
  console.log(
    `wrote ${manifest.coveringSubset.walks.length} covering walks to ${outPath} ` +
      `(walksTotalExact=${manifest.walksTotalExact}, bound=${manifest.bound})`,
  );
  if (manifest.bound !== "PROVEN") process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === `file://${process.argv[1]}`) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
