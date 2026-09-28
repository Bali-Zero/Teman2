/**
 * R19 guard (Property Check PR-2, spec-property-check.md, 2026-09-28):
 * `/property/eligibility` moved onto R19 tokens by owner decision. This
 * component paints almost entirely through inline `style` (not Tailwind
 * classes), so the guard scans both `class` AND `style` attribute text —
 * the r19-b-common FORBIDDEN list applies regardless of which one a value
 * lives in. A literal hex value INSIDE a `var(--x, #hex)` fallback is the
 * one sanctioned exception, so `var(...)` spans are stripped before the hex
 * check runs. Must be RED against origin/main's version of this file
 * (glassmorphism card: linear-gradient/radial-gradient + backdropFilter +
 * literal-hex box-shadow) and GREEN after the restyle — see the lane report
 * for the red tail.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { PropertyEligibilityBody } from "./PropertyEligibilityBody";

vi.mock("@/lib/analytics", () => ({
  trackPropertyAnalyzeCTA: vi.fn(),
  trackPropertyWACTA: vi.fn(),
  trackPropertyBuyerSelected: vi.fn(),
  trackPropertyUseSelected: vi.fn(),
}));

const FORBIDDEN_CLASS = [
  /bg-gradient-/,
  /(^|\s)(bg|text|border|from|via|to)-(sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-\d+/,
  /(^|\s)text-white(\/\d+)?(\s|$)/,
  /(^|\s)bg-black(\/\d+)?(\s|$)/,
  /(^|\s)border-white(\/\d*)?(\s|$)/,
  /(^|\s)bg-white(\/\d+)?(\s|$)/,
  /font-black/,
  /font-extrabold/,
];

const FORBIDDEN_IN_STYLE = [
  /linear-gradient/,
  /radial-gradient/,
  /backdrop-filter/i,
];

function stripVarFallbacks(style: string): string {
  // Remove balanced var(...) spans so a whitelisted `var(--x, #hex)`
  // fallback never trips the bare-hex check below.
  let prev: string;
  let out = style;
  do {
    prev = out;
    out = out.replace(/var\([^()]*\)/g, "");
  } while (out !== prev);
  return out;
}

function forbiddenHitsIn(container: HTMLElement): string[] {
  const hits: string[] = [];
  container.querySelectorAll("[class],[style]").forEach((el) => {
    const cls = el.getAttribute("class") || "";
    for (const re of FORBIDDEN_CLASS) {
      if (re.test(cls)) hits.push(`class:${el.tagName}.${cls} -> ${re}`);
    }
    const style = el.getAttribute("style") || "";
    for (const re of FORBIDDEN_IN_STYLE) {
      if (re.test(style)) hits.push(`style:${el.tagName} "${style}" -> ${re}`);
    }
    const stripped = stripVarFallbacks(style);
    if (/#[0-9a-fA-F]{3,8}/.test(stripped)) {
      hits.push(`style-hex:${el.tagName} "${style}"`);
    }
  });
  return hits;
}

async function fillAndAnalyze(kbliState: string | null) {
  fireEvent.change(screen.getByPlaceholderText(/Google Maps/i), {
    target: { value: "-8.65, 115.13" },
  });
  fireEvent.change(screen.getByLabelText(/Buyer profile/i), {
    target: { value: "wna_pma" },
  });
  fireEvent.change(screen.getByLabelText(/Intended use/i), {
    target: { value: "villa_rental" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Analyze/i }));
  await waitFor(() => expect(screen.getByText(/C-1/)).toBeInTheDocument());
  void kbliState;
}

describe("R19 guard: PropertyEligibilityBody", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: "analyzed",
        zone: {
          code: "C-1",
          name: "High-Intensity Mixed Use",
          desa: "Desa Canggu",
          kdb: "60%",
          klb: "1,8",
          tb: "15 Meter",
        },
        kbli: {
          code: "68112",
          title: "Aktivitas Penyewaan Bangunan dan Lahan Hunian",
          state: "WARNING",
          reason: "PMA_NOT_VERIFIED",
          max_foreign_ownership: null,
        },
        verdict: {
          can_invest: true,
          risk_level: "MEDIUM",
          score: 63,
          label: "YELLOW",
        },
        opportunities: [
          { title_en: "Villas", category_en: "Hospitality", pma_open: true },
        ],
      }),
    } as unknown as Response);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("idle form has no forbidden classes/styles", () => {
    const { container } = render(<PropertyEligibilityBody />);
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("result card (zone + verdict + kbli caveat) has no forbidden classes/styles", async () => {
    const { container } = render(<PropertyEligibilityBody />);
    await fillAndAnalyze("WARNING");
    expect(forbiddenHitsIn(container)).toEqual([]);
  });
});
