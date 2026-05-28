import { afterEach, describe, expect, it, vi } from "vitest";

import { safeHtml, safeHtmlChat, safeMiniMarkdown } from "./safe-html";

describe("safeHtml", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sanitizes dangerous browser HTML while preserving allowed formatting", () => {
    const result = safeHtml(
      '<p onclick="steal()">Hello <strong>Zero</strong><script>alert(1)</script></p>',
    );

    expect(result.__html).toContain("<strong>Zero</strong>");
    expect(result.__html).toContain("Hello");
    expect(result.__html).not.toContain("onclick");
    expect(result.__html).not.toContain("<script");
    expect(result.__html).not.toContain("alert(1)");
  });

  it("merges custom config overrides", () => {
    const result = safeHtml("<strong>Bold</strong><em>Italic</em>", {
      ALLOWED_TAGS: ["em"],
      ALLOWED_ATTR: [],
    });

    expect(result.__html).toBe("Bold<em>Italic</em>");
  });

  it("handles empty input", () => {
    expect(safeHtml("")).toEqual({ __html: "" });
  });

  it("escapes all markup during server-side rendering", () => {
    vi.stubGlobal("window", undefined);

    const result = safeHtml(
      '<img src=x onerror="steal()"><b>"quoted" & raw</b>',
    );

    expect(result.__html).toBe(
      "&lt;img src=x onerror=&quot;steal()&quot;&gt;&lt;b&gt;&quot;quoted&quot; &amp; raw&lt;/b&gt;",
    );
  });

  it("returns empty escaped HTML during server-side rendering", () => {
    vi.stubGlobal("window", undefined);

    expect(safeHtml("")).toEqual({ __html: "" });
  });
});

describe("safeHtmlChat", () => {
  it("allows only inline chat formatting", () => {
    const result = safeHtmlChat(
      '<p>Paragraph</p><strong>Bold</strong><a href="https://example.com" onclick="x()">Link</a><script>x()</script>',
    );

    expect(result.__html).toContain("Paragraph");
    expect(result.__html).toContain("<strong>Bold</strong>");
    expect(result.__html).toContain('<a href="https://example.com">Link</a>');
    expect(result.__html).not.toContain("<p>");
    expect(result.__html).not.toContain("onclick");
    expect(result.__html).not.toContain("<script");
  });
});

describe("safeMiniMarkdown", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sanitizes rendered mini-markdown in the browser", () => {
    const result = safeMiniMarkdown({
      __html:
        '<strong>Safe</strong><a href="https://example.com" onclick="x()">Link</a><img src=x onerror="x()">',
    });

    expect(result.__html).toContain("<strong>Safe</strong>");
    expect(result.__html).toContain('<a href="https://example.com">Link</a>');
    expect(result.__html).not.toContain("<img");
    expect(result.__html).not.toContain("onclick");
    expect(result.__html).not.toContain("onerror");
  });

  it("returns rendered mini-markdown unchanged during server-side rendering", () => {
    vi.stubGlobal("window", undefined);
    const rendered = { __html: "<strong>Already escaped</strong>" };

    expect(safeMiniMarkdown(rendered)).toBe(rendered);
  });
});
