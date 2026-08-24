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

  it("the only CTA is the free fit memo WhatsApp handoff", () => {
    renderLanding();

    const cta = screen.getByRole("link", { name: /free fit memo/i });
    expect(cta).toHaveAttribute("data-lead-source", "cta_handoff");
    // No "apply now" flow anywhere on the page.
    expect(screen.queryByRole("link", { name: /apply/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /apply/i })).toBeNull();
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
