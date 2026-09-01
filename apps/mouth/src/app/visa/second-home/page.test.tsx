import { render, screen, within } from "@testing-library/react";
import { cormorant } from "@balizero/core/fonts/cormorant";
import { I18nProvider } from "@/i18n";
import { getExactSnapshotPrice } from "@/lib/pricing-snapshot";
import { SecondHomeLanding } from "./SecondHomeLanding";

/**
 * E33 Second Home landing — content guard (2026-07-24).
 *
 * The page is a Fit-Memo funnel with hard claims discipline
 * (research/secondhome/e33-fact-registry.json + owner decisions
 * 2026-07-23). These tests pin:
 *  - the required verified claims are rendered (routes, price, 90-day duty);
 *  - the price is the single all-inclusive figure;
 *  - FORBIDDEN claims never appear (BSI/sharia equivalence, split deposits,
 *    ITAP conversion, "any bank" placement);
 *  - the only CTA is the WhatsApp lead handoff (free fit memo);
 *  - the locale switcher exposes real, crawlable links to each variant
 *    (2026-08-20 — it used to flip locale client-side via a button; each
 *    offered locale now has its own SSG route, see
 *    app/visa/second-home/[locale]/page.tsx).
 */

function renderLanding() {
  return render(
    <I18nProvider>
      <SecondHomeLanding />
    </I18nProvider>,
  );
}

function removeContainerBoundedPixelTracks(template: string): string {
  let unresolved = template;
  let previous: string;

  do {
    previous = unresolved;
    unresolved = unresolved.replace(/\bmin(?:max)?\([^()]*%[^()]*\)/gi, "");
  } while (unresolved !== previous);

  return unresolved;
}

describe("SecondHomeLanding", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders the hero, both qualifying routes, and the all-inclusive price", () => {
    const { container } = renderLanding();

    const heroHeading = screen.getByRole("heading", { level: 1 });
    expect(container.firstElementChild).toHaveClass(cormorant.variable);
    expect(heroHeading).toHaveTextContent(/up to 5 years/i);
    expect(heroHeading).toHaveStyle({
      fontFamily: "var(--font-serif, Georgia, serif)",
    });
    expect(heroHeading.style.fontFamily).not.toMatch(/Cormorant Garamond/i);
    // Two qualifying routes — the only two verified bases.
    expect(screen.getAllByText(/USD 130,000/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/USD 1,000,000/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/state-owned \(BUMN\)/i).length).toBeGreaterThan(
      0,
    );
    // Single all-inclusive figure, never decomposed.
    const expectedPrice = getExactSnapshotPrice(
      "kitas_permits",
      "E33 Second Home (5 Years)",
    );
    expect(expectedPrice).not.toBeNull();
    expect(screen.getByText(expectedPrice as string)).toBeInTheDocument();
  });

  it("keeps every pixel-based grid track bounded by its container", () => {
    const { container } = renderLanding();
    const gridTemplates = Array.from(
      container.querySelectorAll<HTMLElement>("[style]"),
    )
      .map((element) => element.style.gridTemplateColumns)
      .filter(Boolean);

    expect(gridTemplates).not.toHaveLength(0);
    gridTemplates.forEach((template) => {
      const unresolved = removeContainerBoundedPixelTracks(template);
      // Assert on a value that carries the offending template itself, so a
      // failure prints "unsafe fixed pixel grid track: <template>" instead
      // of an opaque boolean — `expect(actual, message)` is a Vitest-4
      // runtime feature the project's `expect` types don't declare (TS2554).
      const unsafeFixedPixelTrack = /\d+(?:\.\d+)?px/i.test(unresolved)
        ? `unsafe fixed pixel grid track: ${template}`
        : null;
      expect(unsafeFixedPixelTrack).toBeNull();
    });
  });

  /**
   * IDR typeface, RULED 2026-09-01 (Zero, Legge 5 — «dobbiamo restare coerenti
   * e non passare a plex mono»). R4's typography table asks for IBM Plex Mono
   * on price figures; that requirement is AMENDED AWAY for these two routes,
   * and the amendment note under the table in
   * research/design/2026-08-27-r4-identity-merah-putih-token-spec.md is the law.
   * Without this test the ruling lives only in prose, and prose does not stop
   * the next session from "fixing" the divergence back toward mono.
   *
   * Sibling of the test below, and they pull in OPPOSITE directions on purpose:
   * the price is an aligned figure and takes tabular digits; the hero
   * statistics are prose and must stay proportional.
   */
  it("renders the IDR price in the page's own serif with tabular figures, never mono", () => {
    renderLanding();

    const expectedPrice = getExactSnapshotPrice(
      "kitas_permits",
      "E33 Second Home (5 Years)",
    );
    expect(expectedPrice).not.toBeNull();

    const price = screen.getByText(expectedPrice as string);
    // Assert on the value, not a boolean, so a failure prints the face that
    // replaced the serif instead of an opaque `expected true to be false`.
    expect(price.style.fontFamily).toBe("var(--font-serif, Georgia, serif)");
    expect(price.style.fontVariantNumeric).toBe("tabular-nums");
    expect(price.style.fontFeatureSettings).toMatch(/tnum/);
  });

  it("keeps the hero statistics proportional rather than tabular", () => {
    renderLanding();

    const hero = screen.getByRole("heading", { level: 1 }).closest("section");
    expect(hero).not.toBeNull();

    ["5 years", "USD 130,000", "Free"].forEach((value) => {
      const statistic = within(hero as HTMLElement).getByText(value, {
        exact: true,
      });
      expect(statistic.style.fontVariantNumeric || "normal").toBe("normal");
      expect(statistic.style.fontFeatureSettings || "normal").toBe("normal");
    });
  });

  it("covers the senior tracks, no-work-rights, and the 90-day duty", () => {
    renderLanding();

    expect(screen.getByText(/E33E — Senior, 5 years/)).toBeInTheDocument();
    expect(screen.getByText(/E33F — Senior, 1 year/)).toBeInTheDocument();
    expect(
      screen.getAllByText(/does not authorize employment/i).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByRole("heading", { name: /90-day evidence duty/i }),
    ).toBeInTheDocument();
  });

  // Hero CTA (2026-08-25): the page's first click target used to sit at
  // 87-90% scroll depth (the studio CTA further down). Pins that a fit-check
  // entry point now exists inside the hero <section> itself, pointing at the
  // same destination as the pre-existing footer instance, and that both
  // pre-existing CTAs (studio footer link + WhatsApp handoff) are untouched.
  it("gives the hero its own fit-check entry point, in addition to the existing ones", () => {
    renderLanding();

    const hero = screen.getByRole("heading", { level: 1 }).closest("section");
    expect(hero).not.toBeNull();

    const heroCta = within(hero as HTMLElement).getByTestId(
      "hero-fit-check-cta",
    );
    expect(heroCta).toHaveAttribute("href", "/visa/second-home/studio");
    expect(heroCta).toHaveTextContent("Start the fit-check");

    // The pre-existing footer instance still exists, same destination.
    const footerCta = screen.getByTestId("footer-fit-check-cta");
    expect(footerCta).toHaveAttribute("href", "/visa/second-home/studio");

    // The WhatsApp handoff is still the only "free fit memo" CTA — the hero
    // addition is a second entry point to the studio, not a re-ranking.
    expect(
      screen.getByRole("link", { name: /free fit memo/i }),
    ).toBeInTheDocument();
  });

  it("the only CTA is the free fit memo WhatsApp handoff", () => {
    renderLanding();

    const cta = screen.getByRole("link", { name: /free fit memo/i });
    expect(cta).toHaveAttribute("data-lead-source", "cta_handoff");
    // No "apply now" flow anywhere on the page.
    expect(screen.queryByRole("link", { name: /apply/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /apply/i })).toBeNull();
  });

  // WCAG AA contrast guard (measured 2026-08-24): white text on the
  // WhatsApp brand green (`#25D366`) computes to ~1.98:1, badly failing the
  // 4.5:1 normal-text floor. Ratified cure
  // (app/(visa-oracle)/visa-oracle/oracle.css:23-30, 2026-07-17 adversarial
  // review): `#0d3a1f` on `#25D366` ~6.45:1. jsdom resolves neither
  // `color-mix()` nor custom properties, so this asserts on the literal
  // inline style value rather than a computed color (confirmed live via
  // Playwright render — see the shipping commit for the measured
  // rgb()/contrast numbers).
  it("keeps the WhatsApp CTA's ink dark enough on the brand green (WCAG AA)", () => {
    renderLanding();

    const cta = screen.getByRole("link", { name: /free fit memo/i });
    // Brand green stays byte-identical — only the ink moves. (jsdom's CSSOM
    // normalizes the literal hex it parses to rgb() form; the var()
    // fallback expression is left as-is since it isn't a plain color.)
    expect(cta.style.background).toBe("var(--accent-whatsapp, #25D366)");
    expect(cta.style.color).toBe("rgb(13, 58, 31)"); // #0d3a1f
    expect(cta.style.color).not.toBe("var(--text-on-accent)");
  });

  it("never states a forbidden claim", () => {
    const { container } = renderLanding();
    const text = container.textContent ?? "";

    // bsi_sharia_accepted / split_deposit_accepted / itap_after_3y_criteria /
    // bank_proof_format — all pending in the fact registry, forbidden on-page.
    expect(text).not.toMatch(/BSI|sharia/i);
    expect(text).not.toMatch(/split/i);
    expect(text).not.toMatch(/ITAP|KITAP|permanent residence/i);
    expect(text).not.toMatch(/any (Indonesian )?bank/i);
    // Dependent add-on is DRAFT — no hard dependent price.
    expect(text).not.toMatch(/12,000,000|12\.000\.000/);
  });

  it("locale switcher exposes crawlable links to each variant, with aria-current on the active one", () => {
    renderLanding();

    const group = within(screen.getByRole("group", { name: "Language" }));

    const en = group.getByRole("link", { name: "en" });
    expect(en).toHaveAttribute("href", "/visa/second-home");
    expect(en).toHaveAttribute("aria-current", "page");

    const it = group.getByRole("link", { name: "it" });
    expect(it).toHaveAttribute("href", "/visa/second-home/it");
    expect(it).not.toHaveAttribute("aria-current");

    const id = group.getByRole("link", { name: "id" });
    expect(id).toHaveAttribute("href", "/visa/second-home/id");
    expect(id).not.toHaveAttribute("aria-current");
  });
});
