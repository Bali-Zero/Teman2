import { test, expect } from "@playwright/test";

/**
 * Seeded-failure self-test (family #2 — "a sentinel that greens while dead is
 * worse than none"). This is NOT a production defect probe: it is a
 * deterministic, network-free assertion that is DESIGNED to fail on every
 * single invocation, forever.
 *
 * WHY. A cron wrapper that runs Playwright, greps the JSON report, and only
 * ever alerts when it finds a `status: "failed"` entry is trusting that its
 * own detection code still works. That code can silently rot (a reporter
 * flag renamed upstream, a JSON schema change, a grep pattern typo) and the
 * wrapper would keep reporting "0 failures" forever — cron-theater, exactly
 * the class this whole lane exists to cure. This test is the tripwire:
 * `scripts/journey_sentinel.sh` looks up THIS test's title in the report and
 * treats anything other than `"failed"` as proof the detection pipeline
 * itself is broken — a DIFFERENT, higher-severity alert than a real journey
 * defect (see the wrapper's SELFTEST_TITLE constant, kept byte-identical to
 * the string below on purpose).
 *
 * Do not "fix" this test. Do not wrap it in try/catch. Do not make it
 * conditional. A green run of THIS test is the bug.
 */
test("[SEEDED-FAILURE SELF-TEST] must always fail — proves the sentinel can detect red", () => {
  expect(
    1,
    "This assertion is DESIGNED to fail every run. If you are reading this " +
      "in a CI log and wondering why it's red: it's supposed to be. See the " +
      "file header for why.",
  ).toBe(2);
});
