import { render, screen, fireEvent } from "@testing-library/react";
import { I18nProvider } from "@/i18n";
import {
  LOCALES,
  LOCALE_FLAGS,
  LOCALE_NAMES,
  OFFERED_LOCALES,
  type Locale,
} from "@/i18n/types";
import { PublicNav } from "@/components/nav/PublicNav";

/**
 * Supported ≠ offered (2026-07-29).
 *
 * `ru`/`fr` were withdrawn from the language picker while staying fully
 * SERVED. Two halves, and the second is the one that bites: shrinking
 * LOCALES instead of OFFERED_LOCALES would strand ~967 translation files
 * and 404 every `?lang=ru` / `?lang=fr` link already in the wild.
 *
 * GUILT   — the picker no longer offers ru/fr.
 * INNOCENCE — ru/fr are still supported, still restored from a saved
 * preference, and still labelled honestly in the badge.
 */

function renderNav() {
  return render(
    <I18nProvider>
      <PublicNav showLangSwitcher />
    </I18nProvider>,
  );
}

/**
 * The dropdown is closed on mount, so asserting a language is ABSENT from an
 * unopened menu passes for the wrong reason. Every absence check below opens
 * the menu first and sits next to a positive control.
 */
function openLangMenu(activeCode: string) {
  fireEvent.click(screen.getByRole("button", { name: activeCode }));
}

describe("offered vs supported locales", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  // ── GUILT ────────────────────────────────────────────────────────────────
  it("does not offer ru or fr", () => {
    expect(OFFERED_LOCALES).not.toContain("ru");
    expect(OFFERED_LOCALES).not.toContain("fr");
    expect(OFFERED_LOCALES).toEqual(["en", "id", "it"]);
  });

  it("the nav switcher renders exactly the offered languages", () => {
    renderNav();
    openLangMenu("EN");

    // Positive control first: if these are missing the menu never opened and
    // the absence assertions below would be vacuous.
    for (const code of OFFERED_LOCALES) {
      expect(
        screen.getAllByText(LOCALE_NAMES[code]).length,
      ).toBeGreaterThanOrEqual(1);
    }
    expect(screen.queryByText("Français")).toBeNull();
    expect(screen.queryByText("Русский")).toBeNull();
  });

  // ── INNOCENCE ────────────────────────────────────────────────────────────
  it("still SUPPORTS ru and fr — withdrawing from the picker never unserves a locale", () => {
    expect(LOCALES).toContain("ru");
    expect(LOCALES).toContain("fr");
  });

  it("every offered locale is a supported one", () => {
    for (const code of OFFERED_LOCALES) {
      expect(LOCALES).toContain(code);
    }
  });

  it("names and flags cover every SUPPORTED locale, not just the offered ones", () => {
    for (const code of LOCALES) {
      expect(LOCALE_NAMES[code]).toBeTruthy();
      expect(LOCALE_FLAGS[code]).toBeTruthy();
    }
  });

  it("restores a saved fr preference — an existing visitor keeps their language", () => {
    localStorage.setItem("blog-language", "fr");
    renderNav();

    expect(document.documentElement.lang).toBe("fr");
  });

  it("labels an active-but-unoffered locale honestly instead of falling back to EN", () => {
    localStorage.setItem("blog-language", "ru");
    renderNav();

    expect(screen.getByText("RU")).toBeInTheDocument();
    expect(screen.queryByText("EN")).toBeNull();
  });

  it("lets a visitor on an unoffered locale switch back out", () => {
    localStorage.setItem("blog-language", "fr");
    renderNav();
    openLangMenu("FR");

    fireEvent.click(screen.getByRole("button", { name: /English/ }));

    expect(localStorage.getItem("blog-language")).toBe("en");
    expect(document.documentElement.lang).toBe("en");
  });
});

describe("locale lists are typed as Locale, not loose strings", () => {
  it("accepts only declared locales", () => {
    const sample: Locale[] = [...LOCALES];
    expect(new Set(sample).size).toBe(LOCALES.length);
  });
});
