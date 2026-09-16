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
/** Renders land in the git-ignored `test-results/` by default, so the spec
 * runs on any machine; point `VO_T_RENDER_DIR` elsewhere to keep a set. */
const RENDER_DIR =
  process.env.VO_T_RENDER_DIR ?? path.resolve("test-results", "vo-t-renders");

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

/** Offshore, no stay permit — the shape the existing Oracle e2e walks, and
 * the one that avoids the onshore channel/conversion conflict the reducer
 * legitimately refuses to record. */
const OFFSHORE: Record<string, string> = {
  in_indonesia: "no",
  holds_stay_permit: "no",
};

/** Replay the interview until `answers` facts are on record, or until the
 * interview leaves the question spine. `overrides` forces a specific answer
 * (the purpose branch, here) without touching the rest. A refused answer
 * throws rather than silently stalling: a walk the reducer will not record
 * is not a walk a visitor can take. */
function walk(
  answers: number,
  overrides: Record<string, string> = {},
): FlowState {
  const chosen = { ...OFFSHORE, ...overrides };
  let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
  while (Object.keys(state.facts).length < answers) {
    const node = state.history[state.history.length - 1];
    if (node.kind !== "question") break;
    const before = Object.keys(state.facts).length;
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: node.questionId,
      value: chosen[node.questionId] ?? answerValue(QUESTIONS[node.questionId]),
    });
    if (Object.keys(state.facts).length === before) {
      throw new Error(`the reducer refused an answer to ${node.questionId}`);
    }
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
  // The sheet expands with a height animation; capturing mid-animation
  // clips the panel at whatever height it had reached (the container is
  // overflow:hidden by design).
  await page.waitForTimeout(600);
}

function rail(
  page: Page,
  part: "progress" | "branches" | "outcome",
  mobile: boolean,
) {
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
    await expect(progress).toContainText(/12 of \d+ answered/);
    await expect(progress).toContainText("What this question decides");
    // The purpose branch is chosen: ten of the eleven are closed, and the
    // rail says WHY — the visitor's own answer, named.
    const branches = rail(page, "branches", false);
    await expect(
      branches.locator('[data-process-category][data-status="pruned"]'),
    ).toHaveCount(10);
    await expect(branches).toContainText("closed when you chose");
    // Nothing on screen may name a product before the engine has answered.
    await expect(rail(page, "outcome", false)).toContainText(
      "No product is named yet",
    );
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
    // D19 (2026-09-16): `overstay_days` dropped from this list — this walk
    // is offshore, and offshore never asks it any more.
    for (const questionId of ["in_indonesia", "nationalities", "birth_date"]) {
      await expect(
        desktopTree.locator(`[data-process-jump="${questionId}"]`),
      ).toHaveCount(1);
    }
    // Choosing a DIFFERENT branch from here keeps every prerequisite: the
    // rail re-states the prune with the new answer, and nothing earlier is
    // lost.
    await page
      .getByRole("button", {
        name: translate("en", "q.category.opt.study"),
        exact: true,
      })
      .click();
    await expect(rail(page, "branches", false)).toContainText(
      "closed when you chose “Study”",
    );
    for (const questionId of ["in_indonesia", "nationalities", "birth_date"]) {
      await expect(
        desktopTree.locator(`[data-process-jump="${questionId}"]`),
      ).toHaveCount(1);
    }
  });

  test("the outcome is the last node of the same tree and names the engine's own product", async ({
    page,
  }) => {
    await page.setViewportSize(VIEWPORTS.desktop);
    await seed(page, walkToVerdict());
    await mockEngine(page);
    await page.goto("/visa-oracle");

    const outcome = rail(page, "outcome", false);
    await expect(
      outcome.locator('[data-process-candidate="C1"]'),
    ).toBeVisible();
    await expect(outcome).toContainText("last node of this tree");
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
    await expect(trigger).toContainText(/12 of \d+ answered/);
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
        const shots: [string, FlowState][] = [
          ["step03", walk(3)],
          ["step12", walk(12, { category: "work" })],
          ["outcome", walkToVerdict()],
        ];
        for (const [name, state] of shots) {
          // One page per state: init scripts accumulate on a page and their
          // evaluation order is undefined, so reusing `page` could restore an
          // earlier snapshot under a later file name (council round 10).
          const shot = await page.context().newPage();
          await shot.setViewportSize(viewport);
          await mockEngine(shot);
          await seed(shot, state);
          await shot.goto("/visa-oracle");
          if (language === "id") await switchToIndonesian(shot);
          const mobile = viewportName === "mobile";
          if (mobile) await openMobileSheet(shot);
          // The render must show the state its file name claims.
          if (name === "outcome") {
            await expect(rail(shot, "outcome", mobile)).toContainText("C1");
          } else {
            await expect(rail(shot, "progress", mobile)).toContainText(
              new RegExp(
                `\\b${Object.keys(state.facts).length} (of|dari) \\d+`,
              ),
            );
          }
          await shot.screenshot({
            path: path.join(
              RENDER_DIR,
              `vo-t-${name}-${language}-${viewport.width}.png`,
            ),
            fullPage: true,
          });
          await shot.close();
        }
      });
    }
  }
});
