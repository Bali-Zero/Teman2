/**
 * R19 guard (Property Check PR-2, spec-property-check-v2.md, 2026-09-28):
 * `/property/eligibility` moved onto R19 tokens by owner decision. This
 * component paints almost entirely through inline `style` (not Tailwind
 * classes), so the DOM check below scans both `class` AND `style` attribute
 * text — the r19-b-common FORBIDDEN list applies regardless of which one a
 * value lives in. Must be RED against origin/main's version of this file
 * (glassmorphism card: linear-gradient/radial-gradient + backdropFilter +
 * literal-hex box-shadow) and GREEN after the restyle — see the lane report
 * for the red tail.
 *
 * The hex check is NOT part of the DOM scan (gate-7596-report.md F7): jsdom,
 * like every real browser, serialises an inline `color: #abc` to
 * `rgb(...)` on the element's `style` attribute, so a DOM-based hex regex is
 * permanently dead code — it can never see the literal that was authored.
 * The hex check below instead scans the component's OWNED SOURCE TEXT, where
 * the literal still reads as `#abc`. A literal hex value INSIDE a
 * `var(--x, #hex)` fallback is the one sanctioned exception, so `var(...)`
 * spans are stripped before that check runs.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
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
  });
  return hits;
}

// F7 (gate-7596-report.md): a DOM-serialised hex check can never fire — jsdom
// (and every real browser) serialises an inline `color: #abc` to
// `rgb(...)` on `element.style.cssText`/`getAttribute("style")`, so the old
// `forbiddenHitsIn` hex regex was permanently dead code (13/13 green against
// a mutant that reintroduced literal hex). This scans the OWNED SOURCE FILE
// text instead, following the pattern in
// app/globals.rumah-putih.guard.test.ts: a literal `#hex` is only legal
// inside a `var(--x, #hex)` fallback slot, so every balanced `var(...)` span
// is stripped first (same strip used by the R19 CSS guard on globals.css),
// and anything left containing `#[0-9a-fA-F]{3,8}` is a violation.
// Minor (gate-7596-report.md v2): extended to every file the PR owns under
// apps/mouth/src/app/property/eligibility/, not just the component.
const PROPERTY_ROUTE_DIR = join(
  __dirname,
  "..",
  "..",
  "app",
  "property",
  "eligibility",
);
const SOURCE_FILES = [
  join(__dirname, "PropertyEligibilityBody.tsx"),
  join(PROPERTY_ROUTE_DIR, "layout.tsx"),
  join(PROPERTY_ROUTE_DIR, "page.tsx"),
  join(PROPERTY_ROUTE_DIR, "r19-funnel-frame.module.css"),
];

function stripVarFallbacks(text: string): string {
  let prev: string;
  let out = text;
  do {
    prev = out;
    out = out.replace(/var\([^()]*\)/g, "");
  } while (out !== prev);
  return out;
}

async function fillAndAnalyze() {
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

  it("result card (zone + verdict + villa PMA caveat) has no forbidden classes/styles", async () => {
    const { container } = render(<PropertyEligibilityBody />);
    await fillAndAnalyze();
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it.each(SOURCE_FILES)(
    "%s has no literal #hex color outside a var(--x, #hex) fallback",
    (file) => {
      const source = readFileSync(file, "utf-8");
      const stripped = stripVarFallbacks(source);
      const hexMatches = stripped.match(/#[0-9a-fA-F]{3,8}/g) ?? [];
      expect(hexMatches).toEqual([]);
    },
  );
});
