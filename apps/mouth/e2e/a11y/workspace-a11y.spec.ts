import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * F1 — workspace a11y guard.
 *
 * Ensures the (workspace) routes have ZERO axe violations of severity
 * `serious` or `critical` against WCAG 2.1 A/AA. The workspace layout owns
 * skip-link, h1#bz-page-title, <main id="main-content">, sidebar nav and
 * Header so a regression on any of them would surface here.
 *
 * Skips the heavy/long-API routes that need a fully provisioned backend
 * (terminal pty, team-management socket, dashboard analytics SWR fetch)
 * — those are still validated visually by the F1 baseline screenshots.
 */
const ROUTES = [
  "/admin",
  "/analytics",
  "/clients",
  "/dashboard",
  "/hr",
  "/inbox",
  "/intelligence",
  "/lkpm",
  "/notifications",
  "/omnichannel",
  "/process",
  "/revenue/analytics",
  "/settings",
];

const A11Y_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

for (const route of ROUTES) {
  test(`workspace ${route} has no serious/critical a11y violations`, async ({
    page,
  }) => {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    // Wait for workspace bootstrap (DEV BYPASS sets isLoading=false fast,
    // but Next dev compile may take a bit on the first hit).
    await page
      .waitForFunction(
        () => {
          const splash = Array.from(document.querySelectorAll("p")).some((p) =>
            /^loading…?$/i.test(p.textContent?.trim() || ""),
          );
          return !splash && !!document.querySelector("#bz-page-title");
        },
        { timeout: 30000 },
      )
      .catch(() => undefined);
    await page.waitForTimeout(300);

    const results = await new AxeBuilder({ page })
      .withTags(A11Y_TAGS)
      .analyze();
    const blocking = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(
      blocking,
      `serious/critical a11y violations on ${route}:\n${JSON.stringify(
        blocking.map((v) => ({
          id: v.id,
          impact: v.impact,
          help: v.help,
          nodes: v.nodes.length,
        })),
        null,
        2,
      )}`,
    ).toEqual([]);
  });
}
