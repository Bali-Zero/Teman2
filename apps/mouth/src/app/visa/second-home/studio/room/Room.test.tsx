import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { usePricingData } from "@/hooks/usePricingData";
import { R19_CLASS } from "@/lib/theme/r19Vars";
import { StudioApp } from "../StudioApp";

vi.mock("@/hooks/usePricingData", () => ({ usePricingData: vi.fn() }));

describe("the room — wall, desk, shelf around the wizard", () => {
  beforeEach(() => {
    localStorage.clear();
    window.location.hash = "";
    vi.mocked(usePricingData).mockReturnValue({
      price: null,
      isLoading: false,
      isError: false,
    });
  });

  it("the wrapper is an R19 Direction A room, not a Merah Putih page", () => {
    const { container } = render(<StudioApp />);
    const room = container.querySelector(".bz-shs-room") as HTMLElement;
    expect(room).not.toBeNull();
    expect(room.classList.contains(R19_CLASS)).toBe(true);
    expect(room.classList.contains("merah-putih-day")).toBe(false);
    expect(room.style.getPropertyValue("--surface-base").toUpperCase()).toBe(
      "#F7F4EE",
    );
    expect(room.style.getPropertyValue("--border-strong").toUpperCase()).toBe(
      "#7B817F",
    );
  });

  it("the wall hangs Ari from the roster and the labelled rail; the desk holds the sheet", () => {
    render(<StudioApp />);
    const wall = screen.getByRole("complementary", { name: "On the wall" });
    expect(
      within(wall).getByText("Ari · Team Leader, Setup"),
    ).toBeInTheDocument();
    expect(within(wall).getByText("This is Ari's desk.")).toBeInTheDocument();
    expect(within(wall).getByRole("progressbar")).toBeInTheDocument();
    const desk = screen.getByRole("main", { name: "Ari's desk" });
    expect(within(desk).getByRole("radiogroup")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("Ari and the chart share one wrapper that becomes a single strip above the sheet on mobile", () => {
    const { container } = render(<StudioApp />);
    const strip = container.querySelector<HTMLElement>(".bz-shs-wall-top");
    expect(strip).not.toBeNull();
    expect(
      within(strip!).getByText("Ari · Team Leader, Setup"),
    ).toBeInTheDocument();
    expect(within(strip!).getByRole("progressbar")).toBeInTheDocument();
    // jsdom has no layout; the ≤72px strip is proven by the render probe. This
    // pins the rule that builds it: below 64rem the wrapper is the strip,
    // ordered before the desk, avatar column 40px.
    const css = readFileSync(resolve(__dirname, "studio-room.css"), "utf-8");
    expect(css).toMatch(
      /@media \(max-width: 63\.99rem\)\s*\{[^@]*?\.bz-shs-room \.bz-shs-wall-top\s*\{[^}]*order:\s*2;[^}]*grid-template-columns:\s*40px/,
    );
  });

  it("opening a drawer mid-flow leaves the question, the answer and the saved plan untouched", () => {
    render(<StudioApp />);
    fireEvent.click(screen.getByRole("radio", { name: "Under 55" }));
    const saved = localStorage.getItem("bz_shs_plan_v1");
    expect(saved).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /^Facts/ }));
    const dialog = screen.getByRole("dialog", { name: "Facts" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));

    expect(localStorage.getItem("bz_shs_plan_v1")).toBe(saved);
    expect(screen.getByRole("radio", { name: "Under 55" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(
      screen.getByRole("heading", { name: /how old are you/i }),
    ).toBeInTheDocument();
  });
});
