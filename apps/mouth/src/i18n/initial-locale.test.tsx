import { render, screen } from "@testing-library/react";
import { I18nProvider, useTranslation } from "@/i18n";
import { LANG_OWNER_ATTR, LANG_OWNER_CONTENT } from "@/i18n/content-locale";

/**
 * `initialLocale` prop (2026-08-20).
 *
 * The localized `/visa/second-home/{it,id}` SSG pages pin their own
 * language — the URL IS the language choice. A visitor who previously saved
 * "en" as their UI-chrome preference (or arrives with a stray `?lang=en`)
 * must never have that flip an `/it` page back to English: state initializes
 * to `initialLocale` directly (so SSR/SSG output is already correct, no
 * effect needed for the first render), and the init effect skips the
 * `?lang=`/localStorage restore entirely when the prop is set.
 *
 * GUILT     — a saved "en" preference / a stray `?lang=en` does NOT override
 *             a provider pinned to "it".
 * INNOCENCE — omitting the prop is byte-identical to prior behavior (the
 *             existing `?lang=`/localStorage tests in lang-query-param.test
 *             and offered-locales.test pin this; here we additionally pin
 *             that a page with NO initialLocale still honors both).
 */

function LocaleProbe() {
  const { locale } = useTranslation();
  return <span data-testid="locale">{locale}</span>;
}

describe("I18nProvider initialLocale", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute(LANG_OWNER_ATTR);
    document.documentElement.lang = "en";
    window.history.replaceState({}, "", "/");
  });

  // ── GUILT ────────────────────────────────────────────────────────────────
  it("pins the locale on first render — a saved 'en' preference does not flip an /it page", () => {
    localStorage.setItem("blog-language", "en");

    render(
      <I18nProvider initialLocale="it">
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("it");
    // The saved preference is untouched — this route never wrote to it.
    expect(localStorage.getItem("blog-language")).toBe("en");
  });

  it("a stray ?lang=en in the URL does not flip a page pinned to 'it'", () => {
    window.history.replaceState({}, "", "/?lang=en");

    render(
      <I18nProvider initialLocale="it">
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("it");
  });

  it("pins 'id' the same way", () => {
    localStorage.setItem("blog-language", "it");
    window.history.replaceState({}, "", "/?lang=en");

    render(
      <I18nProvider initialLocale="id">
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("id");
  });

  it("initializes to the pinned locale on the very first render — no effect required", () => {
    // React flushes passive effects synchronously inside testing-library's
    // render(), so this alone cannot distinguish "state started correct"
    // from "an effect corrected it after mount". The renderToString-based
    // SSR test in [locale]/page.test.tsx proves the effect-free case
    // directly; this test pins the SAME state value is used for the DOM
    // attribute an effect (ContentLangSync) would otherwise have to fix.
    render(
      <I18nProvider initialLocale="it">
        <LocaleProbe />
      </I18nProvider>,
    );
    expect(screen.getByTestId("locale").textContent).toBe("it");
  });

  it("a page that owns <html lang> keeps its own value even when initialLocale is set", () => {
    document.documentElement.setAttribute(LANG_OWNER_ATTR, LANG_OWNER_CONTENT);
    document.documentElement.lang = "it";

    render(
      <I18nProvider initialLocale="it">
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(document.documentElement.lang).toBe("it");
  });

  // ── INNOCENCE ────────────────────────────────────────────────────────────
  it("omitting initialLocale is byte-identical to prior behavior: ?lang= still wins", () => {
    window.history.replaceState({}, "", "/?lang=it");

    render(
      <I18nProvider>
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("it");
  });

  it("omitting initialLocale is byte-identical to prior behavior: saved preference still wins", () => {
    localStorage.setItem("blog-language", "fr");

    render(
      <I18nProvider>
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("fr");
  });

  it("omitting initialLocale is byte-identical to prior behavior: default is English", () => {
    render(
      <I18nProvider>
        <LocaleProbe />
      </I18nProvider>,
    );

    expect(screen.getByTestId("locale").textContent).toBe("en");
  });
});
