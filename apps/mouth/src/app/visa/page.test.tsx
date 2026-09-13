import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Retired-door guard (W-VO-C, 2026-09-13).
 *
 * RULING Zero 2026-08-25: «Due porte: 301 → `/visa-oracle` subito». The defect
 * this pins is not "the redirect is missing" — it is the shape the defect took
 * for nineteen days: two doors answering 200, and the indexable one being the
 * legacy quiz rather than the funnel carrying the signed RulePack.
 *
 * Guilt AND innocence, because a redirect is trivially reintroduced as a
 * wrapper around a still-rendering quiz: the first test proves the door
 * redirects, the second proves there is no quiz left behind it to fall back to.
 */

const permanentRedirectMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  permanentRedirect: permanentRedirectMock,
}));

import VisaEntryPage from "./page";

const SOURCE = fs.readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), "page.tsx"),
  "utf8",
);

describe("/visa — retired legacy door", () => {
  beforeEach(() => {
    permanentRedirectMock.mockClear();
  });

  it("permanently redirects to the Oracle", () => {
    VisaEntryPage();
    expect(permanentRedirectMock).toHaveBeenCalledWith("/visa-oracle");
  });

  it("keeps no legacy quiz body behind the redirect", () => {
    expect(SOURCE).not.toContain("use client");
    for (const legacy of [
      "AppBranchSelector",
      "AppWizard",
      "AppFrame",
      "useFunnelApp",
      "/visa/match",
    ]) {
      expect(SOURCE).not.toContain(legacy);
    }
  });
});
