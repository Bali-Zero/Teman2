import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
import path from "node:path";
import {
  createInterviewSnapshot,
  flowReducer,
  initialFlowState,
  QUESTIONS,
  type FlowState,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/flow";
import type { OracleQuestion } from "../src/app/(visa-oracle)/visa-oracle/_lib/tree";
import { translate } from "../src/app/(visa-oracle)/visa-oracle/_lib/i18n";
import { makeVisaOracleResponse } from "../src/app/(visa-oracle)/visa-oracle/_lib/visa-oracle-test-fixture";

/**
 * W-VO-T — the decision tree as a VISIBLE process.
 *
 * Every state this spec renders is produced by replaying the real reducer
 * (`flowReducer`) rather than by hand-writing a history: a walk that the
 * state machine cannot produce is a walk no visitor can reach, and pinning
 * screenshots to one would prove nothing.
 */

const RESUME_KEY = "visa-oracle:v2:resume:v1";
const RENDER_DIR =
  process.env.VO_T_RENDER_DIR ??
  path.resolve("/Users/balizero/Desktop/R3-RENDERS-20260913/vo-t");

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  mobile: { width: 390, height: 844 },
} as const;

/** The corpus generator's own rule: answer with the FIRST option, so the
 * walk is deterministic and reproducible. Typed inputs get the one value
 * their input kind accepts. */
function answerValue(question: OracleQuestion): string {
  if (question.id === "birth_date") return "1985-04-12";
  if (question.kind === "date") return "2026-12-01";
  if (question.kind === "number") {
    if (question.id === "overstay_days") return "0";
    return String(question.numberInput?.min ?? 0);
  }
  if (question.kind === "country-codes") return "IT";
  if (question.kind === "review-gate") return "none";
  return question.options[0]?.key ?? "unsure";
}

/** Replay the interview until `answers` questions have been answered, or
 * until the interview leaves the question spine. `overrides` forces a
 * specific answer (the purpose branch, here) without touching the rest. */
function walk(
  answers: number,
  overrides: Record<string, string> = {},
): FlowState {
  let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
  let answered = 0;
  while (answered < answers) {
    const node = state.history[state.history.length - 1];
    if (node.kind !== "question") break;
    const question = QUESTIONS[node.questionId];
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: node.questionId,
      value: overrides[node.questionId] ?? answerValue(question),
    });
    answered += 1;
  }
  return state;
}

/** Answer everything, then step off the confirmation card onto the verdict. */
function walkToVerdict(overrides: Record<string, string> = {}): FlowState {
  let state = walk(60, overrides);
  const node = state.history[state.history.length - 1];
  if (node.kind === "confirmation") {
    state = flowReducer(state, { type: "ADVANCE" });
  }
  return state;
}

async function seed(page: Page, state: FlowState): Promise<void> {
  const savedAt = new Date();
  const snapshot = createInterviewSnapshot(
    { attempt: state.attempt, history: state.history, facts: state.facts },
    savedAt,
  );
  await page.addInitScript(
    ({ key, payload }) => {
      window.sessionStorage.setItem(key, payload);
    },
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

async function mockEngine(page: Page): Promise<void> {
  await page.route("**/api/visa-oracle/evaluate**", (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(makeVisaOracleResponse()),
    }),
  );
}

async function switchToIndonesian(page: Page): Promise<void> {
  await page
    .getByRole("button", { name: /switch to bahasa indonesia/i })
    .click();
}

/** At 390 the rail is behind the progress line; open the jump sheet. */
async function openMobileSheet(page: Page): Promise<void> {
  await page.locator(".oracle-tree-minimap-trigger").click();
  await expect(
    page.locator('[data-process-part="progress"][data-process-rail="mobile"]'),
  ).toBeVisible();
}

function rail(page: Page, part: "progress" | "branches", mobile: boolean) {
  return page.locator(
    `[data-process-part="${part}"][data-process-rail="${
      mobile ? "mobile" : "desktop"
    }"]`,
  );
}

async function expectNoWcagViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(
    results.violations.map(({ id, impact, help, nodes }) => ({
      id,
      impact,
      help,
      nodes: nodes.map(({ target }) => target),
    })),
  ).toEqual([]);
}

test.describe("Visa Oracle — the decision tree is a visible process", () => {
  test.beforeAll(() => {
    mkdirSync(RENDER_DIR, { recursive: true });
  });

  test("the rail names the stage, the fact in play and the branches an answer closed", async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await seed(page, walk(12, { category: "work" }));
    await mockEngine(page);
    await page.goto("/visa-oracle");

    const progress = rail(page, "progress", false);
    await expect(progress).toContainText("Step 12 of");
    await expect(progress).toContainText("What this question decides");
    // The purpose branch is chosen: ten of the eleven are closed, and the
    // rail says WHY — the visitor's own answer, named.
    const branches = rail(page, "branches", false);
    await expect(
      branches.locator('[data-process-category][data-status="pruned"]'),
    ).toHaveCount(10);
    await expect(branches).toContainText("closed when you chose");
    // Nothing on screen may name a product before the engine has answered.
    await expect(branches).toContainText("No product is named yet");
    await expect(page.locator("[data-process-announce]")).toHaveText(
      /10 of the other purpose branches closed\.$/,
    );
    await expectNoWcagViolations(page);
  });

  test("jumping back to an earlier answer keeps every prerequisite answer", async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await seed(page, walk(12, { category: "work" }));
    await mockEngine(page);
    await page.goto("/visa-oracle");

    const desktopTree = page.locator(".oracle-tree--desktop");
    const jumpBack = desktopTree.locator('[data-process-jump="category"]');
    // The jump target carries the ANSWER, not only the question label.
    await expect(jumpBack).toHaveAttribute(
      "aria-label",
      /you answered Work & employment/,
    );
    await jumpBack.click();

    await expect(
      page.getByRole("heading", { name: translate("en", "q.category") }),
    ).toBeVisible();
    // Prerequisites — everything asked BEFORE the jump target — survive.
    for (const questionId of [
      "in_indonesia",
      "overstay_days",
      "nationalities",
      "birth_date",
    ]) {
      await expect(
        desktopTree.locator(`[data-process-jump="${questionId}"]`),
      ).toHaveCount(1);
    }
    // And the branches the old answer had closed are open again.
    await expect(rail(page, "branches", false)).toContainText(
      "Every purpose branch is still open",
    );
    await expect(page.locator("[data-process-announce]")).toHaveText("");
  });

  test("the outcome is the last node of the same tree and names the engine's own product", async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await seed(page, walkToVerdict());
    await mockEngine(page);
    await page.goto("/visa-oracle");

    const branches = rail(page, "branches", false);
    await expect(
      branches.locator('[data-process-candidate="C1"]'),
    ).toBeVisible();
    await expect(branches).toContainText("last node of this tree");
    await expect(rail(page, "progress", false)).toContainText(
      "No question is open",
    );
    await expectNoWcagViolations(page);
  });

  test("at 390 the rail collapses to a progress line and a jump sheet", async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORTS.mobile);
    await seed(page, walk(12, { category: "work" }));
    await mockEngine(page);
    await page.goto("/visa-oracle");

    const trigger = page.locator(".oracle-tree-minimap-trigger");
    await expect(trigger).toBeVisible();
    await expect(trigger).toContainText(/Step 12 of \d+/);
    await expect(trigger).toContainText("Work & employment");
    await expect(rail(page, "progress", true)).toHaveCount(0);

    await openMobileSheet(page);
    await expect(
      rail(page, "branches", true).locator(
        '[data-process-category][data-status="pruned"]',
      ),
    ).toHaveCount(10);
    await expectNoWcagViolations(page);

    const overflow = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
  });

  for (const language of ["en", "id"] as const) {
    for (const [viewportName, viewport] of Object.entries(VIEWPORTS)) {
      test(`renders ${language.toUpperCase()} at ${viewport.width} — step 3, step 12, outcome`, async ({
        page,
      }) => {
        await page.setViewportSize(viewport);
        await mockEngine(page);
        const shots: [string, FlowState][] = [
          ["step03", walk(3)],
          ["step12", walk(12, { category: "work" })],
          ["outcome", walkToVerdict()],
        ];
        for (const [name, state] of shots) {
          await seed(page, state);
          await page.goto("/visa-oracle");
          if (language === "id") await switchToIndonesian(page);
          if (viewportName === "mobile") await openMobileSheet(page);
          await expect(
            rail(page, "progress", viewportName === "mobile"),
          ).toBeVisible();
          await page.screenshot({
            path: path.join(
              RENDER_DIR,
              `vo-t-${name}-${language}-${viewport.width}.png`,
            ),
            fullPage: true,
          });
        }
      });
    }
  }
});
