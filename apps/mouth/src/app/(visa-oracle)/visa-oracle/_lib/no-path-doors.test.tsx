/**
 * A dead end names the door that IS open — and never names one it cannot
 * prove.
 *
 * Every "you would qualify for X" sentence in this product is a claim about
 * the SIGNED rule pack, so prose is not evidence for it. `fixtures/
 * no-path-doors.replay.json` is: it replays each non-supported interview walk
 * against the currently signed rule pack (`rulepack-prod-023.signed.json` as
 * of the seq-23 regen, 2026-09-25) with exactly one declared field changed,
 * and records which products the pack then supports.
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
  enumerateScenarios,
  runWalk,
} from "../../../../../scripts/visa-oracle/generate-walk-corpus";
import { DEFAULT_OUT_DIR } from "../../../../../scripts/visa-oracle/generate-walk-corpus.cli";
import { OutcomeSheet } from "../_components/OutcomeSheet";
import {
  SUPPORT_REASON_COPY,
  UNMAPPED_REASON_COPY,
  buildEngineOutcome,
  buildNoPathDoors,
} from "./engine-adapter";
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
  SUPPORT_REASON_COPY.OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES.en;

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

  it("covers the 17 dead ends, 3 held walks and 1 missing-input walk the current census reports", () => {
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
    //
    // Slice B5-1 (mission VISA-ORACLE-DW, 2026-09-21): this fixture had not
    // been regenerated since the pack was at sequence 20 (2026-09-06); the
    // walk-corpus regeneration this PR's Y5 required (process.application_channel
    // moving on 14 onshore fixtures — unrelated to any rule below) forced the
    // fingerprint check and, with it, a decade of accumulated pack drift the
    // previous evidence had never caught up to. Re-measured against the
    // signed pack now at sequence 22 (2026-09-16): `offshore/invest/
    // bank_deposit/below_threshold` and `offshore/invest/property/
    // below_threshold` now resolve HUMAN_REVIEW_REQUIRED, not
    // NO_SUPPORTED_PATH; `offshore/other/paid/sponsor_unsure` (was
    // NEEDS_INPUT) and `offshore/work/sponsor_government/trade_office_only/
    // employer_no` (was NO_SUPPORTED_PATH) no longer appear in the replay at
    // all — the corpus itself moved under both labels between sequence 20
    // and 22. None of the four is application_channel-sensitive: no rule in
    // rulepack-prod-020/021/022.source.json reads process.application_channel
    // (grep -c = 0 in all three, verified this PR), and the onshore section
    // of this replay is byte-identical to before. 17 -> 14, 2 -> 1.
    //
    // Slice A7-B rework (2026-09-22): rebased onto origin/main after
    // #7068/#7094/#7091/#7112, then re-measured by re-running
    // apps/mouth/scripts/visa-oracle/replay-no-path-doors.py. B5's ratified
    // move — `offshore/family/PARENT/spNat=IT/minor` sends
    // `person.guardian_consent` as UNKNOWN, so it leaves
    // HUMAN_REVIEW_REQUIRED for NEEDS_INPUT — is this PR's own change, not
    // pack drift: NO_SUPPORTED_PATH is untouched (14, B5-1's number holds),
    // NEEDS_INPUT gains exactly that one walk. 1 -> 2.
    //
    // Slice A7-M (2026-09-22): `tree.ts` now asks `guardian_consent` of
    // every minor. `offshore/family/PARENT/spNat=IT/minor` does not
    // override the answer, takes the question's FIRST option (`"yes"`),
    // and the adapter's `true` arm passes the decision through UNTOUCHED —
    // it leaves NEEDS_INPUT for SUPPORTED_CANDIDATES (not held, re-measured
    // — see `test_interview_walk_census.py`, never assumed). The new
    // sibling walk that declares `guardian_consent: "no"` earns the hold
    // instead (HUMAN_REVIEW_REQUIRED, not counted here). NEEDS_INPUT loses
    // that one walk: 2 -> 1.
    //
    // Seq-28 Step B regenerates this evidence against the current highest
    // signed pack, seq-27. The PR-11 boundary corpus raises the measured
    // distribution to 16 NO_SUPPORTED_PATH / 3 HUMAN_REVIEW_REQUIRED /
    // 1 NEEDS_INPUT; its two new E33G income witnesses are supported and do
    // not enter this non-supported fixture.
    //
    // E33 audit PR-4 (2026-10-14) re-measures against the highest signed
    // pack, seq-29. `offshore/remote/foreign_only/income_59999` now ends in
    // NO_SUPPORTED_PATH with E33G_INCOME_BELOW_THRESHOLD, so the dead ends
    // go 16 -> 17; the business walks lose AGE_BELOW_55 (seq-28) without
    // changing their state. HUMAN_REVIEW_REQUIRED and NEEDS_INPUT hold.
    const states = replay.walks.map((walk) => walk.state);
    expect(
      states.filter((state) => state === "NO_SUPPORTED_PATH"),
    ).toHaveLength(17);
    expect(
      states.filter((state) => state === "HUMAN_REVIEW_REQUIRED"),
    ).toHaveLength(3);
    expect(states.filter((state) => state === "NEEDS_INPUT")).toHaveLength(1);
    expect(replay.pack.file).toBe("rulepack-prod-029.signed.json");
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
        // Every cause is a sentence of its own: never the unmapped fallback,
        // and never the generic catalogue sentence unless the walk is one of
        // the known walks that still has no bespoke cause.
        expect(reason.message.en).not.toBe(UNMAPPED_REASON_COPY.en);
        expect(reason.message.id).not.toBe(UNMAPPED_REASON_COPY.id);
        if (!WALKS_WITHOUT_A_NAMED_CAUSE_YET.has(walk.label)) {
          expect(reason.message.en).not.toBe(GENERIC_NO_PATH_COPY);
        }
      }
    });
  }

  // E33G copy pin (E33 audit PR-4): the remote persona at foreign income
  // 59,999 reads the threshold, the unit and the translation as literal
  // sentences, so a changed figure, a monthly unit or a mistranslation goes
  // red here and not only a missing or raw code.
  it("pins the E33G income-threshold sentence in EN and ID, figure and yearly unit included: offshore/remote/foreign_only/income_59999", () => {
    const walk = replay.walks.find(
      (candidate) =>
        candidate.label === "offshore/remote/foreign_only/income_59999",
    );
    if (!walk) throw new Error("the income_59999 walk is not recorded");
    expect(noPathReasonCodes(walk)).toEqual(["E33G_INCOME_BELOW_THRESHOLD"]);
    const EN =
      "The Remote Worker visa (E33G) needs a salary or income of at least USD 60,000 a year; the yearly figure you gave is below it.";
    const ID =
      "Visa Rumah Kedua Pekerja Jarak Jauh (E33G) memerlukan gaji atau penghasilan minimal USD 60.000 per tahun; angka tahunan yang Anda berikan berada di bawah batas tersebut.";
    const outcome = outcomeFor(walk);
    if (outcome.state !== "NO_SUPPORTED_PATH") {
      throw new Error(`expected NO_SUPPORTED_PATH, got ${outcome.state}`);
    }
    expect(outcome.noPathReasons).toHaveLength(1);
    expect(outcome.noPathReasons[0].message.en).toBe(EN);
    expect(outcome.noPathReasons[0].message.id).toBe(ID);
    for (const [language, sentence] of [
      ["en", EN],
      ["id", ID],
    ] as const) {
      const { unmount } = render(
        <OutcomeSheet
          language={language}
          outcome={outcome}
          facts={factsFor(walk)}
        />,
      );
      expect(screen.getAllByText(sentence).length).toBeGreaterThan(0);
      unmount();
    }
  });

  // The assertions above can fail: an unmapped code really renders the
  // unmapped fallback, and the generic code renders the generic sentence.
  it("proves the fallback assertions bite: an unmapped code reads as the unmapped copy", () => {
    const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
    response.decision.no_path_reasons[0].code = "SOMETHING_NOT_IN_ANY_TABLE";
    const outcome = buildEngineOutcome(response, { facts: {} });
    if (outcome.state !== "NO_SUPPORTED_PATH") throw new Error("state");
    expect(outcome.noPathReasons[0].message.en).toBe(UNMAPPED_REASON_COPY.en);
    expect(outcome.noPathReasons[0].message.id).toBe(UNMAPPED_REASON_COPY.id);
  });

  it("proves the generic code reads as the generic catalogue sentence without a named cause", () => {
    const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
    response.decision.no_path_reasons[0].code =
      "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES";
    const outcome = buildEngineOutcome(response, { facts: {} });
    if (outcome.state !== "NO_SUPPORTED_PATH") throw new Error("state");
    expect(outcome.noPathReasons[0].message.en).toBe(GENERIC_NO_PATH_COPY);
  });

  // Slice A7-B, 2026-09-21 (restored in the 2026-09-22 rework after the
  // rebase onto B5-1 overwrote it wholesale): `person.guardian_consent` had
  // no reachable question in tree.ts yet (B3-bis — the mouth sent the key
  // contract-only, the question shipped in A7-M) — the backend's own
  // `WALK_DEAD_END_ALLOWLIST` named this exact fact `NO_QUESTION_IN_TREE`
  // for the same walk. Gate `vo-gate-a7-b`'s H1 finding named this exact
  // gap (`GATE-A7-B-REPORT-7080.md`); the conductor's 2026-09-22T07:17:47Z
  // ruling accepted it as an ORDERING window (A7-M merges in the same queue
  // window, stacked on this head) rather than a code cure. A7-M (this PR)
  // is that window closing: `guardian_consent` now has a reachable question
  // (`tree.ts`'s `guardian_consent` node, asked right after `birth_date` for
  // a minor). A missing input with no mapped question legitimately renders
  // without a `questionId` (`engine-adapter.ts`'s
  // `match ? { questionId } : {}`), so exemptions below are exact
  // walk+fact pairs rather than a global fact allowlist.
  const INPUTS_WITHOUT_A_REACHABLE_QUESTION_YET = new Set<string>([
    // PR-11's boundary walk deliberately answers retirement basis
    // `undecided` and then `still_unsure`. flow.ts intentionally asks no
    // evidence question after that answer, so the seq-27 replay's
    // passive-income NEEDS_INPUT remains a handoff row rather than reopening
    // a question the visitor just declined to choose a basis for.
    "offshore/retirement/undecided/age64/still_unsure:secondhome.passive_monthly_income_usd",
  ]);

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
        const exceptionKey = `${walk.label}:${input.code}`;
        if (!INPUTS_WITHOUT_A_REACHABLE_QUESTION_YET.has(exceptionKey)) {
          expect(
            input.questionId,
            `${walk.label} cannot reopen ${input.code}, so the visitor is left with a dead sentence`,
          ).toBeTruthy();
        }
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

// Slice A3'-M (M3): a sourceless dead end names no door — the pack never
// decided the answer at all, so there is no replay-proven alternative to
// name either. Unlike the replay-driven suite above, this exercises
// `buildNoPathDoors` directly against a fact shape the guard must catch
// EVEN when every other condition for a C1 door is met.
describe("buildNoPathDoors — the sourceless dead end names no door (A3'-M M3)", () => {
  it("returns no door when DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH is present, even on facts that would otherwise open C1", () => {
    const doors = buildNoPathDoors(["DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH"], {
      category: "other",
      stay_days: "30",
    });
    expect(doors).toEqual([]);
  });

  it("innocence: the SAME facts, without the sourceless code, DO open the C1 door", () => {
    const doors = buildNoPathDoors(
      ["OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES"],
      {
        category: "other",
        stay_days: "30",
      },
    );
    expect(doors.some((door) => door.productCode === "C1")).toBe(true);
  });

  it("innocence: a sourceless code alongside an ordinary one still names no door", () => {
    const doors = buildNoPathDoors(
      [
        "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
        "DISCLOSED_ACTIVITY_BOUNDARY_NO_PATH",
      ],
      { category: "other", stay_days: "30" },
    );
    expect(doors).toEqual([]);
  });
});
