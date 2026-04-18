import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, beforeEach } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
} from "@/contexts/PrimeNexusContext";
import { PrimeLayerLegend } from "../PrimeLayerLegend";

function Probe() {
  const ctx = usePrimeNexus();
  return <span data-testid="kkop">{String(ctx.layers.kkop)}</span>;
}

describe("PrimeLayerLegend", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders 7 rows with role=switch", () => {
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
      </PrimeNexusProvider>,
    );
    const switches = screen.getAllByRole("switch");
    expect(switches.length).toBe(7);
  });

  it("click toggles a layer", async () => {
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
        <Probe />
      </PrimeNexusProvider>,
    );
    expect(screen.getByTestId("kkop")).toHaveTextContent("false");
    await userEvent.click(screen.getByRole("switch", { name: /kkop/i }));
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
  });

  it("shift+click isolates a layer", async () => {
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
        <Probe />
      </PrimeNexusProvider>,
    );
    const user = userEvent.setup();
    await user.keyboard("{Shift>}");
    await user.click(screen.getByRole("switch", { name: /kkop/i }));
    await user.keyboard("{/Shift}");
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
    expect(
      screen.getByRole("switch", { name: /zone colors/i }),
    ).toHaveAttribute("aria-checked", "false");
  });

  it("collapses and persists via localStorage", async () => {
    const { unmount } = render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
      </PrimeNexusProvider>,
    );
    await userEvent.click(
      screen.getByRole("button", { name: /collapse legend/i }),
    );
    expect(screen.queryAllByRole("switch")).toHaveLength(0);
    unmount();
    render(
      <PrimeNexusProvider>
        <PrimeLayerLegend />
      </PrimeNexusProvider>,
    );
    expect(screen.queryAllByRole("switch")).toHaveLength(0);
  });
});
