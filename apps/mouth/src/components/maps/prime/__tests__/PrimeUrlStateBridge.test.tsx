import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import {
  PrimeNexusProvider,
  usePrimeNexus,
} from "@/contexts/PrimeNexusContext";

// Override the global next/navigation mock (set in src/test/setup.tsx)
// to return a populated querystring for these tests.
const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace,
    push: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => new URLSearchParams("layers=kkop,lp2b&compareA=Z9"),
  usePathname: () => "/prime",
}));

import { PrimeUrlStateBridge } from "../PrimeUrlStateBridge";

function Probe() {
  const ctx = usePrimeNexus();
  return (
    <>
      <span data-testid="kkop">{String(ctx.layers.kkop)}</span>
      <span data-testid="lp2b">{String(ctx.layers.lp2b)}</span>
      <span data-testid="zoneColors">{String(ctx.layers.zoneColors)}</span>
      <span data-testid="A">{ctx.compareA?.id ?? "none"}</span>
    </>
  );
}

describe("PrimeUrlStateBridge", () => {
  it("hydrates context from URL on mount", () => {
    render(
      <PrimeNexusProvider>
        <PrimeUrlStateBridge />
        <Probe />
      </PrimeNexusProvider>,
    );
    expect(screen.getByTestId("kkop")).toHaveTextContent("true");
    expect(screen.getByTestId("lp2b")).toHaveTextContent("true");
    // zoneColors was ON by default but URL only specifies kkop+lp2b → should be off
    expect(screen.getByTestId("zoneColors")).toHaveTextContent("false");
    expect(screen.getByTestId("A")).toHaveTextContent("Z9");
  });
});
