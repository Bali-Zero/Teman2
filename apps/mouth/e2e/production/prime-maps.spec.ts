import { test, expect } from "@playwright/test";
import { installNoWriteGuard } from "./_support/no-write-context";

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
 *
 * REFUTATION ROUND 2 (CRITICAL, cicatrix-superscar.md family #2): the
 * original version of this test asserted ONLY the absence of five known
 * error strings. A 404 on `/prime` itself, a script blocked by CSP, a DNS
 * failure reaching maps.googleapis.com, a Maps error Google renames
 * tomorrow, or the map area rendering nothing at all with no console
 * message — every one of those PASSED, because none of them produce one of
 * the five named strings. "The map rendered" was never actually asserted,
 * only "these five specific bad things didn't happen".
 *
 * MEASURED (not assumed) what "map rendered" looks like on THIS component
 * (apps/mouth/src/components/maps/PrimeMap3D.tsx, mounted via
 * apps/mouth/src/components/maps/prime/PrimeNexusLayout.tsx): once the
 * Maps JS bootstrap `<Script>` fires `onLoad`, `isLoaded` flips true, the
 * `<div>`-based "Loading 3D Map" skeleton (PrimeMap3D.tsx's own inline
 * skeleton, distinct from the outer `data-testid="prime-map-skeleton"`
 * Suspense/dynamic-import fallback in PrimeMapSkeleton.tsx) unmounts, and a
 * `<gmp-map-3d>` custom element (Google's `Map3DElement`) is appended into
 * the map container — ALL THREE OF THESE ARE TRUE EVEN TODAY, UNDER THE
 * LIVE ExpiredKeyMapError DEFECT (Google's JS bootstrap loads and defines
 * `window.google.maps` regardless of key validity; key validation happens
 * against the backend, and Google's own error UI renders inside a CLOSED
 * shadow root on `<gmp-map-3d>` that neither `document.body.innerText` nor
 * Playwright locators can see — confirmed empirically: a screenshot shows
 * Google's own "Oops! Something went wrong" overlay, but `getByText` on
 * that exact string returns zero matches). So these three checks alone do
 * NOT discriminate today's defect from a healthy map — they are useful for
 * a DIFFERENT class of break (404 / blocked script / DNS failure / CSP —
 * cases where the SDK never loads at all), and are kept for exactly that,
 * with the below error-string check doing the discrimination for the
 * "SDK loaded but the key doesn't work" class.
 *
 * The "renamed error code" gap is closed differently: Google's own error
 * messages ALL share one stable prefix (confirmed both empirically, on the
 * live ExpiredKeyMapError, and in Google's public error-message docs the
 * error text itself links to) — "Google Maps JavaScript API error: <Code>".
 * Matching that prefix, not an enumerated list of today's known codes,
 * means a code Google adds or renames tomorrow still trips this check
 * without a code change here.
 *
 * UNRESOLVED, dictated by the tooling rather than skipped (reported, not
 * guessed): a genuinely BLANK map with zero console signal at all (no
 * error, SDK loaded, skeleton gone, element present, but nothing visually
 * drawn) is NOT detectable by any of these checks — Google's own failure
 * UI lives in a closed shadow root Playwright cannot query, and telling
 * "blank" from "rendered" without a pixel baseline would need
 * screenshot-diffing this suite does not have. If that class of defect
 * ever needs coverage, it needs a maintained visual baseline, not a DOM
 * assertion.
 */
const MAPS_ERROR_RE = /Google Maps JavaScript API error:/;

test("/prime Google Maps key is valid (currently RED — see file header, needs-ruling item 1)", async ({
  page,
}) => {
  const guard = await installNoWriteGuard(page);
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => {
    pageErrors.push(err.message);
  });

  const response = await page.goto("/prime", { waitUntil: "domcontentloaded" });
  expect(
    response?.ok(),
    `/prime navigation failed: ${response?.status()}`,
  ).toBe(true);

  // Give the Maps SDK time to load, attempt initialization, and (today)
  // fail — measured live this takes a few seconds after DOM content loads.
  await page.waitForTimeout(6_000);

  // Positive signal #1: the Maps SDK's own global namespace actually
  // loaded (catches: 404 on the page, a script blocked by CSP, a DNS
  // failure reaching maps.googleapis.com — none of which leave a matching
  // console error string, because the SDK never got far enough to log
  // one).
  const mapsSdkLoaded = await page.evaluate(
    () =>
      typeof (window as unknown as { google?: { maps?: unknown } }).google
        ?.maps === "object",
  );
  expect(
    mapsSdkLoaded,
    "window.google.maps never loaded — the Maps SDK script itself failed " +
      "(404 / CSP / DNS), not just the key",
  ).toBe(true);

  // Positive signal #2: the real element this page renders once loaded
  // (Map3DElement, PrimeMap3D.tsx's `new Map3DElement(...)` appended into
  // mapContainerRef) is actually present.
  const mapElementCount = await page.locator("gmp-map-3d").count();
  expect(
    mapElementCount,
    "no <gmp-map-3d> element in the DOM — PrimeMap3D never got far enough " +
      "to construct the map",
  ).toBeGreaterThan(0);

  // Positive signal #3: the inline "Loading 3D Map" skeleton
  // (PrimeMap3D.tsx, gated on its own `isLoaded` state) is gone — a map
  // stuck loading forever is exactly what an anonymous visitor sees as
  // "the product never showed up".
  const skeletonStillShowing = await page
    .getByText("Loading 3D Map", { exact: true })
    .isVisible()
    .catch(() => false);
  expect(
    skeletonStillShowing,
    "the 'Loading 3D Map' skeleton never went away",
  ).toBe(false);

  // Existing signal, kept and BROADENED (see file header): any Google Maps
  // JS API error, by its stable message prefix, not an enumerated list of
  // today's known error codes.
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

  expect(
    guard.unexpectedWrites().map((r) => `${r.method()} ${r.url()}`),
    "an unblocked write reached production — see _support/no-write-context.ts",
  ).toEqual([]);
});
