import { APPLICANT_FACT_COUNT } from "../src/lib/api/applicant-fact-paths";
import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { translate } from "../src/app/(visa-oracle)/visa-oracle/_lib/i18n";
import { makeVisaOracleResponse } from "../src/app/(visa-oracle)/visa-oracle/_lib/visa-oracle-test-fixture";

const RESUME_KEY = "visa-oracle:v2:resume:v1";
const SCREENSHOT_DIR = path.resolve(
  process.cwd(),
  "../../docs/audits/screenshots/visa-oracle-v2",
);
const VERDICT_FACTS = {
  in_indonesia: "no",
  // Added 2026-08-24 (P0 offshore-reachability fix, PR #4727): offshore now
  // gates on this question before converging on overstay_days — see
  // flow.ts::computeNextNode's "in_indonesia" case. "no" here means the
  // synthesized NO_STAY_PERMIT sentinel resolves the derived fact without a
  // further question (fact-mapper.ts::mapCurrentStatusCode).
  holds_stay_permit: "no",
  overstay_days: "0",
  nationalities: "US",
  birth_date: "1990-01-01",
  category: "tourism",
  trip_scope: "single",
  stay_days: "30",
  entry_pattern: "SINGLE",
  review_gate: "none",
};
const VERDICT_HISTORY = [
  { kind: "framing" },
  { kind: "question", questionId: "in_indonesia" },
  // Added 2026-08-24 alongside VERDICT_FACTS.holds_stay_permit above — see
  // that constant's comment.
  { kind: "question", questionId: "holds_stay_permit" },
  { kind: "question", questionId: "overstay_days" },
  { kind: "question", questionId: "nationalities" },
  { kind: "question", questionId: "birth_date" },
  { kind: "question", questionId: "category" },
  { kind: "question", questionId: "trip_scope" },
  { kind: "question", questionId: "stay_days" },
  { kind: "question", questionId: "entry_pattern" },
  { kind: "question", questionId: "review_gate" },
  { kind: "confirmation" },
  { kind: "verdict" },
];

type FixtureState = NonNullable<Parameters<typeof makeVisaOracleResponse>[0]>;

async function seedVerdictResume(
  page: Page,
  facts: Record<string, string> = VERDICT_FACTS,
): Promise<void> {
  const savedAtIso = new Date().toISOString();
  const expiresAtIso = new Date(Date.now() + 2 * 60 * 60 * 1_000).toISOString();
  await page.addInitScript(
    ({ key, savedAt, expiresAt, history, facts }) => {
      window.sessionStorage.setItem(
        key,
        JSON.stringify({
          schemaVersion: 1,
          savedAtIso: savedAt,
          expiresAtIso: expiresAt,
          snapshot: {
            schemaVersion: 1,
            attempt: 0,
            history,
            facts,
            updatedAtIso: savedAt,
          },
        }),
      );
    },
    {
      key: RESUME_KEY,
      savedAt: savedAtIso,
      expiresAt: expiresAtIso,
      history: VERDICT_HISTORY,
      facts,
    },
  );
}

async function fulfillJson(route: Route, body: unknown): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function expectEngineState(page: Page, state: FixtureState) {
  await expect(
    page.getByRole("heading", {
      name: translate("en", `verdict.headline.${state}`),
    }),
  ).toBeVisible();
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
      nodes: nodes.map(({ target, failureSummary }) => ({
        target,
        failureSummary,
      })),
    })),
  ).toEqual([]);
}

async function tabTo(
  page: Page,
  target: ReturnType<Page["locator"]>,
  maxTabs = 80,
): Promise<void> {
  await expect(target).toBeVisible();
  for (let attempt = 0; attempt < maxTabs; attempt += 1) {
    if (
      await target.evaluate((element) => element === document.activeElement)
    ) {
      return;
    }
    await page.keyboard.press("Tab");
  }
  throw new Error(
    `Keyboard focus did not reach ${await target.evaluate((element) => element.outerHTML)}`,
  );
}

async function keyboardActivate(
  page: Page,
  target: ReturnType<Page["locator"]>,
): Promise<void> {
  await tabTo(page, target);
  await page.keyboard.press("Enter");
}

async function expectFocusedHeading(page: Page, name: string): Promise<void> {
  const heading = page.getByRole("heading", { name });
  await expect(heading).toBeVisible();
  await expect(heading).toBeFocused();
}

test.describe("Visa Oracle v2 integration — page Page", () => {
  for (const state of [
    "SUPPORTED_CANDIDATES",
    "NEEDS_INPUT",
    "HUMAN_REVIEW_REQUIRED",
    "NO_SUPPORTED_PATH",
    "TEMPORARILY_UNAVAILABLE",
  ] as const) {
    test(`ENGINE renders the OpenAPI ${state} state`, async ({
      page,
    }, testInfo) => {
      await seedVerdictResume(page);
      const requests: Array<{ body: string | null; key: string | undefined }> =
        [];
      await page.route("**/api/visa-oracle/evaluate**", async (route) => {
        requests.push({
          body: route.request().postData(),
          key: route.request().headers()["idempotency-key"],
        });
        await fulfillJson(route, makeVisaOracleResponse(state));
      });

      await page.goto("/visa-oracle");
      await expectEngineState(page, state);
      expect(requests).toHaveLength(1);
      expect(requests[0].key).toMatch(/^[0-9a-f-]{36}$/);
      const body = JSON.parse(requests[0].body ?? "{}") as {
        assessment_id?: string;
        facts?: Record<string, unknown>;
      };
      expect(body.assessment_id).toMatch(/^[0-9a-f-]{36}$/);
      // 45, not 46: `derived.has_active_stay_permit` is server-derived and
      // never sent on the wire — 41 + the 3 applicant-collected facts
      // (2026-08-23 vocabulary extension, PR #4650) + `immigration.renewal_paid`
      // (2026-08-24 F4, question now shipped in tree.ts/flow.ts — this
      // seed never answers `renewal_paid`, so the key is still present but
      // UNKNOWN NOT_ASKED, same count as before) is the correct count.
      expect(Object.keys(body.facts ?? {})).toHaveLength(APPLICANT_FACT_COUNT);

      if (state === "SUPPORTED_CANDIDATES") {
        await expect(page.getByText("Visit Visa C1")).toBeVisible();
        await expectNoWcagViolations(page);
        await page.screenshot({
          path: testInfo.outputPath("visa-oracle-engine-desktop.png"),
          fullPage: true,
        });
      } else {
        await expect(page.getByText("Visit Visa C1")).toHaveCount(0);
      }
    });
  }

  test("CURATED and malformed JSON fail closed with zero candidates", async ({
    page,
  }) => {
    await seedVerdictResume(page);
    const curated = makeVisaOracleResponse();
    curated.mode = "CURATED";
    await page.route("**/api/visa-oracle/evaluate**", (route) =>
      fulfillJson(route, curated),
    );
    await page.goto("/visa-oracle");
    // A pure CURATED response is NON_ENGINE_MODE, not a client-guard
    // failure — an evaluation genuinely happened and was sealed, just not
    // rendered as public authority. OracleShell.tsx routes this to the
    // honest SHADOW headline (fix(visa-oracle): stop telling the visitor
    // they submitted nothing when they did), matching the unit test in
    // OracleShell.test.tsx. The malformed-JSON case below is unaffected —
    // it is MALFORMED_RESPONSE, which stays CLIENT_GUARD.
    await expect(
      page.getByRole("heading", {
        name: translate("en", "verdict.provenance_headline.SHADOW"),
      }),
    ).toBeVisible();
    await expect(page.getByText("Visit Visa C1")).toHaveCount(0);

    await page.unroute("**/api/visa-oracle/evaluate**");
    await seedVerdictResume(page);
    await page.route("**/api/visa-oracle/evaluate**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: '{"mode":"ENGINE","mode":"CURATED"}',
      }),
    );
    await page.reload();
    await expect(
      page.getByRole("heading", {
        name: translate("en", "verdict.provenance_headline.CLIENT_GUARD"),
      }),
    ).toBeVisible();
    await expect(page.getByText("Visit Visa C1")).toHaveCount(0);
  });

  test("automatic network retry preserves exact body/key; explicit TEMP retry rotates both ids", async ({
    page,
  }) => {
    await seedVerdictResume(page);
    const networkRequests: Array<{
      body: string | null;
      key: string | undefined;
    }> = [];
    await page.route("**/api/visa-oracle/evaluate**", async (route) => {
      networkRequests.push({
        body: route.request().postData(),
        key: route.request().headers()["idempotency-key"],
      });
      if (networkRequests.length === 1) {
        await route.abort("failed");
      } else {
        await fulfillJson(
          route,
          makeVisaOracleResponse("TEMPORARILY_UNAVAILABLE"),
        );
      }
    });
    await page.goto("/visa-oracle");
    await expectEngineState(page, "TEMPORARILY_UNAVAILABLE");
    expect(networkRequests).toHaveLength(2);
    expect(networkRequests[1]).toEqual(networkRequests[0]);

    await page
      .getByRole("button", { name: "Retry verified evaluation" })
      .click();
    await expect.poll(() => networkRequests.length).toBe(3);
    expect(networkRequests[2].key).not.toBe(networkRequests[1].key);
    const before = JSON.parse(networkRequests[1].body ?? "{}") as {
      assessment_id?: string;
    };
    const after = JSON.parse(networkRequests[2].body ?? "{}") as {
      assessment_id?: string;
    };
    expect(after.assessment_id).not.toBe(before.assessment_id);
  });

  test("320px, keyboard and reduced-motion path has no overlap or horizontal overflow", async ({
    page,
  }, testInfo) => {
    await page.setViewportSize({ width: 320, height: 720 });
    await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
    await seedVerdictResume(page);
    await page.route("**/api/visa-oracle/evaluate**", (route) =>
      fulfillJson(route, makeVisaOracleResponse()),
    );
    await page.goto("/visa-oracle");
    await expectEngineState(page, "SUPPORTED_CANDIDATES");

    const dimensions = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(dimensions.scrollWidth).toBeLessThanOrEqual(
      dimensions.clientWidth + 1,
    );
    const clippedElements = await page
      .locator(".oracle-main__content")
      .evaluate((root) => {
        const viewportWidth = window.innerWidth;
        return Array.from(root.querySelectorAll<HTMLElement>("*"))
          .filter((element) => {
            if (element.closest(".oracle-breadcrumb, .oracle-table-scroll")) {
              return false;
            }
            const rect = element.getBoundingClientRect();
            return (
              rect.width > 0 &&
              rect.height > 0 &&
              (rect.left < -1 || rect.right > viewportWidth + 1)
            );
          })
          .slice(0, 20)
          .map((element) => {
            const rect = element.getBoundingClientRect();
            return {
              className: element.className,
              left: Math.round(rect.left),
              right: Math.round(rect.right),
              tagName: element.tagName,
            };
          });
      });
    expect(clippedElements).toEqual([]);
    await page.keyboard.press("Tab");
    await expect(page.locator(":focus-visible")).toHaveCount(1);
    await expectNoWcagViolations(page);
    await page.screenshot({
      path: testInfo.outputPath("visa-oracle-engine-320-reduced-motion.png"),
      fullPage: true,
    });
  });

  test("real EN/ID journey supports Back, branch pruning, confirmation edit and verified evaluation", async ({
    page,
  }) => {
    await page.route("**/api/visa-oracle/evaluate**", (route) =>
      fulfillJson(route, makeVisaOracleResponse()),
    );
    await page.goto("/visa-oracle");

    await page
      .getByRole("checkbox", {
        name: /save my interview on this device for 2 hours/i,
      })
      .check();
    await page.getByRole("button", { name: /^start$/i }).click();
    await page.getByRole("button", { name: /no, i.m planning ahead/i }).click();

    // Added 2026-08-24 (P0 offshore-reachability fix, PR #4727): offshore
    // now gates on holds_stay_permit before overstay_days — see
    // VERDICT_FACTS.holds_stay_permit's comment above for the mechanism.
    await page.getByRole("button", { name: "No", exact: true }).click();

    await page.getByRole("spinbutton").fill("0");
    await page.getByRole("button", { name: /^continue$/i }).click();

    await page.getByRole("combobox").selectOption("US");
    await page.getByRole("button", { name: /^add country$/i }).click();
    await page.getByRole("button", { name: /^continue$/i }).click();

    await page.locator('input[type="date"]').fill("1990-01-01");
    await page.getByRole("button", { name: /see my options/i }).click();

    await page
      .getByRole("button", { name: /switch to bahasa indonesia/i })
      .click();
    await expect(
      page.getByRole("heading", { name: /apa tujuan anda ke indonesia/i }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: /kerja & ketenagakerjaan/i })
      .click();
    await page
      .getByRole("button", { name: /ganti ke bahasa inggris/i })
      .click();
    await expect(
      page.getByRole("heading", { name: /only purpose for the trip/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /yes — one main purpose/i }).click();
    await expect(
      page.getByRole("heading", { name: /who sponsors your stay/i }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: /an employer.*company in indonesia/i })
      .click();
    await page
      .getByRole("button", { name: /yes, an indonesian entity pays me/i })
      .click();
    await expect(
      page.getByRole("heading", {
        name: /will any compensation.*indonesian source/i,
      }),
    ).toBeVisible();

    await page.getByRole("button", { name: /^back$/i }).click();
    await page.getByRole("button", { name: /^back$/i }).click();
    await page.getByRole("button", { name: /^back$/i }).click();
    await page.getByRole("button", { name: /^back$/i }).click();
    await expect(
      page.getByRole("heading", { name: /what brings you to indonesia/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /tourism & short visit/i }).click();
    await page.getByRole("button", { name: /yes — one main purpose/i }).click();
    await page.getByRole("spinbutton").fill("30");
    await page.getByRole("button", { name: /^continue$/i }).click();
    await page.getByRole("button", { name: /^one entry$/i }).click();
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();

    await expect(
      page.getByRole("heading", { name: /here.s what you told us/i }),
    ).toBeVisible();
    await expect(
      page.getByText(/will an indonesian-registered company/i),
    ).toHaveCount(0);
    const stayRow = page
      .locator(".oracle-confirmation__row")
      .filter({ hasText: /how many days do you plan to stay/i });
    await stayRow.getByRole("button", { name: /^edit$/i }).click();
    await page.getByRole("spinbutton").fill("45");
    await page.getByRole("button", { name: /^continue$/i }).click();
    await page.getByRole("button", { name: /^one entry$/i }).click();
    await page
      .getByRole("checkbox", { name: /none of these apply to me/i })
      .check();
    await page.getByRole("button", { name: /see my options/i }).click();
    await expect(
      page
        .locator(".oracle-confirmation__row")
        .filter({ hasText: /how many days do you plan to stay.*45 days/i }),
    ).toBeVisible();
    await page.getByRole("button", { name: /see my options/i }).click();

    await expectEngineState(page, "SUPPORTED_CANDIDATES");
    await expect(page.getByText("Visit Visa C1")).toBeVisible();
    await expect
      .poll(() =>
        page.evaluate((key) => sessionStorage.getItem(key), RESUME_KEY),
      )
      .toBeNull();
  });

  for (const language of ["en", "id"] as const) {
    test(`keyboard-only ${language.toUpperCase()} journey reaches a conservative engine outcome`, async ({
      page,
    }) => {
      await page.route("**/api/visa-oracle/evaluate**", (route) =>
        fulfillJson(route, makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED")),
      );
      await page.goto("/visa-oracle");

      if (language === "id") {
        await keyboardActivate(
          page,
          page.getByRole("button", { name: /switch to bahasa indonesia/i }),
        );
      }

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "framing.cta"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.in_indonesia"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "q.in_indonesia.opt.no"),
          exact: true,
        }),
      );
      // Added 2026-08-24 (P0 offshore-reachability fix, PR #4727) — see
      // VERDICT_FACTS.holds_stay_permit's comment above for the mechanism.
      await expectFocusedHeading(
        page,
        translate(language, "q.holds_stay_permit"),
      );

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "q.boolean.no"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.overstay_days"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "notsure.trigger"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.nationalities"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "notsure.trigger"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.birth_date"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "notsure.trigger"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.category"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "q.category.opt.tourism"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.trip_scope"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "q.trip_scope.opt.single"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.stay_days"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "back.button"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.trip_scope"));
      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "q.trip_scope.opt.single"),
          exact: true,
        }),
      );

      const stayDays = page.getByRole("spinbutton");
      await tabTo(page, stayDays);
      await page.keyboard.type("30");
      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "question.continue"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.entry_pattern"));

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "q.entry_pattern.opt.SINGLE"),
          exact: true,
        }),
      );
      await expectFocusedHeading(page, translate(language, "q.review_gate"));

      const noFlags = page.getByRole("checkbox", {
        name: translate(language, "q.review_gate.item.none"),
        exact: true,
      });
      await tabTo(page, noFlags);
      await page.keyboard.press("Space");
      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "confirmation.cta"),
          exact: true,
        }),
      );
      await expectFocusedHeading(
        page,
        translate(language, "confirmation.title"),
      );

      await keyboardActivate(
        page,
        page.getByRole("button", {
          name: translate(language, "confirmation.cta"),
          exact: true,
        }),
      );
      await expect(
        page.getByRole("heading", {
          name: translate(language, "verdict.headline.HUMAN_REVIEW_REQUIRED"),
        }),
      ).toBeVisible();
      await expectNoWcagViolations(page);
    });
  }

  test("configured WhatsApp handoff creates no link or QR before scoped consent", async ({
    page,
  }) => {
    await seedVerdictResume(page);
    await page.route("**/api/visa-oracle/evaluate**", (route) =>
      fulfillJson(route, makeVisaOracleResponse()),
    );
    await page.goto("/visa-oracle");
    await expectEngineState(page, "SUPPORTED_CANDIDATES");
    const contact = page.getByRole("button", {
      name: "Talk to a consultant",
      exact: true,
    });
    await expect(contact).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator("#oracle-consultant-panel")).toBeVisible();

    const consent = page.getByRole("checkbox", {
      name: /i consent to open whatsapp with a minimal visa oracle receipt/i,
    });
    await expect(consent).toBeVisible();
    await expect(
      page.getByRole("link", { name: /open whatsapp/i }),
    ).toHaveCount(0);
    await expect(page.getByRole("img", { name: /qr code/i })).toHaveCount(0);

    await consent.check();
    const link = page.getByRole("link", { name: /open whatsapp/i });
    const qr = page.getByRole("img", { name: /qr code/i });
    await expect(link).toHaveAttribute("href", /^https:\/\/wa\.me\//);
    await expect(qr).toBeVisible();
    expect(await qr.getAttribute("data-qr-value")).toBe(
      await link.getAttribute("href"),
    );
  });

  test("minor handoff requires guardian confirmation before separate WhatsApp consent", async ({
    page,
  }) => {
    await seedVerdictResume(page, {
      ...VERDICT_FACTS,
      birth_date: "2012-01-01",
    });
    await page.route("**/api/visa-oracle/evaluate**", (route) =>
      fulfillJson(route, makeVisaOracleResponse("HUMAN_REVIEW_REQUIRED")),
    );
    await page.goto("/visa-oracle");
    await expectEngineState(page, "HUMAN_REVIEW_REQUIRED");
    const contact = page.getByRole("button", {
      name: "Talk to a consultant",
      exact: true,
    });
    await expect(contact).toHaveAttribute("aria-expanded", "true");
    await expect(page.locator("#oracle-consultant-panel")).toBeVisible();

    const guardian = page.getByRole("checkbox", {
      name: /i confirm that i am the parent or legal guardian/i,
    });
    const whatsapp = page.getByRole("checkbox", {
      name: /i consent to open whatsapp with a minimal visa oracle receipt/i,
    });
    await expect(guardian).not.toBeChecked();
    await expect(whatsapp).toBeDisabled();
    await guardian.check();
    await expect(whatsapp).toBeEnabled();
    await expect(
      page.getByRole("link", { name: /open whatsapp/i }),
    ).toHaveCount(0);
    await whatsapp.check();
    await expect(
      page.getByRole("link", { name: /open whatsapp/i }),
    ).toBeVisible();
  });

  test("bilingual Privacy Policy V1 is WCAG-clean at desktop and 320px", async ({
    page,
  }) => {
    mkdirSync(SCREENSHOT_DIR, { recursive: true });
    for (const viewport of [
      { name: "desktop", width: 1280, height: 900 },
      { name: "mobile-320", width: 320, height: 720 },
    ]) {
      await page.setViewportSize({
        width: viewport.width,
        height: viewport.height,
      });
      await page.emulateMedia({ reducedMotion: "reduce", colorScheme: "dark" });
      await page.goto("/visa-oracle/privacy");
      await expect(
        page.getByRole("heading", { name: "Your Visa Oracle data" }),
      ).toBeVisible();
      await expect(page.getByText(/retained for 30 days/)).toBeVisible();
      const dimensions = await page.evaluate(() => ({
        clientWidth: document.documentElement.clientWidth,
        scrollWidth: document.documentElement.scrollWidth,
      }));
      expect(dimensions.scrollWidth).toBeLessThanOrEqual(
        dimensions.clientWidth + 1,
      );
      await expectNoWcagViolations(page);
      // Next.js' development-only status portal is not part of the product and
      // otherwise covers policy text in full-page evidence screenshots.
      await page.evaluate(() => {
        document
          .querySelectorAll("nextjs-portal")
          .forEach((portal) => portal.remove());
      });
      await page.screenshot({
        path: path.join(
          SCREENSHOT_DIR,
          `visa-oracle-privacy-v1-${viewport.name}.png`,
        ),
        fullPage: true,
      });
    }

    await page
      .getByRole("button", { name: /switch to bahasa indonesia/i })
      .click();
    await expect(
      page.getByRole("heading", { name: "Data Visa Oracle Anda" }),
    ).toBeVisible();
    await expectNoWcagViolations(page);
  });

  test("fresh framing offers sensitive local retention without enabling it", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    await expect(page.getByText(/save the full interview/i)).toBeVisible();
    await expect(
      page.getByRole("checkbox", {
        name: /save my interview on this device for 2 hours/i,
      }),
    ).not.toBeChecked();
    expect(
      await page.evaluate((key) => sessionStorage.getItem(key), RESUME_KEY),
    ).toBeNull();
    await expect(page.getByRole("button", { name: /^start$/i })).toBeVisible();
    await expect(page.locator(".oracle-constellation")).toHaveCount(0);
  });
});

test.describe("Visa Oracle noindex — served <head>, not just the metadata object", () => {
  // #4591 (2026-08-23): source-level analysis (next/dist/lib/metadata/
  // resolve-metadata.js) proved Next.js resolves `robots` as a whole-field
  // REPLACEMENT — never merged with the root layout's indexable `googleBot`
  // — so the exported `metadata.robots` object is trustworthy evidence for
  // what Next *computes*. It is not evidence for what actually ships in the
  // response: a page-level `metadata` export added later, a route moved out
  // from under this layout, a co-deletion of layout+unit-test in one
  // rewrite, or a future Next upgrade that changes merge semantics would
  // all be invisible to layout.test.tsx. Assert the SERVED <head> instead,
  // for every route under the SHADOW-engine layout.
  for (const routePath of [
    "/visa-oracle",
    "/visa-oracle/privacy",
    "/visa-oracle/unlock",
  ]) {
    test(`${routePath} serves a noindex robots meta tag`, async ({ page }) => {
      await page.goto(routePath);
      await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
        "content",
        /noindex/,
      );
      // The specific failure mode the source-level analysis ruled out: a
      // stray indexable googlebot tag next to the noindex robots tag —
      // Google obeys whichever tag is more specific to it. If Next ever
      // emits one (it doesn't today), it must not contradict the noindex.
      const googlebot = page.locator('meta[name="googlebot"]');
      if ((await googlebot.count()) > 0) {
        await expect(googlebot.first()).toHaveAttribute("content", /noindex/);
      }
    });
  }
});
