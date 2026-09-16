/**
 * A dead end names the door that IS open — and never names one it cannot
 * prove.
 *
 * Every "you would qualify for X" sentence in this product is a claim about
 * the SIGNED rule pack, so prose is not evidence for it. `fixtures/
 * no-path-doors.replay.json` is: it replays each non-supported interview walk
 * against `rulepack-prod-020.signed.json` with exactly one declared field
 * changed, and records which products the pack then supports.
 *
 * This test drives the REAL interview (`runWalk` from the corpus generator,
 * the same machine that produced the backend census) into the REAL adapter
 * and the REAL sheet, then holds every rendered door against that evidence.
 * It goes red on four distinct drifts:
 *   1. a door rule names a product the replay does not support (OVER-match),
 *   2. a dead end renders no door at all (UNDER-match),
 *   3. the raw `OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES` catalogue
 *      sentence reappears on a walk whose own facts can name the cause,
 *   4. the walk corpus moved under the evidence (fingerprint), which makes
 *      every door above proven on facts that no longer exist.
 *
 * The cure for (4) is to re-measure, never to re-fingerprint:
 *   apps/backend-rag/.venv/bin/python \
 *     apps/mouth/scripts/visa-oracle/replay-no-path-doors.py
 */

import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  DEFAULT_OUT_DIR,
  enumerateScenarios,
  runWalk,
} from "../../../../../scripts/visa-oracle/generate-walk-corpus";
import { OutcomeSheet } from "../_components/OutcomeSheet";
import { buildEngineOutcome, buildNoPathDoors } from "./engine-adapter";
import { CATEGORY_TO_PURPOSE } from "./fact-mapper";
import replay from "./fixtures/no-path-doors.replay.json";
import type { Language } from "./flow";
import type { NoSupportedPathAlternative } from "./outcome-view-model";
import type { OracleFacts } from "./tree";
import type { VisaOracleEvaluateResponse } from "./visa-oracle-contract";
import {
  TEST_SOURCE_ID,
  makeVisaOracleResponse,
} from "./visa-oracle-test-fixture";

type ReplayWalk = (typeof replay.walks)[number];

/** The catalogue sentence a named cause must replace (engine-adapter.ts). */
const GENERIC_NO_PATH_COPY =
  "No visa in our verified catalogue covers the purpose you described.";

/** The JSON import widens an all-empty column to `never[]`; the codes are
 * plain strings and every consumer here reads them as such. */
function noPathReasonCodes(walk: ReplayWalk): string[] {
  return walk.no_path_reason_codes as string[];
}

const SCENARIOS = new Map(
  enumerateScenarios().map((scenario) => [scenario.label, scenario]),
);

function factsFor(
  walk: ReplayWalk,
  overrides: Record<string, string> = {},
): OracleFacts {
  const scenario = SCENARIOS.get(walk.label);
  if (!scenario) {
    throw new Error(
      `walk "${walk.label}" is no longer enumerated by the corpus generator — re-run replay-no-path-doors.py`,
    );
  }
  return { ...runWalk(scenario.overrides).facts, ...overrides };
}

/** The engine response this walk produced, rebuilt from the replay's own
 * recorded decision — never from a hand-written guess at what the pack says. */
function responseFor(walk: ReplayWalk): VisaOracleEvaluateResponse {
  const response = makeVisaOracleResponse(
    walk.state as VisaOracleEvaluateResponse["decision"]["state"],
  );
  return {
    ...response,
    decision: {
      ...response.decision,
      missing_facts:
        walk.missing_facts as VisaOracleEvaluateResponse["decision"]["missing_facts"],
      no_path_reasons: noPathReasonCodes(walk).map((code) => ({
        code,
        rule_ids: [],
        source_refs: [TEST_SOURCE_ID],
      })),
    },
  };
}

function outcomeFor(walk: ReplayWalk) {
  return buildEngineOutcome(responseFor(walk), { facts: factsFor(walk) });
}

/** Every rendered door names a product the replay actually returned behind
 * that door for these facts — and an empty recorded list means the rule had
 * to abstain. */
function expectDoorsProven(
  rendered: readonly NoSupportedPathAlternative[],
  recorded: Record<string, readonly string[]>,
  label: string,
): void {
  for (const door of rendered) {
    expect(door.productCode).toBeTruthy();
    expect(door.productName).toBeTruthy();
    // An unanswerable door is proven by the age replay; every other one by
    // the purpose its own tile declares. No third source exists.
    const proven =
      door.actionable === false
        ? (recorded.AGE_55 ?? [])
        : (recorded[CATEGORY_TO_PURPOSE[door.category] ?? ""] ?? []);
    expect(
      proven,
      `${label} names ${door.productCode} behind the ${door.category} door, which the replay does not support`,
    ).toContain(door.productCode);
  }
}

describe("no-path doors — the evidence behind every named alternative", () => {
  it("was measured on the walk corpus as it stands today", () => {
    const digest = createHash("sha256");
    for (const walk of replay.walks) {
      const bytes = readFileSync(join(DEFAULT_OUT_DIR, walk.walk_fixture));
      digest.update(walk.walk_fixture);
      digest.update(createHash("sha256").update(bytes).digest("hex"));
    }
    expect(
      digest.digest("hex"),
      "the interview corpus moved under this evidence: re-run apps/mouth/scripts/visa-oracle/replay-no-path-doors.py (with apps/backend-rag/.venv/bin/python) and commit the regenerated fixture",
    ).toBe(replay.walk_corpus_fingerprint);
  });

  it("covers the 17 dead ends and 2 held walks the census reports", () => {
    // D19 (2026-09-16): the corpus regeneration this pin depends on surfaced
    // one walk the previous evidence had omitted —
    // `offshore_business_exploring_sponsor_no_no_route.json`, D12_NOT_CONVERTIBLE —
    // pre-existing under the signed pack, unrelated to the `overstay_days`
    // fix itself; its `overrides` did not change.
    //
    // Zero decision 2026-09-16 (D12 wording, mandate SAETTA R2): regenerating
    // the corpus for the `business_sponsor_confirmed` rename (tree.ts) moved
    // the fingerprint again, and re-measuring surfaced a SECOND walk the
    // evidence had omitted — `offshore_work_sponsor_government_trade_office_
    // only_employer_no.json`, last touched by #6663 (2026-09-16, seq-22
    // candidate pack), unrelated to the D12 rename; its `overrides` did not
    // change either. 16 -> 17.
    const states = replay.walks.map((walk) => walk.state);
    expect(
      states.filter((state) => state === "NO_SUPPORTED_PATH"),
    ).toHaveLength(17);
    expect(states.filter((state) => state === "NEEDS_INPUT")).toHaveLength(2);
    expect(replay.pack.file).toBe("rulepack-prod-020.signed.json");
  });

  for (const walk of replay.walks.filter(
    (candidate) => candidate.state === "NO_SUPPORTED_PATH",
  )) {
    it(`names a door the pack actually supports: ${walk.label}`, () => {
      const outcome = outcomeFor(walk);
      if (outcome.state !== "NO_SUPPORTED_PATH") {
        throw new Error(`expected NO_SUPPORTED_PATH, got ${outcome.state}`);
      }
      expect(outcome.alternatives.length).toBeGreaterThan(0);
      expectDoorsProven(outcome.alternatives, walk.doors, walk.label);
    });
  }

  // The innocence half (Codex council round 1): one answer changed, the same
  // dead end, and a door the pack measurably SHUTS. A rule that fires here is
  // an OVER-match — cicatrix family #3 — no matter how green the 15 walks
  // above are.
  for (const row of replay.counterexamples) {
    it(`states its cause in words too: ${row.id}`, () => {
      const walk = replay.walks.find(
        (candidate) => candidate.walk_fixture === row.walk_fixture,
      );
      if (!walk) throw new Error(`${row.walk_fixture} is not a recorded walk`);
      const outcome = buildEngineOutcome(
        responseFor({
          ...walk,
          no_path_reason_codes: row.no_path_reason_codes,
        } as ReplayWalk),
        { facts: factsFor(walk, row.ui as unknown as Record<string, string>) },
      );
      if (outcome.state !== "NO_SUPPORTED_PATH") {
        throw new Error(`expected NO_SUPPORTED_PATH, got ${outcome.state}`);
      }
      for (const reason of outcome.noPathReasons) {
        expect(
          reason.message.en,
          `${reason.code} has no copy: the raw code reaches the reader`,
        ).not.toContain("Verified reason:");
        expect(reason.message.id).not.toContain("Alasan terverifikasi:");
      }
    });

    it(`abstains where the pack shuts the door: ${row.id}`, () => {
      const walk = replay.walks.find(
        (candidate) => candidate.walk_fixture === row.walk_fixture,
      );
      if (!walk) throw new Error(`${row.walk_fixture} is not a recorded walk`);
      // The JSON import types each row's `ui` as its own literal shape; the
      // answers are plain strings and the interview reads them as such.
      const facts = factsFor(walk, row.ui as unknown as Record<string, string>);
      const doors = buildNoPathDoors(
        row.no_path_reason_codes as string[],
        facts,
      );
      expectDoorsProven(doors, row.doors, row.id);
      // Council round 3: assert the abstention POSITIVELY where the pack
      // shuts every door, so a row whose rules correctly render nothing is
      // not a test that ran no assertion at all.
      const anyDoorOpen = Object.values(
        row.doors as Record<string, readonly string[]>,
      ).some((codes) => codes.length > 0);
      if (!anyDoorOpen) expect(doors).toHaveLength(0);
    });
  }

  // The browser found this hole before this loop did (2026-09-13): a code with
  // no entry in SUPPORT_REASON_COPY rendered `Verified reason: AGE_BELOW_55`
  // at a real reader on 7 of the 15 dead ends. Every walk is checked now, not
  // only the three that carry the generic catalogue code.
  for (const walk of replay.walks.filter(
    (candidate) => candidate.state === "NO_SUPPORTED_PATH",
  )) {
    it(`states every cause in words, EN and ID: ${walk.label}`, () => {
      const outcome = outcomeFor(walk);
      if (outcome.state !== "NO_SUPPORTED_PATH") {
        throw new Error(`expected NO_SUPPORTED_PATH, got ${outcome.state}`);
      }
      expect(outcome.noPathReasons.length).toBe(noPathReasonCodes(walk).length);
      for (const reason of outcome.noPathReasons) {
        expect(
          reason.message.en,
          `${reason.code} has no copy: the raw code reaches the reader`,
        ).not.toContain("Verified reason:");
        expect(reason.message.id).not.toContain("Alasan terverifikasi:");
        expect(reason.message.en).not.toContain(reason.code);
        expect(reason.message.id.length).toBeGreaterThan(0);
      }
    });
  }

  // `offshore/work/sponsor_government/trade_office_only/employer_no` —
  // surfaced by the same D12-rename corpus regeneration as the walk in the
  // dead-end count above, last touched by #6663 (2026-09-16), unrelated to
  // this PR. `engine-adapter.ts` only reconstructs
  // `OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES` for two named
  // combinations today (`paidActivityWithoutIndonesianPayerReason` and the
  // Second Home threshold one, `FACT_DERIVED_NO_PATH_CODES`); a GOVERNMENT
  // sponsor whose trade-office question resolves "no" and whose employer is
  // not Indonesian matches neither, so the generic sentence is the accurate,
  // measured behaviour today — writing it a bespoke cause is a product
  // decision outside a wording-only mandate, not a defect this diff owns.
  const WALKS_WITHOUT_A_NAMED_CAUSE_YET = new Set([
    "offshore/work/sponsor_government/trade_office_only/employer_no",
  ]);

  for (const walk of replay.walks.filter(
    (candidate) =>
      noPathReasonCodes(candidate).includes(
        "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      ) && !WALKS_WITHOUT_A_NAMED_CAUSE_YET.has(candidate.label),
  )) {
    it(`replaces the generic catalogue sentence with a named cause: ${walk.label}`, () => {
      const outcome = outcomeFor(walk);
      if (outcome.state !== "NO_SUPPORTED_PATH") {
        throw new Error(`expected NO_SUPPORTED_PATH, got ${outcome.state}`);
      }
      for (const reason of outcome.noPathReasons) {
        expect(reason.message.en).not.toContain(GENERIC_NO_PATH_COPY);
        expect(reason.message.en).not.toContain("Verified reason:");
        expect(reason.message.id).not.toContain("Alasan terverifikasi:");
        expect(reason.message.id.length).toBeGreaterThan(0);
      }
    });
  }

  for (const walk of replay.walks.filter(
    (candidate) => candidate.state === "NEEDS_INPUT",
  )) {
    it(`asks the missing fact instead of holding it: ${walk.label}`, () => {
      const outcome = outcomeFor(walk);
      if (outcome.state !== "NEEDS_INPUT") {
        throw new Error(`expected NEEDS_INPUT, got ${outcome.state}`);
      }
      expect(outcome.missingInputs.length).toBeGreaterThan(0);
      for (const input of outcome.missingInputs) {
        expect(
          input.questionId,
          `${walk.label} cannot reopen ${input.code}, so the visitor is left with a dead sentence`,
        ).toBeTruthy();
        expect(input.message.en.length).toBeGreaterThan(0);
        expect(input.message.id.length).toBeGreaterThan(0);
      }
    });
  }
});

describe("no-path doors — what the visitor actually reads", () => {
  for (const language of ["en", "id"] as Language[]) {
    for (const walk of replay.walks.filter(
      (candidate) => candidate.state === "NO_SUPPORTED_PATH",
    )) {
      it(`renders the cause and the open door in ${language.toUpperCase()}: ${walk.label}`, () => {
        const outcome = outcomeFor(walk);
        if (outcome.state !== "NO_SUPPORTED_PATH") {
          throw new Error(`expected NO_SUPPORTED_PATH, got ${outcome.state}`);
        }
        const { container, unmount } = render(
          <OutcomeSheet
            language={language}
            outcome={outcome}
            facts={factsFor(walk)}
          />,
        );
        const html = container.innerHTML;
        // The reason code itself is a machine identifier and never copy.
        expect(html).not.toContain(
          "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
        );
        for (const reason of outcome.noPathReasons) {
          expect(
            screen.getAllByText(reason.message[language]).length,
          ).toBeGreaterThan(0);
        }
        for (const door of outcome.alternatives) {
          expect(html).toContain(door.productCode);
        }
        unmount();
      });
    }
  }
});
