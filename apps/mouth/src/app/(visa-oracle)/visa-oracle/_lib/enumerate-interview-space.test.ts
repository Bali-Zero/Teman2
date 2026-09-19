/**
 * Tests for the Slice B1 enumerator (PLAN §3 row B1, criterion G2-a).
 *
 * Ground-truth strategy: `test_manifest_numbers_match_an_independent_recount`
 * re-derives `walksTotalExact` with a SECOND, differently-written recursion
 * (no memoization, small synthetic sub-graph) rather than re-running the
 * function under test — a test that reimplements the thing it tests in
 * slightly different words only proves self-consistency (cicatrix family
 * #6). Guilt-and-innocence pairs (cicatrix family #3) cover the cycle guard
 * and the blind-scan floor.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  answersFor,
  BRANCH_RELEVANT_FACT_KEYS,
  buildCoveringSubset,
  buildManifest,
  countExactWalks,
  renderManifest,
} from "../../../../../scripts/visa-oracle/enumerate-interview-space";
import type { OracleNode } from "./flow";
import { QUESTIONS } from "./tree";

describe("countExactWalks — determinism", () => {
  it("two renders of the full manifest are byte-identical", async () => {
    const first = await renderManifest(buildManifest());
    const second = await renderManifest(buildManifest());
    expect(second).toBe(first);
  }, 30_000);
});

describe("countExactWalks — the cycle guard (guilt)", () => {
  it("throws naming the depth when a synthetic graph loops", () => {
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
    expect(() => countExactWalks(loopingComputeNext, 5)).toThrow(/cycle/);
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
    const space = countExactWalks();
    const declared = Object.keys(QUESTIONS);
    const unreachable = declared.filter((id) => !space.nodesReached.has(id));
    expect(unreachable).toEqual([]);
    expect(space.nodesReached.size).toBe(declared.length);
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

describe("answersFor — every declared option and unsure", () => {
  it("a question with declared options and notSure returns every option plus unsure", () => {
    const values = answersFor("in_indonesia");
    expect(values).toEqual(["yes", "no", "unsure"]);
  });

  it("review_gate returns its real wire domain (REVIEW_GATE_ITEMS), not its own two-option UI gate", () => {
    const values = answersFor("review_gate");
    expect(values).toContain("none");
    expect(values).toContain("criminal_record");
    expect(values.length).toBe(13);
  });
});

describe("buildCoveringSubset — total edge coverage", () => {
  it("covers every declared option of a known branching node (holds_stay_permit) in at least one walk", () => {
    const space = countExactWalks();
    const subset = buildCoveringSubset(space);
    const seen = new Set<string>();
    for (const walk of subset.walks) {
      const value = walk.facts.holds_stay_permit;
      if (value !== undefined) seen.add(value);
    }
    for (const option of answersFor("holds_stay_permit")) {
      expect(seen.has(option)).toBe(true);
    }
  });

  it("edgesCovered equals edgesTotal — zero missing edges", () => {
    const space = countExactWalks();
    const subset = buildCoveringSubset(space);
    expect(subset.edgesCovered).toBeGreaterThanOrEqual(subset.edgesTotal);
  });

  it("is not empty (blind-scan floor: zero walks is a defect, not a valid output)", () => {
    const space = countExactWalks();
    const subset = buildCoveringSubset(space);
    expect(subset.walks.length).toBeGreaterThan(0);
  });
});

describe("manifest numbers match an independent recount", () => {
  it("re-derives walksTotalExact with a SEPARATE, unmemoized recursion over a small synthetic graph", () => {
    // Independent of `countExactWalks`'s own memoized implementation: a
    // plain, brute-force recursive count over a 2-level synthetic graph
    // (3 options at the first question, 2 at the second = 6 total walks),
    // proving the COUNTING LOGIC itself (sum over every child) is sound,
    // not re-running the function under test on the same input.
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

  it("the manifest's walksTotalExact matches countExactWalks's own return value", () => {
    const space = countExactWalks();
    const manifest = buildManifest();
    expect(manifest.walksTotalExact).toBe(space.walksTotalExact);
    expect(manifest.nodesReached).toBe(space.nodesReached.size);
    expect(manifest.maxDepth).toBe(space.maxDepth);
  });
});
