import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";

// The consumer-wiring probe (see the second describe block): the page composes its
// sections at MODULE LOAD, so each case sets `extraExcluded` and then imports the
// page fresh. With an empty set this delegates to the real filter, so the first
// block below is the real behaviour, not a stub.
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

async function renderTeamPage() {
  const { default: TeamPage } = await import("./page");
  render(<TeamPage />);
}

function html(): string {
  return document.body.innerHTML;
}

beforeEach(() => {
  vi.resetModules();
  extraExcluded.clear();
});

describe("/team — the public directory", () => {
  it("does not publish the two people the owner excluded", async () => {
    await renderTeamPage();

    // Not by name, not under the other spelling of the first one, not through a
    // photo path or an alt text: the whole rendered document is checked.
    expect(html()).not.toMatch(/faisha|faysha|sahira/i);
    expect(screen.queryByText("Faisha")).toBeNull();
    expect(screen.queryByText("Sahira")).toBeNull();
  });

  it("keeps every other person, with the role label this page carries today", async () => {
    await renderTeamPage();

    const expected: Array<[string, string]> = [
      ["Pak Heru", "Komisaris · Founder (30 years)"],
      ["Zainal Abidin", "Chief Executive Officer · Founder"],
      ["Ruslana", "Special Advisory"],
      ["Veronika", "Manager"],
      ["Adit", "Supervisor · Lead Setup"],
      ["Ari", "Supervisor"],
      ["Krisna", "Specialist Consultant"],
      ["Dea", "Executive Consultant"],
      ["Candra", "Consultant"],
      ["Vino", "Junior Consultant"],
      ["Angel", "Tax Supervisor"],
      ["Kadek", "Tax Consultant"],
      ["Dewa Ayu", "Tax Consultant"],
      ["Asya Nadia", "Accountant"],
      ["Rina", "Reception"],
      ["Zero", "SOTA Marketing"],
      ["Surya", "Marketing Specialist"],
      ["Damar", "Marketing Junior"],
      ["Subhi", "AI"],
    ];

    for (const [name, role] of expected) {
      const heading = screen.getByRole("heading", { name, level: 3 });
      expect(heading, `${name} is missing`).toBeInTheDocument();
      expect(
        heading.parentElement?.textContent,
        `${name} lost the role label "${role}"`,
      ).toContain(role);
    }
    // 19 people, no more: the two excluded are the only difference from the
    // composition this page shipped before.
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(
      expected.length,
    );
  });

  it("sends each tool owner to the real page of the tool", async () => {
    await renderTeamPage();

    const studio = screen.getByRole("link", { name: /Second Home Studio/i });
    expect(studio).toHaveAttribute("href", "/visa/second-home/studio");
    const evoa = screen.getByRole("link", { name: /E-VOA/i });
    expect(evoa).toHaveAttribute("href", "/visa/voa");
  });

  it("keeps the reviews block and the trust figures it already showed", async () => {
    await renderTeamPage();

    expect(screen.getAllByText(/5,000\+/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Licensed since 2006/)).toBeInTheDocument();
    // the curated Google reviews block still renders under the directory
    expect(screen.getByText(/Marco R\./)).toBeInTheDocument();
  });

  it("gives every section of the directory a heading its nav can reach", async () => {
    await renderTeamPage();

    for (const id of [
      "leadership",
      "setup",
      "tax",
      "accounting",
      "marketing",
    ]) {
      expect(document.getElementById(id), `#${id} is missing`).not.toBeNull();
    }
  });
});

describe("/team — the exclusion filter is wired into this consumer", () => {
  it("drops a person the filter excludes, whoever it is", async () => {
    // Guilt probe: with the filter reporting Candra as not publicly listed, the
    // page must stop rendering Candra. If this page ever stops routing its
    // editorial entries through publicEntries(), this case goes green→red.
    extraExcluded.add("candra");
    await renderTeamPage();

    expect(screen.queryByText("Candra")).toBeNull();
    // and nobody else is disturbed
    expect(
      screen.getByRole("heading", { name: "Vino", level: 3 }),
    ).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: "Adit", level: 3 }),
    ).toBeTruthy();
  });

  it("applies the filter to every section, not only the first", async () => {
    extraExcluded.add("kadek"); // tax
    extraExcluded.add("damar"); // marketing
    extraExcluded.add("rina"); // accounting
    await renderTeamPage();

    expect(screen.queryByText("Kadek")).toBeNull();
    expect(screen.queryByText("Damar")).toBeNull();
    expect(screen.queryByText("Rina")).toBeNull();
  });
});
