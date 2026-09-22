/**
 * W-VO-B3 — the UI-parity runner: the promoted bundle renders the LIVE
 * engine's recorded verdict, and this run spends no engine call.
 *
 * Design: kit/DRAFT-SPEC-B3-1.v2.md; clauses U1-U9, MANDATE-vo.md "Slice
 * B3" (PLAN §3 row B3, criterion G2-c; deps B2, A2 shipped).
 *
 * `page.route` intercepts the SAME-ORIGIN `/api/visa-oracle/evaluate` POST
 * (`_lib/evaluation-client.ts`) inside the browser, before the server-side
 * proxy, and fulfils it with the verdict the LIVE engine already recorded
 * for that `walk_id` in the B4-2 full sweep
 * (`research/operations/2026-09-22-visa-oracle-live-enumeration/
 * prove-live-b4-2-full-sweep-report-20260922.json`, 252 walks). The claim is
 * scoped on purpose: this proves the promoted BUNDLE renders that verdict
 * faithfully, never that the live engine still returns it today — a
 * route-mocked e2e pointed at production would prove the mock, not the
 * bundle (MANDATE-vo.md §6.3).
 *
 * Declared limits (one sentence each, repeated in the PR body):
 * - The record is a projection: candidates, pricing, sources, and the
 *   NEEDS_INPUT class's `missing_facts` (this fixture's `intent.stay_days`,
 *   which the record does not carry) are NOT compared.
 * - This run proves the bundle, not that the live engine still returns
 *   these verdicts (§6.3, honoured by scoping the assertions as above).
 * - Expectations are pinned to rule pack sequence 22 and to the source sha
 *   asserted in `beforeAll` below (U9) — a re-recorded sweep must update
 *   that constant in a PR, never silently change the measured expectations.
 * - `review_gate` multi-item combinations are outside the manifest's own
 *   declared gap (`enumerate-interview-space.ts`), not this spec's.
 * - One language per run (`en`).
 *
 * Opt-in by THREE fences (U8), because the default CI job IMPORTS every
 * spec file to build its `--list` and dies if that import throws
 * (`tests.yml:2386-2413`), and the enumerator's own cost (~2s, per its
 * `_lib/enumerate-interview-space.test.ts` docstring) would otherwise be
 * paid on every PR: (1) `VISA_ORACLE_LIVE_PARITY === "1"` gates the entire
 * `test.describe` below at MODULE SCOPE — when unset, this file registers
 * ZERO tests, not skipped ones; (2) the title matches neither
 * `"page Page"` nor `"@offline"`, the two tokens the default job's own
 * `--grep` selects; (3) module scope itself does NOTHING beyond that one
 * env read — no report read, no `countExactWalks`, no `buildCoveringSubset`
 * — all of that lives in `beforeAll`.
 *
 * B5-2 moved the CLI-only `import.meta` code out of this imported library;
 * B5-1 makes every sampled replay reach a verdict. A replay throw is still
 * reported rather than adjusted, including for review-gate post-hoc clones.
 *
 * A THIRD RED WAS MET, then CURED upstream by B4-2b (out of this spec's
 * touch-no-other-file scope, per U1): the report's `review-gate/blacklist`
 * row briefly carried `engine_state: "TEMPORARILY_UNAVAILABLE"` and
 * `rule_pack: null` — a sweep-time engine outage recorded in place of a
 * real verdict, not a business decision — which failed `beforeAll` by name
 * and blocked all 34 samples before any render logic ran. B4-2b re-swept
 * that ONE walk (now `HUMAN_REVIEW_REQUIRED`, real `rule_pack`) and this
 * PR's U9 sha was re-pinned to the patched report in a separate commit.
 * The `missingRulePack` check below stays as a permanent, named-failure
 * guard against a future outage row, even though none is expected today.
 */

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";

import {
  createInterviewSnapshot,
  flowReducer,
  initialFlowState,
  type FlowState,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/flow";
import {
  buildEngineOutcome,
  isSecondHomeStudioOnly,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter";
import {
  translate,
  type I18nKey,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/i18n";
import { localized } from "../src/app/(visa-oracle)/visa-oracle/_lib/outcome-view-model";
import type { OracleFacts } from "../src/app/(visa-oracle)/visa-oracle/_lib/tree";
import type { VisaOracleEvaluateResponse } from "../src/app/(visa-oracle)/visa-oracle/_lib/visa-oracle-contract";
import {
  makeVisaOracleResponse,
  TEST_SOURCE_ID,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/visa-oracle-test-fixture";
import {
  buildCoveringSubset,
  countExactWalks,
  type CoveringWalk,
} from "../scripts/visa-oracle/enumerate-interview-space";
import { installNoWriteGuard } from "./production/_support/no-write-context";

type EngineState = NonNullable<Parameters<typeof makeVisaOracleResponse>[0]>;

const LIVE_PARITY = process.env.VISA_ORACLE_LIVE_PARITY === "1";
const PER_CLASS = (() => {
  const raw = Number(process.env.VISA_ORACLE_PARITY_PER_CLASS ?? "1");
  return Number.isFinite(raw) && raw >= 1 ? Math.floor(raw) : 1;
})();
// The B4-2 report currently measures 34 classes (re-derived, not a pin to
// B4's stale 32 — U9 v3). Test declarations must be registered at module
// evaluation, so this count is the slot count for the static `test()` loop
// below; `beforeAll` re-derives the real count from the report and asserts
// it against this constant (U2's regression fence: dropping `notices` from
// the grouping key collapses the real count and that assertion goes RED),
// in addition to logging it.
const SAMPLE_CLASS_COUNT = 34;
const EXPECTED_REPORT_SHA256 =
  "49f0144323e1a1229992d57f8d8dbf2753f6d7a351b28e4254eefea6e57f8ac9";
const REPORT_RELATIVE_PATH =
  "../../research/operations/2026-09-22-visa-oracle-live-enumeration/" +
  "prove-live-b4-2-full-sweep-report-20260922.json";
const REPORT_PATH = resolve(process.cwd(), REPORT_RELATIVE_PATH);
const PARITY_REPORT_PATH = resolve(
  process.cwd(),
  process.env.VISA_ORACLE_PARITY_REPORT ??
    "output/visa-oracle-parity-report.json",
);

// `engine-adapter.ts`'s `GENERIC_REVIEW_REASON` is not exported (its own
// throw only fires outside `NODE_ENV=production`, so the promoted bundle
// falls back to this copy silently on an unmapped code) — duplicated
// verbatim here so PLAN G2-c red (iv), "the DOM shows GENERIC_REVIEW_
// REASON's text", has something concrete to assert against.
const GENERIC_REVIEW_REASON_EN =
  "Some of your answers need a person's judgment before we can confirm a path.";

const ALL_ENGINE_STATES: readonly EngineState[] = [
  "SUPPORTED_CANDIDATES",
  "NEEDS_INPUT",
  "HUMAN_REVIEW_REQUIRED",
  "NO_SUPPORTED_PATH",
  "TEMPORARILY_UNAVAILABLE",
];

interface RawReasonCodes {
  review_reasons: string[];
  no_path_reasons: string[];
  notices: string[];
}
interface RawWalk {
  walk_id: string;
  engine_state: EngineState;
  reason_codes: RawReasonCodes;
  rule_pack: { payload_sha256: string; sequence: number };
}
interface RawReport {
  walks: RawWalk[];
}

interface Sample {
  walkId: string;
  engineState: EngineState;
  reviewReasons: string[];
  noPathReasons: string[];
  notices: string[];
  facts: OracleFacts;
}

interface ObservedWalkResult {
  walk_id: string;
  class: string;
  expected: {
    headline: string;
    notices: string[];
    review_reasons: string[];
    no_path_reasons: string[];
  };
  observed: {
    headline: string | null;
    notices: string[];
    review_reasons_found: string[];
    no_path_reasons_found: string[];
  };
  parity: boolean;
  detail?: string;
}

const RESUME_KEY = "visa-oracle:v2:resume:v1";

/**
 * COPIED from `visa-oracle-state-colours.spec.ts:308-349` (never imported —
 * Playwright re-registers an imported spec file's tests), adapted to
 * replay a SAMPLED walk's own recorded facts instead of one fixed default
 * per question. U4: if the tree asks a question this walk's facts do not
 * answer, this throws NAMING the question id — never a 30s timeout. The
 * ten `review-gate/<item>` classes replay facts synthesized post hoc
 * (`enumerate-interview-space.ts:540-546`); a throw there is a REPORTED
 * risk, never adjusted.
 *
 * An earlier build session measured this throw firing far more broadly —
 * 30 of the then-32 sampled classes — because `generate-walk-corpus.ts`'s
 * `answerFor()` gave `wants_onshore_conversion`/`application_channel`
 * incoherent option pairs `flowReducer` correctly refused. B5-1 (merged
 * upstream of this PR) added the same `channelConflictsWithOnshoreIntent`
 * guard to `answerFor()` that `flowReducer` already applied, so every
 * walk's synthesized answers are coherent by construction now; this
 * finisher's real gated run reached a verdict for all 34 sampled classes,
 * zero throws (U4 v3's own fence). The throw path above stays live and
 * REPORTED (never adjusted) for the two cases it can still legitimately
 * fire: the ten `review-gate/<item>` post-hoc clones, and any future walk
 * the enumerator synthesizes outside what `flowReducer` will accept.
 */
function walkToVerdict(facts: OracleFacts, walkId: string): FlowState {
  let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
  while (Object.keys(state.facts).length < 60) {
    const node = state.history[state.history.length - 1];
    if (node.kind !== "question") break;
    const value = facts[node.questionId];
    if (value === undefined) {
      throw new Error(
        `live-parity weld [${walkId}]: the tree asked "${node.questionId}", which this ` +
          "walk's recorded facts do not answer",
      );
    }
    const before = Object.keys(state.facts).length;
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: node.questionId,
      value,
    });
    if (Object.keys(state.facts).length === before) {
      throw new Error(
        `live-parity weld [${walkId}]: the reducer refused an answer to "${node.questionId}"`,
      );
    }
  }
  const last = state.history[state.history.length - 1];
  return last.kind === "confirmation"
    ? flowReducer(state, { type: "ADVANCE" })
    : state;
}

async function seedVerdictResume(
  page: Page,
  facts: OracleFacts,
  walkId: string,
): Promise<void> {
  const state = walkToVerdict(facts, walkId);
  const savedAt = new Date();
  const snapshot = createInterviewSnapshot(
    { attempt: state.attempt, history: state.history, facts: state.facts },
    savedAt,
  );
  await page.addInitScript(
    ({ key, payload }) => window.sessionStorage.setItem(key, payload),
    {
      key: RESUME_KEY,
      payload: JSON.stringify({
        schemaVersion: 1,
        savedAtIso: savedAt.toISOString(),
        expiresAtIso: new Date(
          savedAt.getTime() + 2 * 60 * 60 * 1_000,
        ).toISOString(),
        snapshot,
      }),
    },
  );
}

/**
 * U5: the three response lists are REBUILT from the record's bare-string
 * codes, never overwritten wholesale — `makeVisaOracleResponse` emits at
 * most one review entry, at most one no-path entry and never a notice,
 * while 12 of the 32 classes carry two codes in one list and 13 carry a
 * notice. No-path entries need a DECISIVE ref (`engine-adapter.ts:1630`
 * `requireDecisiveRefs`) or the adapter throws `RESPONSE_INVARIANT` —
 * `TEST_SOURCE_ID` is the fixture's one decisive source. Review reasons
 * and notices may ship `source_refs: []` (`requireReviewHoldRefs` accepts
 * an empty list).
 */
function buildSampledResponse(sample: Sample): VisaOracleEvaluateResponse {
  const response = makeVisaOracleResponse(sample.engineState);
  response.decision.review_reasons = sample.reviewReasons.map((code) => ({
    code,
    rule_ids: [],
    source_refs: [],
  }));
  response.decision.notices = sample.notices.map((code) => ({
    code,
    rule_ids: [],
    source_refs: [],
  }));
  response.decision.no_path_reasons = sample.noPathReasons.map((code) => ({
    code,
    rule_ids: ["no-path"],
    source_refs: [TEST_SOURCE_ID],
  }));
  return response;
}

function classKey(codes: RawReasonCodes, state: EngineState): string {
  return JSON.stringify([
    state,
    [...codes.review_reasons].sort(),
    [...codes.no_path_reasons].sort(),
    [...codes.notices].sort(),
  ]);
}

let samples: Sample[] = [];
let measuredClassCount = 0;
let sourceReportMeta: {
  path: string;
  sha256: string;
  walk_count: number;
  rule_pack: { sequence: number; payload_sha256: string };
} | null = null;
const observedResults: ObservedWalkResult[] = [];
const targetMeta: {
  base_url: string;
  health_commit: string | null;
  vercel_id: string | null;
} = { base_url: "", health_commit: null, vercel_id: null };

// U8's third fence: this entire block — including the `for` loop that
// registers one `test()` per sample — runs at MODULE SCOPE, but only
// when opted in. Unset, the file registers zero tests (never skipped
// ones), so the default job's `--list` sees nothing from this file.
if (LIVE_PARITY) {
  test.describe("Visa Oracle v2 UI-parity — renders the B4-2 sweep's recorded verdicts", () => {
    test.beforeAll(async () => {
      const raw = readFileSync(REPORT_PATH);
      const actualSha256 = createHash("sha256").update(raw).digest("hex");
      if (actualSha256 !== EXPECTED_REPORT_SHA256) {
        throw new Error(
          "live-parity weld: source report sha mismatch — expected " +
            `${EXPECTED_REPORT_SHA256}, got ${actualSha256}. A re-recorded sweep must ` +
            "update this constant in a PR, never silently change measured expectations.",
        );
      }
      const report = JSON.parse(raw.toString("utf8")) as RawReport;

      // Discovered red, reported not cured: the B4-2 report can carry an
      // outage row (a sweep hiccup recorded as `engine_state:
      // "TEMPORARILY_UNAVAILABLE"` with `rule_pack: null`, not a real
      // engine verdict for that walk's facts — e.g. `review-gate/blacklist`
      // in the 20d429cc… report). Fail by NAME here, matching U3/U4's own
      // idiom, rather than an opaque TypeError on `.rule_pack.payload_sha256`.
      // Curing this (filtering the row, re-sweeping it) is a report-data
      // question outside this spec's scope — see the PR body.
      const missingRulePack = report.walks
        .filter((w) => !w.rule_pack)
        .map((w) => w.walk_id);
      if (missingRulePack.length > 0) {
        throw new Error(
          "live-parity weld: walk(s) with no rule_pack in the source report " +
            `(outage row, not a real engine verdict): ${JSON.stringify(missingRulePack)}`,
        );
      }

      const rulePackShas = new Set(
        report.walks.map((w) => w.rule_pack.payload_sha256),
      );
      if (rulePackShas.size !== 1) {
        throw new Error(
          "live-parity weld: sampled records do not share one rule_pack.payload_sha256 " +
            `— saw ${JSON.stringify([...rulePackShas])}`,
        );
      }
      const rulePackSequences = new Set(
        report.walks.map((w) => w.rule_pack.sequence),
      );
      sourceReportMeta = {
        path: REPORT_RELATIVE_PATH,
        sha256: actualSha256,
        walk_count: report.walks.length,
        rule_pack: {
          sequence: [...rulePackSequences][0],
          payload_sha256: [...rulePackShas][0],
        },
      };

      // U2: group by (engine_state, sorted review/no_path/notices),
      // sort each group by walk_id, take the first `PER_CLASS`.
      const groups = new Map<string, RawWalk[]>();
      for (const walk of report.walks) {
        const key = classKey(walk.reason_codes, walk.engine_state);
        const bucket = groups.get(key);
        if (bucket) bucket.push(walk);
        else groups.set(key, [walk]);
      }
      console.log(`B3 U9 measured sample classes: ${groups.size}`);
      // U2's regression fence, re-derived for B4-2 rather than pinned to
      // B4's stale 32 (U9 v3): the static `test()` loop below is declared
      // against SAMPLE_CLASS_COUNT at module scope, so a drift between the
      // measured class count and that constant must fail loudly here, not
      // silently drop classes from the sample or index `samples[]` out of
      // bounds. GUILT: drop `notices` from `classKey` → the measured count
      // no longer equals SAMPLE_CLASS_COUNT and this assertion goes RED.
      measuredClassCount = groups.size;
      expect(
        groups.size,
        "measured outcome classes vs SAMPLE_CLASS_COUNT",
      ).toBe(SAMPLE_CLASS_COUNT);

      const selected: RawWalk[] = [];
      for (const bucket of groups.values()) {
        const sorted = [...bucket].sort((a, b) =>
          a.walk_id < b.walk_id ? -1 : a.walk_id > b.walk_id ? 1 : 0,
        );
        selected.push(...sorted.slice(0, PER_CLASS));
      }

      // U3: the walk set is DERIVED, never transcribed — the derived
      // label set must EQUAL the report's walk_id set, failing by name
      // before the first page load. The import is top-level; the expensive
      // enumeration itself remains confined to this `beforeAll`.
      const space = countExactWalks();
      const subset = buildCoveringSubset(space);
      const derivedByLabel = new Map<string, CoveringWalk>(
        subset.walks.map((w) => [w.label, w]),
      );
      const derivedLabels = new Set(derivedByLabel.keys());
      const reportLabels = new Set(report.walks.map((w) => w.walk_id));
      const missingFromDerived = [...reportLabels]
        .filter((id) => !derivedLabels.has(id))
        .sort();
      const extraInDerived = [...derivedLabels]
        .filter((id) => !reportLabels.has(id))
        .sort();
      if (missingFromDerived.length > 0 || extraInDerived.length > 0) {
        throw new Error(
          "live-parity weld: derived label set != report walk_id set — missing " +
            `${JSON.stringify(missingFromDerived)}, extra ${JSON.stringify(extraInDerived)}`,
        );
      }

      samples = selected.map((walk) => {
        const derived = derivedByLabel.get(walk.walk_id);
        if (!derived) {
          throw new Error(
            `live-parity weld: no derived walk for "${walk.walk_id}"`,
          );
        }
        return {
          walkId: walk.walk_id,
          engineState: walk.engine_state,
          reviewReasons: walk.reason_codes.review_reasons,
          noPathReasons: walk.reason_codes.no_path_reasons,
          notices: walk.reason_codes.notices,
          facts: derived.facts,
        };
      });

      // U9 target metadata — best-effort locally (this builder's gated
      // run has no Vercel deployment in front of it); the conductor's
      // prove-live run against https://balizero.com is what makes
      // `health_commit`/`vercel_id` meaningful (MANDATE-vo.md "Slice
      // B3", Prove-live clause).
      targetMeta.base_url =
        process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
      try {
        const health = await fetch(`${targetMeta.base_url}/api/health`);
        const body = (await health.json()) as { commit?: string | null };
        targetMeta.health_commit = body.commit ?? null;
        targetMeta.vercel_id = health.headers.get("x-vercel-id");
      } catch {
        targetMeta.health_commit = null;
        targetMeta.vercel_id = null;
      }
    });

    for (let i = 0; i < SAMPLE_CLASS_COUNT * PER_CLASS; i++) {
      test(`sample ${i} renders its recorded verdict`, async ({ page }) => {
        const sample = samples[i];

        // U7: the guard needs the evaluate prefix, or the honest run is
        // RED on its own mock (`no-write-context.ts:106` records a
        // request even when a spec's own route fulfils it).
        const guard = await installNoWriteGuard(page, {
          allowedWritePathPrefixes: ["/api/visa-oracle/evaluate"],
        });

        await seedVerdictResume(page, sample.facts, sample.walkId);

        const response = buildSampledResponse(sample);
        let evaluateCount = 0;
        await page.route("**/api/visa-oracle/evaluate**", async (route) => {
          evaluateCount += 1;
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(response),
          });
        });

        await page.goto("/visa-oracle");
        await expect(page.locator(".oracle-headline")).toBeVisible();

        // U6: expected texts come from `buildEngineOutcome(response, {
        // facts })` — the `facts` option is load-bearing: it derives the
        // sentence for `PAID_ACTIVITY_WITHOUT_INDONESIAN_SPONSOR`
        // (sampled by `edge/work_payer=no`) from the interview's own
        // facts; an omitted option compares static fallback copy
        // against a fact-derived DOM.
        const outcome = buildEngineOutcome(response, { facts: sample.facts });
        // The expected headline is derived the way the SHIPPED UI derives
        // it (U6): `VerdictReveal.tsx` and `OutcomeSheet.tsx`'s share text
        // both select `verdict.headline.SECOND_HOME_STUDIO` over the
        // generic per-state headline whenever `isSecondHomeStudioOnly`
        // (imported from `engine-adapter.ts`, never re-implemented here)
        // is true — the ONE review reason `HUMAN_REVIEW_REQUIRED` must
        // never say "needs a human, not an algorithm" for. That predicate
        // already gates on `state === "HUMAN_REVIEW_REQUIRED"` internally.
        const expectedHeadline = translate(
          "en",
          (isSecondHomeStudioOnly(outcome)
            ? "verdict.headline.SECOND_HOME_STUDIO"
            : `verdict.headline.${sample.engineState}`) as I18nKey,
        );
        const expectedNoticeTexts = outcome.conditions.map((c) =>
          localized(c.message, "en"),
        );
        const expectedReviewTexts =
          outcome.state === "HUMAN_REVIEW_REQUIRED"
            ? outcome.reviewReasons.map((r) => localized(r.message, "en"))
            : [];
        const expectedNoPathTexts =
          outcome.state === "NO_SUPPORTED_PATH"
            ? outcome.noPathReasons.map((r) => localized(r.message, "en"))
            : [];

        const observedHeadline =
          (await page.locator(".oracle-headline").textContent())?.trim() ??
          null;

        const conditionsSection = page.locator(".oracle-outcome__conditions");
        const conditionsCount = await conditionsSection.count();
        const observedNotices =
          conditionsCount > 0
            ? (
                await conditionsSection
                  .locator(".oracle-reason-list li")
                  .allTextContents()
              ).map((t) => t.trim())
            : [];

        const pageText = await page.locator("body").innerText();
        const reviewFound = expectedReviewTexts.filter((text) =>
          pageText.includes(text),
        );
        const noPathFound = expectedNoPathTexts.filter((text) =>
          pageText.includes(text),
        );
        const otherHeadlinesAbsent = ALL_ENGINE_STATES.filter(
          (other) => other !== sample.engineState,
        ).every(
          (other) =>
            !pageText.includes(
              translate("en", `verdict.headline.${other}` as I18nKey),
            ),
        );
        const noGenericFallback = !pageText.includes(GENERIC_REVIEW_REASON_EN);

        const checks: Record<string, boolean> = {
          headline: observedHeadline === expectedHeadline,
          otherHeadlinesAbsent,
          // U6: zero recorded notices ⇒ the container is ABSENT, never
          // merely empty — GUILT-b feeds a zero-notice walk a fabricated
          // notice and this must go RED, not stay green.
          noticesSectionPresence:
            expectedNoticeTexts.length === 0
              ? conditionsCount === 0
              : conditionsCount === 1,
          notices:
            JSON.stringify(observedNotices) ===
            JSON.stringify(expectedNoticeTexts),
          reviewReasons: reviewFound.length === expectedReviewTexts.length,
          noPathReasons: noPathFound.length === expectedNoPathTexts.length,
          noGenericFallback,
          noUnexpectedWrites: guard.unexpectedWrites().length === 0,
          evaluateCalledOnce: evaluateCount === 1,
        };
        const parity = Object.values(checks).every(Boolean);

        observedResults.push({
          walk_id: sample.walkId,
          class: classKey(
            {
              review_reasons: sample.reviewReasons,
              no_path_reasons: sample.noPathReasons,
              notices: sample.notices,
            },
            sample.engineState,
          ),
          expected: {
            headline: expectedHeadline,
            notices: expectedNoticeTexts,
            review_reasons: expectedReviewTexts,
            no_path_reasons: expectedNoPathTexts,
          },
          observed: {
            headline: observedHeadline,
            notices: observedNotices,
            review_reasons_found: reviewFound,
            no_path_reasons_found: noPathFound,
          },
          parity,
          ...(parity ? {} : { detail: JSON.stringify(checks) }),
        });

        // The real assertions — each named so a red says which of the
        // above went wrong, not just "expect(true).toBe(true) failed".
        expect(observedHeadline, "headline").toBe(expectedHeadline);
        expect(otherHeadlinesAbsent, "no other state's headline present").toBe(
          true,
        );
        expect(
          conditionsCount,
          "notices section present iff notices recorded",
        ).toBe(expectedNoticeTexts.length === 0 ? 0 : 1);
        expect(
          observedNotices,
          "notice messages inside .oracle-outcome__conditions",
        ).toEqual(expectedNoticeTexts);
        expect(
          reviewFound,
          "every recorded review-reason message present page-wide",
        ).toEqual(expectedReviewTexts);
        expect(
          noPathFound,
          "every recorded no-path message present page-wide",
        ).toEqual(expectedNoPathTexts);
        expect(
          noGenericFallback,
          "no GENERIC_REVIEW_REASON fallback text anywhere",
        ).toBe(true);
        expect(
          guard.unexpectedWrites(),
          "no unexpected production write",
        ).toHaveLength(0);
        expect(evaluateCount, "evaluate route intercepted exactly once").toBe(
          1,
        );
      });
    }

    test.afterAll(() => {
      if (!sourceReportMeta) return; // beforeAll threw before populating it
      const report = {
        report_version: "1.0.0",
        generated_at: new Date().toISOString(),
        target: targetMeta,
        source_report: sourceReportMeta,
        sample: {
          strategy:
            "one walk per (engine_state, review_reasons, no_path_reasons, notices) class, sorted by walk_id",
          classes: measuredClassCount,
          walks: samples.length,
          per_class: PER_CLASS,
          language: "en",
        },
        scope: [
          "the record is a projection: candidates, pricing, sources and NEEDS_INPUT's missing_facts are not compared",
          "this run proves the BUNDLE, not that the live engine still returns these verdicts (MANDATE-vo.md §6.3)",
          "expectations are pinned to rule pack sequence 22 and to the source sha asserted above",
          "review_gate multi-item combinations are outside the manifest's own declared gap",
          "one language per run (en)",
        ],
        walks: observedResults,
        summary: {
          match: observedResults.filter((r) => r.parity).length,
          mismatch: observedResults.filter((r) => !r.parity).length,
        },
      };
      mkdirSync(dirname(PARITY_REPORT_PATH), { recursive: true });
      writeFileSync(
        PARITY_REPORT_PATH,
        `${JSON.stringify(report, null, 2)}\n`,
        "utf8",
      );
    });
  });
}
