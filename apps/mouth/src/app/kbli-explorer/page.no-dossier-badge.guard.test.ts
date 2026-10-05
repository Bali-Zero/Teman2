import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The transition banner on /kbli-explorer drew a "KBLI 2025 Dossier" card
 * with a red, pulsing "RESTRICTED" badge. #7739 established that no dossier
 * exists and nothing is restricted: the banner only opens a WhatsApp hand-off.
 * The picture promised a document and urgency that the page cannot back.
 *
 * Declared limits: this reads the source, it does not render the page.
 */
const PAGE = readFileSync(join(__dirname, "page.tsx"), "utf8");

describe("/kbli-explorer transition banner artwork", () => {
  it("positive control: the banner this guard anchors on exists", () => {
    expect(PAGE).toContain("Are your company codes still valid?");
  });

  it("does not depict a dossier that does not exist", () => {
    expect(PAGE).not.toMatch(/Dossier/);
  });

  it("does not show a pulsing RESTRICTED badge", () => {
    expect(PAGE).not.toContain("RESTRICTED");
  });
});
