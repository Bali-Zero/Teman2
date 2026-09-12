import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";

// Same shape as the other consumer probes: the page builds its people at MODULE
// LOAD, so each case sets `extraExcluded` and imports fresh. Empty set → the real
// filter.
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

async function renderAboutPage() {
  const { default: AboutPage } = await import("./page");
  render(<AboutPage />);
}

beforeEach(() => {
  vi.resetModules();
  extraExcluded.clear();
});

describe("/v2/company/about", () => {
  it("publishes neither excluded person", async () => {
    await renderAboutPage();
    expect(document.body.innerHTML).not.toMatch(/faisha|faysha|sahira/i);
  });

  it("keeps the five people it shows today", async () => {
    await renderAboutPage();

    for (const name of [
      "Zainal Abidin",
      "Pak Heru",
      "Ruslana",
      "Krisna",
      "Asya Nadia",
    ]) {
      expect(screen.getByText(name), `${name} is missing`).toBeInTheDocument();
    }
    expect(screen.getByText("CEO · Founder")).toBeInTheDocument();
    expect(screen.getByText("Setup Lead")).toBeInTheDocument();
  });

  it("drops a person the filter excludes, whoever it is", async () => {
    // Guilt probe: neither excluded person is listed on this page today, so only
    // a filter reporting somebody it DOES list can prove the wiring.
    extraExcluded.add("krisna");
    await renderAboutPage();

    expect(screen.queryByText("Krisna")).toBeNull();
    expect(screen.getByText("Ruslana")).toBeInTheDocument();
  });
});
