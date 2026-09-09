import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { notFound } from "next/navigation";
import { decodeAuthoredTranslation } from "../../../lib/server/article-translations";
import ArticlePage from "./page";

const translations = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/server/article-translations", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../lib/server/article-translations")>(),
  loadAuthoredTranslations: translations,
}));

vi.mock("next/server", () => ({ connection: vi.fn(async () => {}) }));
vi.mock("next/navigation", () => ({ notFound: vi.fn(() => { throw new Error("NEXT_NOT_FOUND"); }), redirect: vi.fn(() => { throw new Error("NEXT_REDIRECT"); }) }));

const params = () => Promise.resolve({ category: "business", slug: "published-story" });
const article = { category: "business", slug: "published-story", title: "Published story", status: "published", noIndex: false, publishedAt: "2026-01-02", content: "A published article." };
afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
beforeEach(() => { translations.mockResolvedValue({}); });

describe("article availability", () => {
  it.each(["id", "it", "ru", "fr"] as const)("renders the authored %s edition only after checking current publication", async (lang) => {
    const edition = decodeAuthoredTranslation(`---\ntitle: Authored translation\nslug: published-story\ncategory: business\nlocale: ${lang}\npublishedAt: "2026-01-02"\n---\n## Authored section\n\nComplete translated body.`, "business", "published-story", lang);
    translations.mockResolvedValue({ [lang]: edition });
    const fetcher = vi.fn(async () => new Response(JSON.stringify(article), { headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(await ArticlePage({ params: params(), searchParams: Promise.resolve({ lang, token: "private-reference" }) }));
    expect(screen.getByRole("heading", { level: 1, name: "Authored translation" })).toBeVisible();
    expect(container.querySelector(`article[lang="${lang}"]`)).not.toBeNull();
    expect(screen.getByText("Complete translated body.")).toBeVisible();
    expect(fetcher).toHaveBeenCalled();
    expect(container.innerHTML).not.toContain("private-reference");
  });
  it("labels the English fallback honestly when an authored edition is absent", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(article), { headers: { "content-type": "application/json" } })));
    const { container } = render(await ArticlePage({ params: params(), searchParams: Promise.resolve({ lang: "it" }) }));
    expect(screen.getByText(/You are reading the English article/)).toBeVisible();
    expect(container.querySelector('article[lang="en"]')).not.toBeNull();
    expect(screen.getByRole("heading", { level: 1, name: "Published story" })).toBeVisible();
  });
  it.each(["de", "../../portal", ["it", "id"]])("rejects unsupported or ambiguous locale %s", async (lang) => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    await expect(ArticlePage({ params: params(), searchParams: Promise.resolve({ lang }) })).rejects.toThrow("NEXT_NOT_FOUND");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it.each(["server failure", "timeout", "transport failure"])("offers retry and the original source during %s instead of a 404", async (failure) => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      if (failure === "timeout") throw new DOMException("Timed out", "TimeoutError");
      if (failure === "transport failure") throw new TypeError("Network unavailable");
      return new Response(null, { status: 503 });
    }));
    render(await ArticlePage({ params: params() }));
    expect(screen.getByRole("heading", { level: 1, name: "This story is temporarily unavailable." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Try again" })).toHaveAttribute("href", "/business/published-story");
    expect(screen.getByRole("link", { name: /Read the original article/ })).toHaveAttribute("href", "/legacy/business/published-story");
    expect(notFound).not.toHaveBeenCalled();
    expect(translations).not.toHaveBeenCalled();
  });

  it.each(["missing", "unpublished", "hidden", "wrong identity"])("keeps %s articles on the not-found path", async (state) => {
    vi.stubGlobal("fetch", vi.fn(async () => state === "missing"
      ? new Response(null, { status: 404 })
      : new Response(JSON.stringify({ ...article, ...(state === "unpublished" ? { status: "draft" } : state === "hidden" ? { noIndex: true } : { slug: "another-story" }) }), { headers: { "content-type": "application/json" } })));
    await expect(ArticlePage({ params: params() })).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFound).toHaveBeenCalledOnce();
    expect(translations).not.toHaveBeenCalled();
  });
});
