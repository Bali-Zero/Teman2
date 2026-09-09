import { existsSync } from "node:fs";
import { join } from "node:path";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Team } from "./Team";
import TeamPage from "../app/team/page";
import { boardMember, founders, teamMembers } from "../content/team";

describe("team journey", () => {
  it("keeps only the two founder portraits in the homepage band and opens the local team page", () => {
    const { container } = render(<Team />);
    expect(screen.getAllByRole("img")).toHaveLength(2);
    for (const founder of founders) expect(screen.getByRole("img", { name: founder.name })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Meet our team" })).toHaveAttribute("href", "/team");
    expect(container.querySelector('img[src*="atlas"]')).toBeNull();
  });

  it("preserves all current people and existing roles on the dedicated page without removed members", () => {
    const { container } = render(<TeamPage />);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    screen.getByRole("main").focus();
    expect(screen.getByRole("main")).toHaveFocus();
    expect(screen.getAllByRole("article")).toHaveLength(16);
    for (const person of [...founders, boardMember, ...teamMembers]) {
      const heading = screen.getByRole("heading", { name: person.name, level: 3 });
      expect(within(heading.closest("article")!).getByText(person.role)).toBeInTheDocument();
      expect(screen.getByRole("img", { name: person.name })).toBeInTheDocument();
    }
    expect(container.textContent).not.toMatch(/Faysha|Fayisha|Sahira/i);
    for (const image of container.querySelectorAll("img")) {
      expect(existsSync(join(process.cwd(), "public", image.getAttribute("src")!))).toBe(true);
    }
  });
});
