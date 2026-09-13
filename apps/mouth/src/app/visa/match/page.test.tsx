import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Retired-door guard (W-VO-C, 2026-09-13).
 *
 * This file used to hold the W0b telemetry regression guard: the v1 visa funnel
 * died silently for three months because submit failure was swallowed into
 * `setSubmitError` with no event. That antibody is NOT lost with the wizard it
 * watched — `formSubmitFailed(endpoint, status)` is still pinned on the two
 * wizards that remain, `visa/clock/page.test.tsx` and `lib/funnel-app-events.test.ts`.
 * What retires here is the free-text quiz itself (RULING Zero 2026-08-25).
 *
 * `[hash]` result pages are untouched and keep their own render tests: a link
 * already shared with a visitor must still resolve (acceptance A5).
 */

const permanentRedirectMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  permanentRedirect: permanentRedirectMock,
}));

import VisaMatchPage from "./page";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const SOURCE = fs.readFileSync(path.join(DIR, "page.tsx"), "utf8");

describe("/visa/match — retired legacy quiz", () => {
  beforeEach(() => {
    permanentRedirectMock.mockClear();
  });

  it("permanently redirects to the Oracle", () => {
    VisaMatchPage();
    expect(permanentRedirectMock).toHaveBeenCalledWith("/visa-oracle");
  });

  it("keeps no wizard body behind the redirect", () => {
    expect(SOURCE).not.toContain("use client");
    for (const legacy of ["AppWizard", "AppFrame", "useFunnelApp", "fetch("]) {
      expect(SOURCE).not.toContain(legacy);
    }
  });

  it("leaves the shared result route in place (deep links still resolve)", () => {
    expect(fs.existsSync(path.join(DIR, "[hash]", "page.tsx"))).toBe(true);
  });
});
