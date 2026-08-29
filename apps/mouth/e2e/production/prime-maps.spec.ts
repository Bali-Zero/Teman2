import { test, expect } from "@playwright/test";

/**
 * `/prime` Google Maps key sentinel.
 *
 * THIS TEST IS EXPECTED TO FAIL AGAINST PRODUCTION TODAY (2026-08-29,
 * measured live: console prints
 * `Google Maps JavaScript API error: ExpiredKeyMapError`). That is correct
 * behavior, not a bug in this test — do NOT weaken the assertion to make it
 * pass. The map IS `/prime`'s product; a red here means a client opening
 * `/prime` sees a broken map, full stop.
 *
 * Needs-ruling item 1 (L11 spec): the fix is rotating/renewing the Google
 * Cloud Console API key — `operator[GUI]`, no code path in this repo can do
 * it. This sentinel exists so that fix, whenever it lands, is PROVEN by a
 * flip from red to green here instead of being taken on faith — and so the
 * regression is caught again immediately if the key expires a second time.
 *
 * This is deliberately the suite's one currently-red sentinel: it is the
 * evidence that this suite tests something real, not a suite that is green
 * because every assertion was written to already agree with production
 * (cicatrix-superscar.md family #2 — "esiste ≠ armato" applied to a test
 * suite, not just a cron).
 */
const MAPS_ERROR_RE =
  /ExpiredKeyMapError|InvalidKeyMapError|RefererNotAllowedMapError|ApiNotActivatedMapError|BillingNotEnabledMapError/;

test("/prime Google Maps key is valid (currently RED — see file header, needs-ruling item 1)", async ({
  page,
}) => {
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => {
    pageErrors.push(err.message);
  });

  await page.goto("/prime", { waitUntil: "domcontentloaded" });

  // Give the Maps SDK time to load, attempt initialization, and (today)
  // fail — measured live this takes a few seconds after DOM content loads.
  await page.waitForTimeout(6_000);

  const allMessages = [...consoleErrors, ...pageErrors];
  const mapsErrors = allMessages.filter((m) => MAPS_ERROR_RE.test(m));

  if (mapsErrors.length > 0) {
    throw new Error(
      "GOOGLE MAPS KEY DEFECT (live credential issue, not a code bug):\n" +
        mapsErrors.join("\n") +
        "\n\nFix: rotate/renew the Google Cloud Console Maps JavaScript API " +
        "key for this project (operator[GUI] — no code path fixes a " +
        "credential). See L11 spec needs-ruling item 1 and " +
        "research/operations/2026-08-28-beyond-sota-product-ux-visual-design.md.",
    );
  }

  expect(mapsErrors, "no Maps API key errors").toEqual([]);
});
