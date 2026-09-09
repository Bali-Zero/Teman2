import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AboutPage, { metadata as aboutMetadata } from "../app/about/page";
import TeamPage from "../app/team/page";
import { responsibilityGroups } from "../content/team";

describe("company content and responsibility journeys", () => {
  it("keeps the public company story on its canonical route", () => {
    expect(aboutMetadata.title).not.toBe("Bali Zero — Website development");
    expect(AboutPage).toEqual(expect.any(Function));
  });

  it("restores factual company context and practical steps without unsupported historical claims", () => {
    render(<AboutPage />);
    const main = screen.getByRole("main");
    expect(main).toHaveTextContent(
      "Bali Zero was founded by Zainal Abidin and Pak Heru.",
    );
    expect(main).toHaveTextContent("Kerobokan, Bali");
    expect(main).not.toHaveTextContent(
      /2006|2019|2020|5,000|licensed|friends for|trained on every/i,
    );
    const method = screen.getByRole("region", {
      name: "From a question to a practical next step.",
    });
    expect(within(method).getAllByRole("listitem")).toHaveLength(3);
    expect(
      within(method).getByRole("link", { name: "Find your starting point" }),
    ).toHaveAttribute("href", "/#tools");
    expect(
      within(method).getByRole("link", { name: "Explore service details" }),
    ).toHaveAttribute("href", "/services");
    expect(
      within(method).getByRole("link", { name: "Plan a conversation" }),
    ).toHaveAttribute("href", "/contact?from=about");
    const expertise = screen.getByRole("region", {
      name: "The work behind your next chapter.",
    });
    const expectedRoutes = [
      "/services/immigration",
      "/services/company-setup",
      "/services/tax",
      "/services/property",
      "/services/compliance",
    ];
    expect(
      within(expertise)
        .getAllByRole("link")
        .map((link) => link.getAttribute("href")),
    ).toEqual(expectedRoutes);
  });

  it("groups the exact approved roster once and preserves project responsibilities", () => {
    render(<TeamPage />);
    const expected = {
      "Setup & advisory": ["Adit", "Krisna", "Candra", "Vino", "Damar", "Dea"],
      Tax: ["Veronika", "Dewa Ayu", "Angel"],
      Accounting: ["Asya"],
      "Projects & digital tools": ["Ari", "Surya", "Subhi"],
    };
    for (const [name, people] of Object.entries(expected)) {
      const group = screen.getByRole("region", { name });
      expect(
        within(group)
          .getAllByRole("heading", { level: 3 })
          .map((heading) => heading.textContent),
      ).toEqual(people);
    }
    expect(
      responsibilityGroups.flatMap((group) => [...group.people]).sort(),
    ).toEqual(Object.values(expected).flat().sort());
    expect(screen.getAllByRole("article")).toHaveLength(16);
    expect(
      screen.getByRole("link", { name: "Explore Second Home Studio" }),
    ).toHaveAttribute("href", "/#second-home-studio");
    expect(screen.getByRole("link", { name: "Explore E-VOA" })).toHaveAttribute(
      "href",
      "/#evoa",
    );
    expect(
      screen.getByRole("link", { name: "Discuss accounting support" }),
    ).toHaveAttribute("href", "/contact?from=team&topic=tax");
  });

  it("gives every responsibility jump link a visible destination", () => {
    const { container } = render(<TeamPage />);
    const navigation = screen.getByRole("navigation", {
      name: "Team responsibilities",
    });
    for (const link of within(navigation).getAllByRole("link")) {
      const target = container.querySelector(link.getAttribute("href")!);
      expect(target).toBeInTheDocument();
      expect(target).toBeVisible();
    }
  });

  it.each([AboutPage, TeamPage])(
    "uses the shared public shell and keeps account functions separate",
    (Page) => {
      render(<Page />);
      const navigation = screen.getByRole("navigation", {
        name: "Main navigation",
      });
      expect(
        within(navigation).getByRole("link", { name: "My account" }),
      ).toHaveAttribute("href", "https://my.balizero.com/");
      expect(screen.getByRole("contentinfo")).toBeInTheDocument();
      expect(
        within(screen.getByRole("contentinfo")).getByRole("link", {
          name: "Our story",
        }),
      ).toHaveAttribute("href", "/about");
      expect(screen.getAllByRole("main")).toHaveLength(1);
      expect(screen.getAllByRole("banner")).toHaveLength(1);
    },
  );
});
