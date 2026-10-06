import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The 2025 compliance alert on /kbli-explorer showed a pulsing
 * "Extraction Protocol Available" badge next to its only button. No
 * extraction protocol exists: the button opens BlackBookModal, which hands
 * the visitor to WhatsApp (#7739 established that no dossier exists). The
 * badge was false urgency on a compliance firm's public tool, the same
 * class as the RESTRICTED badge removed from the transition banner.
 * Measured at 279d063447.
 *
 * Declared limits: reads LegacyAlert.tsx as text; it does not render.
 */
const SRC = readFileSync(join(__dirname, "LegacyAlert.tsx"), "utf8");

describe("LegacyAlert makes no claim the page cannot back", () => {
  it("positive control: the alert and its one action are still there", () => {
    expect(SRC).toContain("2025 COMPLIANCE ALERT");
    expect(SRC).toContain("ASK WHICH CODE REPLACES IT");
    expect(SRC).toContain("onClick={onOpenBlackBook}");
  });

  it("no 'Extraction Protocol' badge", () => {
    expect(SRC).not.toMatch(/extraction protocol/i);
  });

  it("no pulsing decoration left in the alert", () => {
    expect(SRC).not.toContain("animate-pulse");
  });
});
