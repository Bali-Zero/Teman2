/**
 * R19 group-B / surface-2+3 guard (CLAUDE.md Builder Contract, R19 restyle,
 * 2026-09-28): renders NewsletterForm's inline and sidebar variants under an
 * active R19 context, then fails if any element's className carries a
 * pre-R19 literal-color / gradient / hardcoded-dark utility. It must be RED
 * against origin/main's version of this file and GREEN after the restyle
 * (see the lane report for the red tail).
 *
 * The non-R19 render (`isR19 === false`) is a DIFFERENT case. No live route
 * reaches it today: both consumers (CategoryContent, ArticleClient) sit under
 * routes where `isR19Route` is true. It still keeps the pre-R19 look
 * verbatim, so the last two cases assert the legacy panel AND the full legacy
 * token set of every input. A fresh gate (2026-09-28) caught
 * `focus:outline-none` missing from that branch.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { R19HomeProvider } from "@/components/r19/R19Presentation";

vi.mock("@/lib/blog/newsletter", () => ({
  subscribeToNewsletter: vi
    .fn()
    .mockResolvedValue({ success: true, message: "ok" }),
}));

import { NewsletterInline, NewsletterSidebar } from "./NewsletterForm";

const FORBIDDEN = [
  // literal hex color in a className (a var() fallback lives in inline
  // style, never in a class string, so any hex here is a real offender)
  /#[0-9a-fA-F]{3,8}/,
  /bg-gradient-/,
  /linear-gradient/,
  /(^|\s)(bg|text|border|from|via|to)-(sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo)-\d+/,
  /(^|\s)text-white(\/\d+)?(\s|$)/,
  /(^|\s)bg-black(\/\d+)?(\s|$)/,
  /(^|\s)border-white(\/\d*)?(\s|$)/,
  /(^|\s)bg-white(\/\d+)?(\s|$)/,
  /font-black/,
  /font-extrabold/,
];

// origin/main's input classes, verbatim; the non-R19 branch must keep all of them.
const LEGACY_SIDEBAR_INPUT = [
  "bg-white/5",
  "border",
  "border-white/10",
  "text-white",
  "placeholder-white/40",
  "focus:outline-none",
  "focus:ring-2",
  "focus:ring-violet-500/50",
];
const LEGACY_INLINE_INPUT = [
  ...LEGACY_SIDEBAR_INPUT,
  "focus:border-violet-500/50",
];

function forbiddenHitsIn(container: HTMLElement): string[] {
  const hits: string[] = [];
  container.querySelectorAll("[class]").forEach((el) => {
    const cls = el.getAttribute("class") || "";
    for (const re of FORBIDDEN) {
      if (re.test(cls)) hits.push(`${el.tagName}.${cls} -> ${re}`);
    }
  });
  return hits;
}

describe("R19 group-B surface-2/3 guard: NewsletterForm", () => {
  it("NewsletterInline idle state (R19 route context)", () => {
    const { container } = render(
      <R19HomeProvider>
        <NewsletterInline />
      </R19HomeProvider>,
    );
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("NewsletterInline error state (R19 route context)", () => {
    const { container } = render(
      <R19HomeProvider>
        <NewsletterInline />
      </R19HomeProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: /subscribe/i }));
    expect(
      screen.getByText("Please enter a valid email address"),
    ).toBeInTheDocument();
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("NewsletterSidebar idle state incl. open category dropdown (R19 route context)", () => {
    const { container } = render(
      <R19HomeProvider>
        <NewsletterSidebar defaultCategories={["visas"]} />
      </R19HomeProvider>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /topics? selected|select topics/i }),
    );
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("NewsletterSidebar error state (R19 route context)", () => {
    const { container } = render(
      <R19HomeProvider>
        <NewsletterSidebar defaultCategories={[]} />
      </R19HomeProvider>,
    );
    // The email input is `required type="email"`, so a real click on the
    // submit button never reaches the JS handler while it's empty — the
    // browser's own constraint validation blocks it first. Dispatch the
    // submit event directly (as `fireEvent.submit` does) to exercise the
    // component's own validation branch and its R19 styling, same as the
    // lane report's "failed submit" screenshot.
    fireEvent.submit(container.querySelector("form")!);
    expect(
      screen.getByText("Please enter a valid email address"),
    ).toBeInTheDocument();
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("NewsletterSidebar success state (R19 route context)", async () => {
    const { container } = render(
      <R19HomeProvider>
        <NewsletterSidebar defaultCategories={["visas"]} />
      </R19HomeProvider>,
    );
    fireEvent.change(screen.getByLabelText(/email address/i), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /subscribe/i }));
    await waitFor(() =>
      expect(screen.getByText("Welcome Aboard!")).toBeInTheDocument(),
    );
    expect(forbiddenHitsIn(container)).toEqual([]);
  });

  it("non-R19 context keeps the legacy violet/fuchsia sidebar unchanged (behavior preserved)", () => {
    const { container } = render(
      <NewsletterSidebar defaultCategories={["visas"]} />,
    );
    const panel = container.firstElementChild as HTMLElement;
    expect(panel.className).toMatch(/from-violet-500\/10 to-fuchsia-500\/10/);
    expect(panel.className).toMatch(/border-violet-500\/20/);
    const inputs = Array.from(container.querySelectorAll("input"));
    expect(inputs.length).toBe(2);
    for (const input of inputs) {
      const tokens = (input.getAttribute("class") || "").split(/\s+/);
      expect(tokens).toEqual(expect.arrayContaining(LEGACY_SIDEBAR_INPUT));
    }
  });

  it("non-R19 context keeps the legacy inline input token set verbatim", () => {
    const { container } = render(<NewsletterInline />);
    const input = container.querySelector("input") as HTMLInputElement;
    const tokens = (input.getAttribute("class") || "").split(/\s+/);
    expect(tokens).toEqual(expect.arrayContaining(LEGACY_INLINE_INPUT));
  });
});
