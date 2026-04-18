import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
  type ZoneSelection,
} from "@/contexts/PrimeNexusContext";
import { PrimeCompareDrawer } from "../PrimeCompareDrawer";

function ZoneAdder({ zone }: { zone: ZoneSelection }) {
  const ctx = usePrimeNexus();
  return <button onClick={() => ctx.addToCompare(zone)}>add-{zone.id}</button>;
}

const Z1: ZoneSelection = {
  id: "Z1",
  name: "Sanur Commercial",
  zoneCode: "C-1",
  info: { restricted: false, district: "Denpasar" },
};
const Z2: ZoneSelection = {
  id: "Z2",
  name: "Canggu Residential",
  zoneCode: "R-2",
  info: { restricted: true, district: "Badung" },
};

describe("PrimeCompareDrawer", () => {
  it("is hidden when no zones selected", () => {
    render(
      <PrimeNexusProvider>
        <PrimeCompareDrawer />
      </PrimeNexusProvider>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows one card with one zone, then two with delta", async () => {
    render(
      <PrimeNexusProvider>
        <ZoneAdder zone={Z1} />
        <ZoneAdder zone={Z2} />
        <PrimeCompareDrawer />
      </PrimeNexusProvider>,
    );
    await userEvent.click(screen.getByText("add-Z1"));
    expect(
      screen.getByRole("dialog", { name: /zone comparison/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Sanur Commercial")).toBeInTheDocument();
    // Delta section only appears with two zones
    expect(screen.queryByText(/^delta$/i)).toBeNull();
    await userEvent.click(screen.getByText("add-Z2"));
    expect(screen.getByText("Canggu Residential")).toBeInTheDocument();
    expect(screen.getByText(/^delta$/i)).toBeInTheDocument();
  });

  it("ESC clears all slots", async () => {
    render(
      <PrimeNexusProvider>
        <ZoneAdder zone={Z1} />
        <PrimeCompareDrawer />
      </PrimeNexusProvider>,
    );
    await userEvent.click(screen.getByText("add-Z1"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("Clear all button empties slots", async () => {
    render(
      <PrimeNexusProvider>
        <ZoneAdder zone={Z1} />
        <PrimeCompareDrawer />
      </PrimeNexusProvider>,
    );
    await userEvent.click(screen.getByText("add-Z1"));
    await userEvent.click(screen.getByRole("button", { name: /clear all/i }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
