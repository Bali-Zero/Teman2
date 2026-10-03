import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import BlogLoading from "./loading";
import ArticleLoading from "./[category]/[slug]/loading";

// Next streams a loading.tsx as the Suspense fallback in the initial HTML of
// every (blog) page, so a dark fallback flashes black over the R19 paper
// before the content arrives (live 2026-09-27: `bg-[#0a0a0f]` in /privacy's
// HTML). The fallback must inherit the layout's surface instead.
const DARK = /bg-\[#0a0a0f\]|border-white\/|text-white\b|bg-black\b/;

function classes(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("[class]")).map(
    (el) => el.getAttribute("class") ?? "",
  );
}

describe("(blog) loading fallbacks carry no pre-R19 dark styling", () => {
  it("the (blog) group fallback", () => {
    const { container } = render(<BlogLoading />);
    expect(classes(container).filter((c) => DARK.test(c))).toEqual([]);
  });

  it("the article fallback", () => {
    const { container } = render(<ArticleLoading />);
    expect(classes(container).filter((c) => DARK.test(c))).toEqual([]);
  });
});
