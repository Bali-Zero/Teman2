/**
 * R19 group-B / surface-2+3 guard (CLAUDE.md Builder Contract, R19 restyle,
 * 2026-09-28): renders NewsletterForm's inline and sidebar variants under an
 * active R19 context, then fails if any element's className carries a
 * pre-R19 literal-color / gradient / hardcoded-dark utility. It must be RED
 * against origin/main's version of this file and GREEN after the restyle
 * (see the lane report for the red tail).
 *
 * The non-R19 (`isR19 === false`, e.g. the `/property` category listing —
 * `routePolicy.ts::isR19Route` excludes it) render is a DIFFERENT case:
 * these files deliberately KEEP the pre-R19 violet/fuchsia look there, so a
 * separate assertion checks the opposite direction (the legacy skin is
 * still there, unchanged) instead of applying the same forbidden-class
 * guard to it.
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
  });
});
