import { render, act } from "@testing-library/react";
import { I18nProvider } from "@/i18n";
import {
  LANG_OWNER_ATTR,
  LANG_OWNER_CONTENT,
  resolveContentLocale,
} from "@/i18n/content-locale";
import { ContentLangSync } from "@/i18n/ContentLangSync";

/**
 * `<html lang>` describes the language of the document's CONTENT.
 *
 * Two writers wanted that field: the I18nProvider (UI-chrome locale, from the
 * `blog-language` preference) and the article route (the locale the SERVER
 * actually served, which falls back to English when no translation exists).
 * With no rule, whichever ran last won and the document could claim a
 * language its body was not in. These tests pin the rule in both directions.
 */

describe("resolveContentLocale — the served locale, not the requested one", () => {
  it("GUILT: a requested locale with no translation on disk resolves to English", () => {
    // getArticleByLocale falls back to English here, so declaring "fr" would
    // put a French label on an English article — the same defect, inverted.
    expect(resolveContentLocale("fr", ["en"])).toBe("en");
  });

  it("INNOCENCE: a requested locale that DOES exist is honoured", () => {
    expect(resolveContentLocale("fr", ["en", "fr"])).toBe("fr");
    expect(resolveContentLocale("id", ["en", "id", "it"])).toBe("id");
  });

  it("no ?lang at all is English", () => {
    expect(resolveContentLocale(undefined, ["en", "it"])).toBe("en");
    expect(resolveContentLocale(null, ["en", "it"])).toBe("en");
    expect(resolveContentLocale("", ["en", "it"])).toBe("en");
  });

  it("a locale the site does not support is English even if a file claims it", () => {
    expect(resolveContentLocale("de", ["en", "de"])).toBe("en");
    expect(resolveContentLocale("zh", ["en", "zh"])).toBe("en");
  });
});

describe("a hostile ?lang never becomes the declared language", () => {
  // The value originates in searchParams, so it is attacker-controlled all
  // the way to `<html lang>`. The allow-list is what stops it.
  it("GUILT: an injection payload collapses to the default", () => {
    expect(resolveContentLocale('";alert(document.cookie);//', ["en"])).toBe(
      "en",
    );
    expect(
      resolveContentLocale("</script><script>alert(1)</script>", ["en"]),
    ).toBe("en");
  });

  it("GUILT: it collapses even when the 'available' list vouches for it", () => {
    const hostile = '"><img src=x onerror=alert(1)>';
    expect(resolveContentLocale(hostile, ["en", hostile])).toBe("en");
  });
});

describe("the two writers of <html lang>", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute(LANG_OWNER_ATTR);
    document.documentElement.lang = "en";
  });

  it("GUILT: the provider does NOT overwrite a page-owned lang", () => {
    // A reader whose chrome preference is Italian, on an English article.
    render(<ContentLangSync locale="en" />);
    localStorage.setItem("blog-language", "it");

    render(
      <I18nProvider>
        <span />
      </I18nProvider>,
    );

    expect(document.documentElement.lang).toBe("en");
  });

  it("INNOCENCE: with no page owner, the provider still describes the document", () => {
    localStorage.setItem("blog-language", "it");

    render(
      <I18nProvider>
        <span />
      </I18nProvider>,
    );

    expect(document.documentElement.lang).toBe("it");
  });

  it("ContentLangSync declares the served locale and takes ownership", () => {
    render(<ContentLangSync locale="fr" />);

    expect(document.documentElement.lang).toBe("fr");
    expect(document.documentElement.getAttribute(LANG_OWNER_ATTR)).toBe(
      LANG_OWNER_CONTENT,
    );
  });

  it("releases ownership on unmount, so ordinary pages go back to the provider", () => {
    const { unmount } = render(<ContentLangSync locale="fr" />);
    expect(document.documentElement.getAttribute(LANG_OWNER_ATTR)).toBe(
      LANG_OWNER_CONTENT,
    );

    act(() => unmount());

    expect(document.documentElement.getAttribute(LANG_OWNER_ATTR)).toBeNull();
  });

  it("follows a client-side navigation to an article in another language", () => {
    const { rerender } = render(<ContentLangSync locale="it" />);
    expect(document.documentElement.lang).toBe("it");

    rerender(<ContentLangSync locale="id" />);

    expect(document.documentElement.lang).toBe("id");
  });
});
