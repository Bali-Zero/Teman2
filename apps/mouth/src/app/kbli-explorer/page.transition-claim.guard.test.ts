import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The transition banner on /kbli-explorer said "Hundreds of KBLI 2020 codes
 * were revoked on Dec 17. The KBLI 2025 transition starts now." Peraturan BPS
 * 7/2025 was enacted 17 Dec 2025, promulgated and in force 18 Dec 2025 (Art. 7),
 * revoked the whole of Peraturan BPS 2/2020 (Art. 6), and gave users 6 months
 * to adjust (Art. 5). "Starts now" stopped being true in June 2026, and
 * "hundreds of codes" has no source in this repo.
 *
 * Declared limits: this reads the source, it does not render the page.
 */
const PAGE = readFileSync(join(__dirname, "page.tsx"), "utf8");

describe("/kbli-explorer transition banner claim", () => {
  it("positive control: the banner this guard anchors on exists", () => {
    expect(PAGE).toContain("Are your company codes still valid?");
  });

  it("cites the regulation that replaced KBLI 2020", () => {
    expect(PAGE).toContain("(Peraturan BPS 7/2025) replaced KBLI 2020");
  });

  it("no longer says the transition starts now or counts revoked codes", () => {
    expect(PAGE).not.toMatch(/transition starts now/i);
    expect(PAGE).not.toMatch(/Hundreds of KBLI/i);
    expect(PAGE).not.toMatch(/revoked on Dec 17/i);
  });
});
