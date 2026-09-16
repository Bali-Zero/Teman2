/**
 * A dead end, walked in a real browser, names the door that is open.
 *
 * `_lib/no-path-doors.test.tsx` holds the door table against the signed
 * pack's replay for all 17 non-supported walks, in both languages, through
 * the real `OutcomeSheet`. This spec proves the OTHER half on three of them:
 * that a visitor who actually answers those questions lands on that sheet,
 * and reads a named cause and a named product there — EN and ID.
 *
 * Nothing about the verdict is hand-written. The mocked engine response is
 * built from `no-path-doors.replay.json`'s OWN recorded decision for the
 * walk, and the expected doors come from the REAL adapter
 * (`buildNoPathDoors`) applied to the answers this spec gives. Only the
 * answer sequence itself is written out (the corpus generator cannot be
 * imported here: it resolves its output directory through `import.meta`,
 * which Playwright's CJS transform rejects) — and a stale sequence fails
 * loudly on the very first click, never silently.
 */

import { expect, test, type Page, type Route } from "@playwright/test";

import { buildNoPathDoors } from "../src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter";
import replay from "../src/app/(visa-oracle)/visa-oracle/_lib/fixtures/no-path-doors.replay.json";
import {
  QUESTIONS,
  type OracleFacts,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/tree";
import {
  translate,
  type I18nKey,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/i18n";
import { makeVisaOracleResponse } from "../src/app/(visa-oracle)/visa-oracle/_lib/visa-oracle-test-fixture";

const TEST_SOURCE_ID = "11111111-1111-4111-8111-111111111111";

interface Step {
  id: string;
  value: string;
}

/** The answers `generate-walk-corpus.ts` gives on these three walks (first
 * option everywhere, its fixed synthetic identity for typed questions). D19
 * (2026-09-16): `overstay_days` dropped from all three — offshore never
 * asks it any more. */
const WALKS: { label: string; steps: Step[] }[] = [
  {
    label: "offshore/business",
    steps: [
      { id: "in_indonesia", value: "no" },
      { id: "holds_stay_permit", value: "no" },
      { id: "nationalities", value: "IT" },
      { id: "birth_date", value: "2000-11-11" },
      { id: "category", value: "business" },
      { id: "trip_scope", value: "single" },
      { id: "business_activity", value: "meetings" },
      { id: "work_indonesia_compensation", value: "yes" },
      { id: "stay_days", value: "121" },
      { id: "entry_pattern", value: "SINGLE" },
      { id: "review_gate", value: "none" },
    ],
  },
  {
    label: "offshore/retirement/bank_deposit",
    steps: [
      { id: "in_indonesia", value: "no" },
      { id: "holds_stay_permit", value: "no" },
      { id: "nationalities", value: "IT" },
      { id: "birth_date", value: "2000-11-11" },
      { id: "category", value: "retirement" },
      { id: "trip_scope", value: "single" },
      { id: "sponsor_category", value: "NONE" },
      { id: "retirement_basis", value: "bank_deposit" },
      { id: "secondhome_deposit_usd", value: "1000000000" },
      { id: "secondhome_state_bank", value: "yes" },
      { id: "secondhome_own_name", value: "yes" },
      { id: "secondhome_passive_income_usd", value: "1000000000" },
      { id: "family_sponsor_confirmed", value: "yes" },
      { id: "stay_days", value: "121" },
      { id: "review_gate", value: "none" },
    ],
  },
  {
    label: "offshore/other/paid/employer_no",
    steps: [
      { id: "in_indonesia", value: "no" },
      { id: "holds_stay_permit", value: "no" },
      { id: "nationalities", value: "IT" },
      { id: "birth_date", value: "2000-11-11" },
      { id: "category", value: "other" },
      { id: "trip_scope", value: "single" },
      { id: "other_purpose", value: "transit" },
      { id: "other_paid_activity", value: "yes" },
      { id: "sponsor_category", value: "NONE" },
      { id: "work_payer", value: "no" },
      { id: "work_sponsor_confirmed", value: "yes" },
      { id: "stay_days", value: "121" },
      { id: "entry_pattern", value: "SINGLE" },
      { id: "review_gate", value: "none" },
    ],
  },
];

function replayWalk(label: string) {
  const walk = replay.walks.find((candidate) => candidate.label === label);
  if (!walk) throw new Error(`${label} is not in the replay fixture`);
  return walk;
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function decisionFor(label: string) {
  const walk = replayWalk(label);
  const response = makeVisaOracleResponse("NO_SUPPORTED_PATH");
  return {
    ...response,
    decision: {
      ...response.decision,
      no_path_reasons: (walk.no_path_reason_codes as string[]).map((code) => ({
        code,
        rule_ids: [],
        source_refs: [TEST_SOURCE_ID],
      })),
    },
  };
}

async function answer(page: Page, step: Step): Promise<void> {
  const question = QUESTIONS[step.id];
  if (!question) throw new Error(`the tree no longer asks ${step.id}`);
  const continueLabel = translate("en", "question.continue");
  const seeOptionsLabel = translate("en", "confirmation.cta");
  switch (question.kind) {
    case "branch":
    case "choice":
    case "tiles": {
      const option = question.options.find((item) => item.key === step.value);
      if (!option) throw new Error(`${step.id} has no option ${step.value}`);
      await page
        .getByRole("button", {
          name: translate("en", option.labelI18nKey as I18nKey),
          exact: true,
        })
        .click();
      return;
    }
    case "number":
      await page.getByRole("spinbutton").fill(step.value);
      await page.getByRole("button", { name: continueLabel }).click();
      return;
    case "date":
      await page.locator('input[type="date"]').fill(step.value);
      await page.getByRole("button", { name: seeOptionsLabel }).click();
      return;
    case "country-codes":
      await page.getByRole("combobox").selectOption(step.value);
      await page.getByRole("button", { name: /^add country$/i }).click();
      await page.getByRole("button", { name: continueLabel }).click();
      return;
    case "review-gate":
      await page
        .getByRole("checkbox", { name: /none of these apply to me/i })
        .check();
      await page.getByRole("button", { name: seeOptionsLabel }).click();
      return;
    default:
      throw new Error(`no driver for question kind ${question.kind}`);
  }
}

test.describe("Visa Oracle — a dead end names the door that is open", () => {
  for (const walk of WALKS) {
    test(`${walk.label} reads its cause and its door in EN and ID`, async ({
      page,
    }) => {
      test.slow();
      await page.route("**/api/visa-oracle/evaluate**", (route) =>
        fulfillJson(route, decisionFor(walk.label)),
      );
      await page.goto("/visa-oracle");
      await page.getByRole("button", { name: /^start$/i }).click();
      for (const step of walk.steps) await answer(page, step);
      await expect(
        page.getByRole("heading", {
          name: translate("en", "confirmation.title"),
        }),
      ).toBeVisible();
      await page
        .getByRole("button", { name: translate("en", "confirmation.cta") })
        .click();

      const sheet = page.locator(".oracle-outcome");
      await expect(sheet).toBeVisible();
      // No machine identifier ever reaches a reader, in either language.
      await expect(sheet).not.toContainText(
        "OPERATIONAL_NO_PRODUCT_MATCHES_DECLARED_PURPOSES",
      );
      await expect(sheet).not.toContainText("Verified reason:");

      const facts: OracleFacts = Object.fromEntries(
        walk.steps.map((step) => [step.id, step.value]),
      );
      const doors = buildNoPathDoors(
        replayWalk(walk.label).no_path_reason_codes as string[],
        facts,
      );
      expect(doors.length).toBeGreaterThan(0);
      for (const door of doors) {
        await expect(sheet).toContainText(door.productName!.en);
        await expect(sheet).toContainText(door.message!.en);
      }

      await page
        .getByRole("button", { name: /switch to bahasa indonesia/i })
        .click();
      for (const door of doors) {
        await expect(sheet).toContainText(door.productName!.id);
        await expect(sheet).toContainText(door.message!.id);
      }
      await expect(sheet).not.toContainText("Alasan terverifikasi:");
    });
  }
});
