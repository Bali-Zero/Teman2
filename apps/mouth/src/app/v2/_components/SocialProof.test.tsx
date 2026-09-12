import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";

// Same shape as the other consumer probes: the component builds its people at
// MODULE LOAD, so each case sets `extraExcluded` and imports fresh. Empty set →
// the real filter, so everything below is real behaviour unless stated.
const extraExcluded = new Set<string>();

vi.mock("@/lib/team-public-listing", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/team-public-listing")>();
  return {
    ...actual,
    publicEntries: <T extends { slug?: string }>(entries: readonly T[]) =>
      actual
        .publicEntries(entries)
        .filter((e) => !e.slug || !extraExcluded.has(e.slug)),
  };
});

async function renderSocialProof(props?: { variant?: "founder-band" }) {
  const { SocialProof } = await import("./SocialProof");
  render(props ? <SocialProof {...props} /> : <SocialProof />);
}

beforeEach(() => {
  vi.resetModules();
  extraExcluded.clear();
});

describe("SocialProof — the default render (what /v2 gets)", () => {
  it("still shows the founders and the four people behind them", async () => {
    await renderSocialProof();

    expect(screen.getByText("Zainal & Heru")).toBeInTheDocument();
    expect(screen.getByText("Zainal Abidin")).toBeInTheDocument();
    expect(screen.getByText("Pak Heru")).toBeInTheDocument();
    expect(screen.getByText("The team behind them")).toBeInTheDocument();
    for (const name of ["Ruslana", "Veronika", "Adit", "Angel"]) {
      expect(screen.getByText(name), `${name} is missing`).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: /All 18\+/ })).toHaveAttribute(
      "href",
      "/team",
    );
  });

  it("still shows the reviews and the trust strip", async () => {
    await renderSocialProof();

    expect(screen.getByText(/Marco R\./)).toBeInTheDocument();
    expect(screen.getByText("4.9")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /See all reviews on Google Maps/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/5,000\+ Clients since 2020/)).toBeInTheDocument();
  });
});

describe("SocialProof — the founder-band variant (what the home opts into)", () => {
  it("shows the two founders and nobody else", async () => {
    await renderSocialProof({ variant: "founder-band" });

    expect(screen.getByText("Zainal Abidin")).toBeInTheDocument();
    expect(screen.getByText("Pak Heru")).toBeInTheDocument();
    expect(screen.queryByText("The team behind them")).toBeNull();
    for (const name of ["Ruslana", "Veronika", "Adit", "Angel"]) {
      expect(screen.queryByText(name), `${name} should not be here`).toBeNull();
    }
  });

  it("carries one link to the directory", async () => {
    await renderSocialProof({ variant: "founder-band" });

    const links = screen
      .getAllByRole("link")
      .filter((a) => a.getAttribute("href") === "/team");
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveTextContent(/Meet the team/);
    expect(screen.queryByRole("link", { name: /All 18\+/ })).toBeNull();
  });

  it("keeps the reviews and the trust strip of the default", async () => {
    await renderSocialProof({ variant: "founder-band" });

    expect(screen.getByText(/Marco R\./)).toBeInTheDocument();
    expect(screen.getByText("4.9")).toBeInTheDocument();
    expect(screen.getByText(/5,000\+ Clients since 2020/)).toBeInTheDocument();
  });
});

describe("SocialProof — the exclusion filter is wired into this consumer", () => {
  it("publishes neither excluded person, in either variant", async () => {
    await renderSocialProof();
    expect(document.body.innerHTML).not.toMatch(/faisha|faysha|sahira/i);

    document.body.innerHTML = "";
    vi.resetModules();
    await renderSocialProof({ variant: "founder-band" });
    expect(document.body.innerHTML).not.toMatch(/faisha|faysha|sahira/i);
  });

  it("drops a person the filter excludes, whoever it is", async () => {
    // Guilt probe: neither excluded person is listed by this component today, so
    // only a filter reporting somebody it DOES list can prove the wiring. If the
    // component stops routing its entries through publicEntries(), this fails.
    extraExcluded.add("adit");
    await renderSocialProof();

    expect(screen.queryByText("Adit")).toBeNull();
    expect(screen.getByText("Angel")).toBeInTheDocument();
  });

  it("applies the filter to the founders too", async () => {
    extraExcluded.add("heru");
    await renderSocialProof({ variant: "founder-band" });

    expect(screen.queryByText("Pak Heru")).toBeNull();
    expect(screen.getByText("Zainal Abidin")).toBeInTheDocument();
  });
});
