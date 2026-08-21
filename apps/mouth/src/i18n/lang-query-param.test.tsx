import { render, screen } from "@testing-library/react";
import { I18nProvider, useTranslation } from "@/i18n";
import { LANG_OWNER_ATTR, LANG_OWNER_CONTENT } from "@/i18n/content-locale";

/**
 * `?lang=<locale>` (2026-08-20).
 *
 * A shared link (`?lang=it`) did nothing on first load: the provider only
 * ever initialized from the saved `blog-language` preference, so a
 * first-time visitor following a localized link got the default locale
 * regardless of what the URL asked for, even though full translations
 * exist. The fix reads the query param once on mount and, if it is on the
 * LOCALES whitelist, lets it win for THIS VISIT — without ever persisting
 * it to localStorage, so it can never clobber an explicit saved choice.
 *
 * GUILT     — a valid `?lang` overrides the (absent or present) saved value.
 * INNOCENCE — an invalid `?lang` is ignored; no `?lang` is unaffected;
 *             a page that owns `<html lang>` keeps its own value.
 */

function LocaleProbe() {
  const { locale } = useTranslation();
  return <span data-testid="locale">{locale}</span>;
}

function renderProvider() {
  return render(
    <I18nProvider>
      <LocaleProbe />
    </I18nProvider>,
  );
}

describe("I18nProvider honors ?lang= on first load", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute(LANG_OWNER_ATTR);
    document.documentElement.lang = "en";
    window.history.replaceState({}, "", "/");
  });

  // ── GUILT ────────────────────────────────────────────────────────────────
  it("?lang=it becomes the provider locale without touching localStorage", () => {
    window.history.replaceState({}, "", "/?lang=it");

    renderProvider();

    expect(screen.getByTestId("locale").textContent).toBe("it");
    expect(localStorage.getItem("blog-language")).toBeNull();
    expect(document.documentElement.lang).toBe("it");
  });

  it("?lang=it takes precedence over an existing saved preference, still without persisting it", () => {
    localStorage.setItem("blog-language", "en");
    window.history.replaceState({}, "", "/?lang=it");

    renderProvider();

    expect(screen.getByTestId("locale").textContent).toBe("it");
    // The saved preference is untouched — a link must not overwrite it.
    expect(localStorage.getItem("blog-language")).toBe("en");
  });

  // ── INNOCENCE ────────────────────────────────────────────────────────────
  it("an unknown ?lang=zz falls back to the saved localStorage preference", () => {
    localStorage.setItem("blog-language", "id");
    window.history.replaceState({}, "", "/?lang=zz");

    renderProvider();

    expect(screen.getByTestId("locale").textContent).toBe("id");
    expect(localStorage.getItem("blog-language")).toBe("id");
  });

  it("an unknown ?lang=zz with no saved preference stays on the default locale", () => {
    window.history.replaceState({}, "", "/?lang=zz");

    renderProvider();

    expect(screen.getByTestId("locale").textContent).toBe("en");
  });

  it("no ?lang param — existing localStorage-only behavior is unchanged", () => {
    localStorage.setItem("blog-language", "fr");
    window.history.replaceState({}, "", "/");

    renderProvider();

    expect(screen.getByTestId("locale").textContent).toBe("fr");
  });

  it("?lang=it with a page owning lang does not overwrite documentElement.lang", () => {
    document.documentElement.setAttribute(LANG_OWNER_ATTR, LANG_OWNER_CONTENT);
    document.documentElement.lang = "en";
    window.history.replaceState({}, "", "/?lang=it");

    renderProvider();

    // The UI-chrome locale still switches (translations/picker follow it)...
    expect(screen.getByTestId("locale").textContent).toBe("it");
    // ...but the page's declared content language is not clobbered.
    expect(document.documentElement.lang).toBe("en");
  });
});
