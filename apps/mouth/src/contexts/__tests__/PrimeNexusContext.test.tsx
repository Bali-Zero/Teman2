import { render, screen, act } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
  DEFAULT_MAP_LAYERS,
  type ZoneSelection,
} from "../PrimeNexusContext";

const Z1: ZoneSelection = {
  id: "Z1",
  name: "Sanur",
  zoneCode: "C-1",
  info: {},
};
const Z2: ZoneSelection = {
  id: "Z2",
  name: "Canggu",
  zoneCode: "R-2",
  info: {},
};
const Z3: ZoneSelection = {
  id: "Z3",
  name: "Ubud",
  zoneCode: "P-3",
  info: {},
};

function Probe() {
  const ctx = usePrimeNexus();
  return (
    <div>
      <span data-testid="zoneColors">{String(ctx.layers.zoneColors)}</span>
      <span data-testid="kkop">{String(ctx.layers.kkop)}</span>
      <span data-testid="lp2b">{String(ctx.layers.lp2b)}</span>
      <span data-testid="A">{ctx.compareA?.id ?? "none"}</span>
      <span data-testid="B">{ctx.compareB?.id ?? "none"}</span>
      <button onClick={() => ctx.toggleLayer("kkop")}>toggle-kkop</button>
      <button onClick={() => ctx.isolateLayer("kkop")}>isolate-kkop</button>
      <button onClick={() => ctx.addToCompare(Z1)}>add-Z1</button>
      <button onClick={() => ctx.addToCompare(Z2)}>add-Z2</button>
      <button onClick={() => ctx.addToCompare(Z3)}>add-Z3</button>
      <button onClick={() => ctx.clearCompareAll()}>clear</button>
    </div>
  );
}

describe("PrimeNexusContext layer + compare", () => {
  it("starts with DEFAULT_MAP_LAYERS", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    expect(screen.getByTestId("zoneColors")).toHaveTextContent("true");
    expect(screen.getByTestId("kkop")).toHaveTextContent("false");
    expect(DEFAULT_MAP_LAYERS.zoneColors).toBe(true);
  });

  it("toggleLayer flips a single layer", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    act(() => {
      screen.getByText("toggle-kkop").click();
    });
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
    expect(screen.getByTestId("zoneColors")).toHaveTextContent("true");
  });

  it("isolateLayer turns off every other layer", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    act(() => {
      screen.getByText("isolate-kkop").click();
    });
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
    expect(screen.getByTestId("zoneColors")).toHaveTextContent("false");
    expect(screen.getByTestId("lp2b")).toHaveTextContent("false");
  });

  it("addToCompare fills A then B", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    act(() => {
      screen.getByText("add-Z1").click();
    });
    expect(screen.getByTestId("A")).toHaveTextContent("Z1");
    expect(screen.getByTestId("B")).toHaveTextContent("none");
    act(() => {
      screen.getByText("add-Z2").click();
    });
    expect(screen.getByTestId("A")).toHaveTextContent("Z1");
    expect(screen.getByTestId("B")).toHaveTextContent("Z2");
  });

  it("addToCompare rotates when both slots full: A ← B, B ← new", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    act(() => {
      screen.getByText("add-Z1").click();
    });
    act(() => {
      screen.getByText("add-Z2").click();
    });
    act(() => {
      screen.getByText("add-Z3").click();
    });
    expect(screen.getByTestId("A")).toHaveTextContent("Z2");
    expect(screen.getByTestId("B")).toHaveTextContent("Z3");
  });

  it("clearCompareAll empties both slots", () => {
    render(
      <PrimeNexusProvider>
        <Probe />
      </PrimeNexusProvider>,
    );
    act(() => {
      screen.getByText("add-Z1").click();
    });
    act(() => {
      screen.getByText("add-Z2").click();
    });
    act(() => {
      screen.getByText("clear").click();
    });
    expect(screen.getByTestId("A")).toHaveTextContent("none");
    expect(screen.getByTestId("B")).toHaveTextContent("none");
  });
});
