/**
 * Tests for the Slice B1' enumerator (PLAN §3 row B1, criterion G2-a; cured
 * after GATE-B1-REPORT-6842.md's REWORK-BUILD on #6842).
 *
 * Ground-truth strategy: `test_manifest_numbers_match_an_independent_recount`
 * re-derives `walksTotalExact` with a SECOND, differently-written recursion
 * (no memoization, small synthetic sub-graph) rather than re-running the
 * function under test — a test that reimplements the thing it tests in
 * slightly different words only proves self-consistency (cicatrix family
 * #6). Guilt-and-innocence pairs (cicatrix family #3) cover the cycle guard
 * and the blind-scan floor. The memo-recount test further down drives the
 * REAL production `computeNextNode` (wrapped only to bound its scope) over
 * a small sub-space where the memo is proven to actually fire, rather than
 * a fully synthetic topology (GATE-B1-REPORT-6842.md Check 5).
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";
import { validate as uuidValidate, version as uuidVersion } from "uuid";

import {
  answersFor,
  BRANCH_RELEVANT_FACT_KEYS,
  buildCoveringSubset,
  buildManifest,
  countExactWalks,
  dryRunSummary,
  edgeCoverageReport,
  type Manifest,
  REPRESENTATIVE_VALUES,
  renderCoveringWalks,
  renderManifest,
  typedBranchRelevantQuestionIds,
} from "../../../../../scripts/visa-oracle/enumerate-interview-space";
import { CORPUS_TODAY } from "../../../../../scripts/visa-oracle/generate-walk-corpus";
import {
  type BlockedAnswer,
  computeNextNode,
  createInterviewSnapshot,
  flowReducer,
  initialFlowState,
  type OracleNode,
  restoreInterviewSnapshot,
} from "./flow";
import { QUESTIONS } from "./tree";

/**
 * `countExactWalks()`/`buildManifest()` over the REAL 67-node graph are each
 * "measured under two seconds" (module docstring), but several tests below
 * only need to READ the result, not recompute it — computed once here and
 * shared, instead of once per `it()`, so the suite's wall time stays close
 * to a small constant multiple of that single traversal rather than growing
 * with the number of read-only assertions on it. The determinism test below
 * deliberately builds TWICE, fresh — that comparison IS its point.
 */
const REAL_SPACE = countExactWalks();
const REAL_SUBSET = buildCoveringSubset(REAL_SPACE);
const REAL_MANIFEST = buildManifest();

describe("countExactWalks — determinism", () => {
  it("two renders of the full manifest are byte-identical", async () => {
    const first = await renderManifest(buildManifest());
    const second = await renderManifest(buildManifest());
    expect(second).toBe(first);
    // A7-M (2026-09-22, gate `vo-gate-a7-m` L4): `birth_date` joining
    // BRANCH_RELEVANT_FACT_KEYS enlarged the enumerated space enough that
    // this double full-manifest render measured over the prior 30s budget
    // under CI/local load (never a wall-clock cliff of its own — a rerun of
    // the same job went green with no code change). 120s gives the render
    // headroom without hiding a real regression: a genuine correctness
    // break here still fails on the assertion, not the clock.
  }, 120_000);
});

// Hygiene follow-up, not yet built (GATE-A7-M-REPORT-7135.md, option 2): if the enumerated
// space keeps growing (Slice A6-bis is pending and may add more facts to
// BRANCH_RELEVANT_FACT_KEYS), coarsen the memo-key projection for `birth_date` via the
// injection point T1 proved below, rather than bumping this budget again. Not built here —
// A6-bis may move the pins this file carries first, and any re-pin is by command.

describe("countExactWalks — the cycle guard names the repeated node (guilt)", () => {
  it("throws naming the repeated question when a synthetic graph loops", () => {
    // Two REAL question ids (so `answersFor` resolves them against the real
    // `QUESTIONS` table) that ping-pong forever: `in_indonesia` ->
    // `holds_stay_permit` -> `in_indonesia` -> ... — the loop is synthetic
    // (`flow.ts`'s real `computeNextNode` is acyclic), the ids are not.
    const loopingComputeNext = (current: OracleNode): OracleNode => {
      if (current.kind !== "question")
        return { kind: "question", questionId: "in_indonesia" };
      return current.questionId === "in_indonesia"
        ? { kind: "question", questionId: "holds_stay_permit" }
        : { kind: "question", questionId: "in_indonesia" };
    };
    expect(() => countExactWalks(loopingComputeNext, 5)).toThrow(
      /"in_indonesia" repeats within a single walk/,
    );
  });

  it("the depth ceiling is a second fence, distinct from the repeated-node check", () => {
    // A synthetic transition that walks a fixed CHAIN of 15 distinct REAL
    // question ids (each id used at most once, so `answersFor` resolves
    // every one against the live QUESTIONS table and the path check never
    // fires) longer than `declaredCount + 5` — only the depth ceiling can
    // stop it, and its message must not claim a repeat it never found.
    const chain = Object.keys(QUESTIONS).slice(0, 15);
    const linearChain = (current: OracleNode): OracleNode => {
      if (current.kind !== "question")
        return { kind: "question", questionId: chain[0] };
      const index = chain.indexOf(current.questionId);
      if (index === -1 || index === chain.length - 1)
        return { kind: "verdict" };
      return { kind: "question", questionId: chain[index + 1] };
    };
    expect(() => countExactWalks(linearChain, 3)).toThrow(
      /depth \d+ exceeds the declared question count \(3\)/,
    );
  });
});

describe("countExactWalks — the blind-scan floor (innocence + guilt)", () => {
  it("a synthetic graph that reaches nothing reports zero nodes and every declared id unreachable", () => {
    const deadOnArrival = (): OracleNode => ({ kind: "verdict" });
    const space = countExactWalks(deadOnArrival, 5);
    expect(space.walksTotalExact).toBe(1);
    expect(space.nodesReached.size).toBe(0);
    const declared = Object.keys(QUESTIONS);
    const unreachable = declared.filter((id) => !space.nodesReached.has(id));
    expect(unreachable).toEqual(declared);
  });

  it("the real production graph reaches every declared question (innocence)", () => {
    const declared = Object.keys(QUESTIONS);
    const unreachable = declared.filter(
      (id) => !REAL_SPACE.nodesReached.has(id),
    );
    expect(unreachable).toEqual([]);
    expect(REAL_SPACE.nodesReached.size).toBe(declared.length);
  });
});

describe("BRANCH_RELEVANT_FACT_KEYS covers every fact flow.ts actually reads", () => {
  it("matches a fresh grep of the live source (guilt if the table under-declares)", () => {
    const flowSource = readFileSync(join(__dirname, "flow.ts"), "utf8");
    const dotReads = new Set(
      [...flowSource.matchAll(/facts\.([a-zA-Z_]+)/g)].map((m) => m[1]),
    );
    // The one dynamic bracket read this file is known to have
    // (`investmentRouteQuestionIds`'s `routes.some((id) => facts[id] ===
    // "yes")`) is not statically greppable by key name, so it is asserted
    // by name instead of re-derived.
    const dynamicReads = [
      "investment_foreign_branch",
      "investment_ikn_subsidiary",
    ];
    const allReads = new Set([...dotReads, ...dynamicReads]);
    const declaredSet = new Set(BRANCH_RELEVANT_FACT_KEYS);
    const missing = [...allReads].filter((key) => !declaredSet.has(key));
    expect(missing).toEqual([]);
  });
});

describe("REPRESENTATIVE_VALUES is complete (GATE-B1-REPORT-6842.md Check 2, MEDIUM-1)", () => {
  it("covers every typed (options: []) question that is also branch-relevant, naming any it is missing", () => {
    const required = typedBranchRelevantQuestionIds();
    const declared = new Set(Object.keys(REPRESENTATIVE_VALUES));
    const missing = required.filter((id) => !declared.has(id));
    expect(missing).toEqual([]);
  });

  it("typedBranchRelevantQuestionIds finds the four known thresholds (not a stale hardcoded pair)", () => {
    // Slice A7-M (2026-09-22): `birth_date` (kind "date") joins
    // `BRANCH_RELEVANT_FACT_KEYS` — `flow.ts` now branches on it (minor vs
    // adult) — so it joins this typed set too.
    expect(typedBranchRelevantQuestionIds()).toEqual(
      [
        "birth_date",
        "family_sponsor_nationalities",
        "permit_expiry",
        "stay_days",
      ].sort(),
    );
  });

  it('family_sponsor_nationalities brackets flow.ts\'s !sponsorCodes.includes("ID") threshold', () => {
    const values = REPRESENTATIVE_VALUES.family_sponsor_nationalities;
    expect(values).toContain("IT"); // definite non-Indonesian sponsor (true arm)
    expect(values).toContain("ID"); // definite Indonesian (WNI) sponsor (false arm)
    expect(values).toContain("ID,IT"); // the comma-split multi-code shape
  });
});

describe("answersFor — every declared option and unsure", () => {
  it("a question with declared options and notSure returns every option plus unsure", () => {
    const values = answersFor("in_indonesia", {});
    expect(values).toEqual(["yes", "no", "unsure"]);
  });

  it("review_gate returns its real wire domain (REVIEW_GATE_ITEMS), not its own two-option UI gate", () => {
    const values = answersFor("review_gate", {});
    expect(values).toContain("none");
    expect(values).toContain("criminal_record");
    expect(values.length).toBe(13);
  });
});

describe("answersFor — application_channel is filtered by wants_onshore_conversion (Slice B5-1, Y1)", () => {
  it("excludes OFFSHORE when wants_onshore_conversion is yes", () => {
    const values = answersFor("application_channel", {
      wants_onshore_conversion: "yes",
    });
    expect(values).not.toContain("OFFSHORE");
    expect(values).toEqual(
      expect.arrayContaining([
        "ONSHORE_CONVERSION",
        "STATUS_BRIDGING",
        "unsure",
      ]),
    );
  });

  it("excludes the two ONSHORE channels when wants_onshore_conversion is no", () => {
    const values = answersFor("application_channel", {
      wants_onshore_conversion: "no",
    });
    expect(values).not.toContain("ONSHORE_CONVERSION");
    expect(values).not.toContain("STATUS_BRIDGING");
    expect(values).toEqual(expect.arrayContaining(["OFFSHORE", "unsure"]));
  });

  it("is unfiltered when wants_onshore_conversion is absent or unsure (the guard's own tri-state exemption)", () => {
    const withNoFact = answersFor("application_channel", {});
    const withUnsure = answersFor("application_channel", {
      wants_onshore_conversion: "unsure",
    });
    const full = [
      "OFFSHORE",
      "ONSHORE_CONVERSION",
      "STATUS_BRIDGING",
      "unsure",
    ];
    expect(withNoFact.sort()).toEqual([...full].sort());
    expect(withUnsure.sort()).toEqual([...full].sort());
  });

  it("never filters any OTHER question id, even one that happens to share the fact key (byte-identical domain)", () => {
    const withoutFacts = answersFor("wants_onshore_conversion", {});
    const withUnrelatedFacts = answersFor("wants_onshore_conversion", {
      wants_onshore_conversion: "yes",
    });
    expect(withUnrelatedFacts).toEqual(withoutFacts);
  });
});

describe("buildCoveringSubset — a certain WNI sponsor walk exists (GATE-B1-REPORT-6842.md Check 2)", () => {
  it("emits at least one walk with a CERTAIN Indonesian (WNI) sponsor and no unsure anywhere in its facts", () => {
    const hasCertainWniSponsorWalk = REAL_SUBSET.walks.some((walk) => {
      const sponsor = walk.facts.family_sponsor_nationalities;
      if (sponsor === undefined || sponsor === "unsure") return false;
      const codes = sponsor.split(",");
      if (!codes.includes("ID")) return false;
      return !Object.values(walk.facts).includes("unsure");
    });
    expect(hasCertainWniSponsorWalk).toBe(true);
  });
});

describe("buildCoveringSubset — total edge coverage", () => {
  it("covers every declared option of a known branching node (holds_stay_permit) in at least one walk", () => {
    const seen = new Set<string>();
    for (const walk of REAL_SUBSET.walks) {
      const value = walk.facts.holds_stay_permit;
      if (value !== undefined) seen.add(value);
    }
    for (const option of answersFor("holds_stay_permit", {})) {
      expect(seen.has(option)).toBe(true);
    }
  });

  it("required minus actual is empty — zero missing edges (GATE-B1-REPORT-6842.md Check 4, MEDIUM-2)", () => {
    // A SET comparison, not a size comparison: the old test asserted
    // `edgesCovered >= edgesTotal` over two DIFFERENT id sets, which could
    // not go red on a real miss. `edgesMissing` is `required \ actual`.
    expect(REAL_SUBSET.edgesMissing).toEqual([]);
    expect(REAL_SUBSET.edgesExtra).toEqual([]);
    expect(REAL_SUBSET.edgesCovered).toBe(REAL_SUBSET.edgesRequired);
  });

  it("guilt: dropping the sole walk carrying family_sponsor_nationalities=ID turns edgesMissing red, naming it", () => {
    const targetLabel = "edge/family_sponsor_nationalities=ID";
    const target = REAL_SUBSET.walks.find((walk) => walk.label === targetLabel);
    expect(target).toBeDefined();
    const withoutIt = REAL_SUBSET.walks.filter(
      (walk) => walk.label !== targetLabel,
    );
    const report = edgeCoverageReport(REAL_SPACE.edgesReachable, withoutIt);
    expect(report.edgesMissing).toEqual(["family_sponsor_nationalities=ID"]);
  });

  it("is not empty (blind-scan floor: zero walks is a defect, not a valid output)", () => {
    expect(REAL_SUBSET.walks.length).toBeGreaterThan(0);
  });
});

/**
 * Generous but bounded: `REAL_SPACE.maxDepth` (26, measured) is the deepest
 * the real graph goes from `framing`; this leaves headroom for the ADVANCE
 * steps between questions without masking a genuine infinite loop as a slow
 * test.
 */
const MAX_DRIVE_STEPS = 60;

/**
 * Replays ONE covering walk's `facts` through the REAL `flowReducer`, from a
 * fresh `initialFlowState`, `SKIP` for `"unsure"` and `ANSWER` otherwise —
 * the two actions a real applicant's browser ever sends. Stops early (with
 * `blocked` set) the moment the reducer refuses an answer, exactly like the
 * live UI would; otherwise drives to `verdict` and then round-trips a
 * snapshot through `createInterviewSnapshot` -> JSON -> `restoreInterviewSnapshot`,
 * reporting whether THAT path also lands on `verdict`. Deliberately does not
 * exercise `SELECT_CATEGORY`, `ASK_FOLLOW_UP`, `BACK` or `EDIT` — this
 * walk-replay only ever moves forward, one question at a time, which is all
 * a covering walk's linear `asked`/`facts` pair can drive.
 */
function driveWalkThroughReducer(walk: {
  label: string;
  facts: Record<string, string>;
}): { label: string; blocked: BlockedAnswer | null; restoredVerdict: boolean } {
  let state = initialFlowState("en");
  state = flowReducer(state, { type: "ADVANCE" });
  for (let step = 0; step < MAX_DRIVE_STEPS; step += 1) {
    const head = state.history[state.history.length - 1];
    if (head.kind === "verdict") break;
    if (head.kind !== "question") {
      state = flowReducer(state, { type: "ADVANCE" });
      continue;
    }
    const value = walk.facts[head.questionId];
    if (value === undefined) {
      throw new Error(
        `walk "${walk.label}" asks "${head.questionId}" but its facts carry no answer for it`,
      );
    }
    state =
      value === "unsure"
        ? flowReducer(state, {
            type: "SKIP",
            questionId: head.questionId,
            today: CORPUS_TODAY,
          })
        : flowReducer(state, {
            type: "ANSWER",
            questionId: head.questionId,
            value,
            today: CORPUS_TODAY,
          });
    if (state.blockedAnswer) {
      return {
        label: walk.label,
        blocked: state.blockedAnswer,
        restoredVerdict: false,
      };
    }
  }
  const head = state.history[state.history.length - 1];
  if (head.kind !== "verdict") {
    throw new Error(
      `walk "${walk.label}" never reached a verdict within ${MAX_DRIVE_STEPS} steps ` +
        `(stopped on "${head.kind === "question" ? head.questionId : head.kind}")`,
    );
  }
  const snapshot = createInterviewSnapshot(state, CORPUS_TODAY);
  const roundTripped = JSON.parse(JSON.stringify(snapshot));
  const restored = restoreInterviewSnapshot(roundTripped, "en", CORPUS_TODAY);
  const restoredHead = restored?.history[restored.history.length - 1];
  return {
    label: walk.label,
    blocked: null,
    restoredVerdict: restoredHead?.kind === "verdict",
  };
}

describe("Y3 — every covering walk reaches a verdict through flowReducer AND through the resume snapshot (Slice B5-1)", () => {
  it("reached === covering, both the reducer path and the snapshot-restore path (innocence)", () => {
    const walks = REAL_SUBSET.walks;
    const results = walks.map(driveWalkThroughReducer);
    const blocked = results.filter((result) => result.blocked !== null);
    if (blocked.length > 0) {
      const pairs = new Set(
        blocked.map(
          (result) =>
            `${result.blocked!.questionId} vs ${result.blocked!.conflictsWithQuestionId}`,
        ),
      );
      throw new Error(
        `${blocked.length} of ${walks.length} covering walks were blocked by flowReducer: ${[
          ...pairs,
        ].join(", ")}`,
      );
    }
    const reached = results.filter((result) => result.restoredVerdict).length;
    expect(reached).toBe(walks.length);
  });
});

describe("Y3b — the derived refusable-question-id set is exactly {application_channel}, cardinality 1 (Slice B5-1)", () => {
  it("probing every value of every asked question, over every covering walk, only application_channel ever blocks", () => {
    const refusableIds = new Set<string>();
    for (const walk of REAL_SUBSET.walks) {
      let state = initialFlowState("en");
      state = flowReducer(state, { type: "ADVANCE" });
      for (let step = 0; step < MAX_DRIVE_STEPS; step += 1) {
        const head = state.history[state.history.length - 1];
        if (head.kind === "verdict") break;
        if (head.kind !== "question") {
          state = flowReducer(state, { type: "ADVANCE" });
          continue;
        }
        const questionId = head.questionId;
        // The FULL declared domain, unfiltered (`{}`, never `state.facts`):
        // Y1's own filter already removes a conflicting value from what
        // `answersFor(id, state.facts)` would offer, so probing THAT
        // output could never surface application_channel's own refusal —
        // it would prove only that the enumerator never asks for what it
        // already knows is blocked, not what the REDUCER itself refuses.
        // `answersFor(id, {})` is byte-identical to `answersFor(id,
        // anyFacts)` for every id but application_channel (module
        // docstring), so this stays a faithful probe for every OTHER id.
        for (const value of answersFor(questionId, {})) {
          const trial = flowReducer(state, {
            type: "ANSWER",
            questionId,
            value,
            today: CORPUS_TODAY,
          });
          if (trial.blockedAnswer)
            refusableIds.add(trial.blockedAnswer.questionId);
        }
        const actualValue = walk.facts[questionId];
        if (actualValue === undefined) {
          throw new Error(
            `walk "${walk.label}" asks "${questionId}" but its facts carry no answer for it`,
          );
        }
        state =
          actualValue === "unsure"
            ? flowReducer(state, {
                type: "SKIP",
                questionId,
                today: CORPUS_TODAY,
              })
            : flowReducer(state, {
                type: "ANSWER",
                questionId,
                value: actualValue,
                today: CORPUS_TODAY,
              });
      }
    }
    const refusable = [...refusableIds].sort();
    // The cardinality below is a LITERAL, never derived from
    // BRANCH_RELEVANT_FACT_KEYS or any other table under test (GATE-A2G
    // OBS-A2g-4): a second refusal guard added anywhere in flowReducer must
    // move this literal, by hand, for the test to keep passing — it cannot
    // silently absorb a new guard the way a `.length`-derived bound could.
    expect(refusable.length).toBe(1);
    expect(refusable).toEqual(["application_channel"]);
  });
});

describe("Y4 — the guard's own fact-key input stays inside BRANCH_RELEVANT_FACT_KEYS (memo soundness, Slice B5-1)", () => {
  it("wants_onshore_conversion — the only fact channelConflictsWithOnshoreIntent reads — is a declared member", () => {
    // A literal, not derived from channelConflictsWithOnshoreIntent's own
    // source: the function takes wantsOnshoreConversion as a parameter, so
    // the fact key it depends on is named here, at the one call site
    // (`answersFor`) that reads it out of `facts`.
    const guardFactKeys = ["wants_onshore_conversion"];
    const declared = new Set(BRANCH_RELEVANT_FACT_KEYS);
    const missing = guardFactKeys.filter((key) => !declared.has(key));
    expect(missing).toEqual([]);
  });
});

describe("dryRunSummary — exits non-zero when an edge is missing (GATE-B1-REPORT-6842.md Check 4)", () => {
  it("a fully covered, PROVEN manifest is ok", () => {
    const { ok } = dryRunSummary(REAL_MANIFEST);
    expect(ok).toBe(true);
  });

  it("a manifest with a missing edge is NOT ok, even if bound is PROVEN", () => {
    const broken: Manifest = {
      ...REAL_MANIFEST,
      coveringSubset: {
        ...REAL_MANIFEST.coveringSubset,
        edgesMissing: ["fake_id=fake_value"],
      },
    };
    const { ok } = dryRunSummary(broken);
    expect(ok).toBe(false);
  });

  it("an UNPROVEN manifest is NOT ok, even with zero missing edges", () => {
    const broken: Manifest = {
      ...REAL_MANIFEST,
      bound: "UNPROVEN",
      unreachable: ["some_id"],
    };
    const { ok } = dryRunSummary(broken);
    expect(ok).toBe(false);
  });
});

describe("manifest numbers match an independent recount", () => {
  it("re-derives walksTotalExact with a SEPARATE, unmemoized recursion over a SYNTHETIC 2-level topology", () => {
    // Independent of `countExactWalks`'s own memoized implementation: a
    // plain, brute-force recursive count over a 2-level synthetic graph
    // (3 options at the first question, 2 at the second = 6 total walks),
    // proving the COUNTING LOGIC itself (sum over every child) is sound,
    // not re-running the function under test on the same input. Neither the
    // transition function nor the question ids are real.
    const synthetic = (current: OracleNode): OracleNode => {
      if (current.kind !== "question")
        return { kind: "question", questionId: "first" };
      if (current.questionId === "first")
        return { kind: "question", questionId: "second" };
      return { kind: "verdict" };
    };
    const optionsFor: Record<string, string[]> = {
      first: ["a", "b", "c"],
      second: ["x", "y"],
    };
    function bruteForceCount(node: OracleNode, depth: number): number {
      if (depth > 10) throw new Error("cycle");
      const next = synthetic(node);
      if (next.kind !== "question") return 1;
      let total = 0;
      for (const _value of optionsFor[next.questionId]) {
        total += bruteForceCount(next, depth + 1);
      }
      return total;
    }
    const independentCount = bruteForceCount({ kind: "framing" }, 0);
    expect(independentCount).toBe(6);
  });

  it("the manifest's walksTotalExact matches countExactWalks's own return value (self-consistency, not independence)", () => {
    expect(REAL_MANIFEST.walksTotalExact).toBe(REAL_SPACE.walksTotalExact);
    expect(REAL_MANIFEST.nodesReached).toBe(REAL_SPACE.nodesReached.size);
    expect(REAL_MANIFEST.maxDepth).toBe(REAL_SPACE.maxDepth);
  });

  it("countExactWalks reproduces a hand-computed count on a SYNTHETIC two-level topology built from two real question ids", () => {
    // Unlike the two cases above (a self-standing brute force that never
    // touches countExactWalks, and a re-run of the function under test on
    // the same input), THIS drives countExactWalks itself — the memoized
    // DAG-reduction under test — through a controlled two-level topology.
    // The TRANSITION FUNCTION is synthetic (it ignores every answer and
    // always walks framing -> in_indonesia -> holds_stay_permit -> verdict);
    // only the two question ids (in_indonesia, holds_stay_permit) are real,
    // used so `answersFor` resolves them against the live QUESTIONS table.
    // in_indonesia and holds_stay_permit each declare 2 options plus
    // notSure (asserted above: ["yes","no","unsure"]), so this topology has
    // EXACTLY 3 * 3 = 9 walks, independent of countExactWalks's own
    // memoization or summation logic.
    const twoLevelSynthetic = (current: OracleNode): OracleNode => {
      if (current.kind !== "question")
        return { kind: "question", questionId: "in_indonesia" };
      if (current.questionId === "in_indonesia")
        return { kind: "question", questionId: "holds_stay_permit" };
      return { kind: "verdict" };
    };
    const expected =
      answersFor("in_indonesia", {}).length *
      answersFor("holds_stay_permit", {}).length;
    expect(expected).toBe(9);
    const space = countExactWalks(twoLevelSynthetic, 5);
    expect(space.walksTotalExact).toBe(expected);
  });

  describe("the memo actually fires on a BOUNDED REAL sub-space (GATE-B1-REPORT-6842.md Check 5, MEDIUM-3)", () => {
    // Unlike the three cases above (two fully synthetic transition
    // functions, one self-consistency check), this wraps the REAL
    // production `computeNextNode` — its branching decisions are not
    // reimplemented — and only bounds WHERE it is allowed to go, so the
    // sub-space stays small enough to recount by hand and run in
    // milliseconds. `marital_status` is not in `BRANCH_RELEVANT_FACT_KEYS`
    // (flow.ts never branches on it), so all 6 of its answers converge on
    // the IDENTICAL next state (same node, same relevant facts) reached
    // right after it — a REAL memo-reuse opportunity, not a contrived one.
    const REAL_SUBGRAPH_IDS = new Set([
      "marital_status",
      "family_sponsor_nationalities",
    ]);
    const boundedReal = (
      node: OracleNode,
      facts: Record<string, string>,
      today?: Date,
    ): OracleNode => {
      const next = computeNextNode(node, facts, today);
      if (next.kind === "question" && !REAL_SUBGRAPH_IDS.has(next.questionId)) {
        return { kind: "verdict" };
      }
      return next;
    };
    const START = {
      node: { kind: "question" as const, questionId: "family_relation" },
      facts: { category: "family" },
    };
    const TODAY = new Date("2026-09-06T00:00:00Z");

    it("counts 6 (marital_status) x 4 (family_sponsor_nationalities) = 24 walks, with the memo reused at least once", () => {
      const memoStats = { hits: 0 };
      const space = countExactWalks(boundedReal, 10, {
        start: START,
        memoStats,
      });
      expect(answersFor("marital_status", {}).length).toBe(6);
      expect(answersFor("family_sponsor_nationalities", {}).length).toBe(4);
      expect(space.walksTotalExact).toBe(24);
      // The reuse is not incidental: all 6 marital_status branches reach
      // the SAME memoized family_sponsor_nationalities state, so exactly
      // 5 of the 6 are cache hits (the topology cannot pass this on a
      // memo-degenerate case, since a broken/never-reused memo key would
      // report 0 hits here).
      expect(memoStats.hits).toBe(5);
    }, 5_000);

    it("an UNMEMOIZED plain recursion over the SAME wrapped production computeNextNode agrees exactly", () => {
      function bruteForceReal(
        node: OracleNode,
        facts: Record<string, string>,
        depth: number,
      ): number {
        if (depth > 10) throw new Error("cycle");
        const next = boundedReal(node, facts, TODAY);
        if (next.kind !== "question") return 1;
        let total = 0;
        for (const value of answersFor(next.questionId, facts)) {
          total += bruteForceReal(
            next,
            { ...facts, [next.questionId]: value },
            depth + 1,
          );
        }
        return total;
      }
      const independent = bruteForceReal(START.node, START.facts, 0);
      const memoized = countExactWalks(boundedReal, 10, { start: START });
      expect(independent).toBe(24);
      expect(memoized.walksTotalExact).toBe(independent);
    }, 5_000);
  });
});

describe("the memo-key projection is injectable, and a guilt/innocence PAIR proves it matters (GATE-B1C-REPORT-6848.md Check 4, MEDIUM-1)", () => {
  // GATE-B1C-REPORT-6848.md measured that R3's own sub-space (marital_status
  // x family_sponsor_nationalities) proves reuse HAPPENED but can never prove
  // reuse was CORRECT: dropping `business_activity` from `memoKey`'s
  // projection on a COPY moved `walksTotalExact` by 16,055,337,168 while
  // every existing test stayed green, because `family_sponsor_nationalities`
  // branches at its OWN immediate successor — two states that would collide
  // under a corrupted key already differ in node identity, so no single key
  // drop there can ever go undetected. This pair targets the class the gate
  // named: `flow.ts:1087`'s `category === "business" && facts.
  // business_activity === "exploring"` selects a whole different downstream
  // question SEQUENCE (`businessExplorerQuestionIds` vs
  // `FIXED_CATEGORY_QUESTIONS.business`), and BOTH sequences pass through a
  // node named "stay_days" — the SAME node identity, reached by genuinely
  // different futures. Only `business_activity` (answered well before
  // "stay_days" is reached) tells those futures apart, so dropping it from
  // the projection is exactly the under-projection bug class this pair
  // exists to catch.
  //
  // Bounded via the same wrapped-`computeNextNode` idiom as the R3 pair
  // above: real ids, real branching logic, real `answersFor` domains — only
  // the REACHABLE SET is capped, to `review_gate`'s leaf multiplier
  // deliberately excluded (kept small enough to hand-verify: the two
  // sequences already disagree well before it).
  const REAL_SUBGRAPH_IDS = new Set([
    "business_activity",
    "business_sponsor_confirmed",
    "work_indonesia_compensation",
    "stay_days",
    "entry_pattern",
  ]);
  const boundedReal = (
    node: OracleNode,
    facts: Record<string, string>,
    today?: Date,
  ): OracleNode => {
    const next = computeNextNode(node, facts, today);
    if (next.kind === "question" && !REAL_SUBGRAPH_IDS.has(next.questionId)) {
      return { kind: "verdict" };
    }
    return next;
  };
  // Start one node BEFORE `business_activity` (real production entry into a
  // BUSINESS-category interview: `trip_scope` -> `getCategoryQuestionIds`'s
  // first id, `business_activity`, for either sequence) with `in_indonesia:
  // "yes"` so the offshore-only `wants_onshore_conversion` branch never
  // enters this sub-space, keeping it to exactly the divergence under test.
  const START = {
    node: { kind: "question" as const, questionId: "trip_scope" },
    facts: { in_indonesia: "yes", category: "business" },
  };
  const TODAY = new Date("2026-09-06T00:00:00Z");

  function bruteForceReal(
    node: OracleNode,
    facts: Record<string, string>,
    depth: number,
  ): number {
    if (depth > 15) throw new Error("cycle");
    const next = boundedReal(node, facts, TODAY);
    if (next.kind !== "question") return 1;
    let total = 0;
    for (const value of answersFor(next.questionId, facts)) {
      total += bruteForceReal(
        next,
        { ...facts, [next.questionId]: value },
        depth + 1,
      );
    }
    return total;
  }

  it("innocence: with the FULL (default) projection, memoised equals an independent unmemoised recursion, and the memo actually fires", () => {
    const memoStats = { hits: 0 };
    const memoised = countExactWalks(boundedReal, 15, {
      start: START,
      memoStats,
    });
    const unmemoised = bruteForceReal(START.node, START.facts, 0);
    expect(memoStats.hits).toBeGreaterThan(0);
    expect(memoised.walksTotalExact).toBe(unmemoised);
  }, 5_000);

  it("guilt: dropping business_activity from the projection makes memoised diverge from the SAME unmemoised recursion", () => {
    const corruptedProjection = BRANCH_RELEVANT_FACT_KEYS.filter(
      (key) => key !== "business_activity",
    );
    expect(corruptedProjection.length).toBe(
      BRANCH_RELEVANT_FACT_KEYS.length - 1,
    );
    const memoised = countExactWalks(boundedReal, 15, {
      start: START,
      memoProjection: corruptedProjection,
    });
    const unmemoised = bruteForceReal(START.node, START.facts, 0);
    expect(memoised.walksTotalExact).not.toBe(unmemoised);
  }, 5_000);

  it("the full graph's memoProjection defaults to BRANCH_RELEVANT_FACT_KEYS — production numbers are unaffected by this injection point", () => {
    const withDefault = countExactWalks();
    const withExplicitDefault = countExactWalks(computeNextNode, undefined, {
      memoProjection: BRANCH_RELEVANT_FACT_KEYS,
    });
    expect(withExplicitDefault.walksTotalExact).toBe(
      withDefault.walksTotalExact,
    );
    // Same A7-M/L4 budget bump as the determinism test above — two full
    // countExactWalks() runs over the now-larger space, same cause.
  }, 120_000);
});

describe("renderCoveringWalks — assessment_id is a per-walk deterministic UUID (B2''-c C2)", () => {
  // The engine's ApplicantFacts.assessment_id is a uuid.UUID (models.py
  // ~line 1283); the emitter used to hardcode ASSESSMENT_ID = "x" for every
  // walk, which is not a UUID at all and tripped the live runner's breaker
  // at request 3 (all http_422/uuid_parsing). This suite pins the fix: every
  // rendered walk gets its OWN valid v5 UUID, derived from its label, so the
  // SAME label always yields the SAME id (determinism keeps the manifest
  // byte-stable across runs — the B1'' memo-key projection is unaffected).
  const RENDERED = renderCoveringWalks(REAL_SUBSET.walks);

  // A6-bis (mouth slice, PLAN-ratified, not yet merged) adds two more "Not sure" defaults and may
  // move this pinned literal — do not re-pin speculatively; re-measure and re-pin only when
  // A6-bis lands, by command (MANDATE-vo.md, row 4 "enumeration memo-space").
  it("cardinality: the covering subset renders exactly 254 walks (pinned literal, re-measured after Slice A7-M's birth_date branch)", () => {
    // Slice A7-M (2026-09-22): `birth_date` joins `BRANCH_RELEVANT_FACT_KEYS`
    // with two representative values (adult, minor) — 252 → 254.
    expect(RENDERED.length).toBe(254);
  });

  it("guilt+innocence: every rendered walk's assessment_id is a valid v5 UUID", () => {
    for (const walk of RENDERED) {
      expect(uuidValidate(walk.assessment_id)).toBe(true);
      expect(uuidVersion(walk.assessment_id)).toBe(5);
    }
  });

  it("guilt+innocence: assessment_id is unique across the covering subset", () => {
    const ids = RENDERED.map((walk) => walk.assessment_id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("determinism: the same label yields the same assessment_id across two independent enumerations", () => {
    const firstRun = renderCoveringWalks(REAL_SUBSET.walks);
    const secondRun = renderCoveringWalks(
      buildCoveringSubset(REAL_SPACE).walks,
    );
    expect(firstRun.length).toBe(secondRun.length);
    const byLabel = new Map(
      secondRun.map((walk) => [walk.label, walk.assessment_id]),
    );
    for (const walk of firstRun) {
      expect(byLabel.get(walk.label)).toBe(walk.assessment_id);
    }
  });

  it("guilt: the module's OWN first rendered walk names itself if assessment_id regresses to the pre-fix placeholder (GATE-B2C-REPORT-6972-6970.md OBS-C2-1)", () => {
    // OBS-C2-1 found the previous version of this test tautological: it
    // corrupted an array it built itself and re-implemented the assertion
    // inline, so nothing it asserted depended on renderCoveringWalks at
    // all — measured to stay GREEN under the real `assessmentIdFor`
    // mutation while the guilt+innocence tests above went red. This
    // version reads ONLY RENDERED[0] — the real, unmodified first element
    // of renderCoveringWalks(REAL_SUBSET.walks) — so a real regression to
    // `ASSESSMENT_ID = "x"` changes what THIS line reads, and the throw
    // below fires naming the walk by its own label, not a hand-built one.
    const firstWalk = RENDERED[0];
    if (!uuidValidate(firstWalk.assessment_id)) {
      throw new Error(
        `assessment_id is not a valid UUID for walk "${firstWalk.label}": ${firstWalk.assessment_id}`,
      );
    }
    expect(uuidValidate(firstWalk.assessment_id)).toBe(true);
  });
});

/**
 * Y11 — the label-truth invariant (B5-2 amendment, `Y2 ADJUDICATED`,
 * 2026-09-21). `buildCoveringSubset` labels each edge-targeted walk
 * `edge/<id>=<value>` and each review-gate walk `review-gate/<item>`; the
 * label is a CLAIM about what the walk's own `facts` carry, and nothing
 * upstream re-checks it against the walk that was actually recorded.
 * `Y2 ADJUDICATED` measured that on all 317 declared edges exactly ONE
 * (`application_channel=OFFSHORE`) needs its per-EDGE witness rather than
 * the per-QUESTION one — the two agree everywhere else, so a regression to
 * the per-question witness stays invisible to every OTHER assertion in this
 * file (cardinality holds, edge coverage holds) and is caught only here, by
 * name.
 */
describe("Y11 — the label-truth invariant (Slice B5-2, Y2 ADJUDICATED)", () => {
  it("innocence: every edge/<id>=<value> walk's own facts carry that value, and every review-gate/<item> walk's own facts carry review_gate=<item>", () => {
    let edgeWalks = 0;
    let reviewGateWalks = 0;
    for (const walk of REAL_SUBSET.walks) {
      if (walk.label.startsWith("edge/")) {
        edgeWalks += 1;
        const edge = walk.label.slice("edge/".length);
        const splitAt = edge.indexOf("=");
        const id = edge.slice(0, splitAt);
        const value = edge.slice(splitAt + 1);
        expect(walk.facts[id]).toBe(value);
      } else if (walk.label.startsWith("review-gate/")) {
        reviewGateWalks += 1;
        const item = walk.label.slice("review-gate/".length);
        expect(walk.facts.review_gate).toBe(item);
      }
    }
    // Blind-scan floor: a filter that silently matched nothing would leave
    // the loop above green on zero iterations.
    expect(edgeWalks).toBeGreaterThan(0);
    expect(reviewGateWalks).toBeGreaterThan(0);
  });
});
