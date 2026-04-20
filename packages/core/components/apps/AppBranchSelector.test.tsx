import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { AppBranchSelector } from "./AppBranchSelector";

const opts = [
  { id: "clock", title: "A", description: "first", href: "/a" },
  { id: "match", title: "B", description: "second", href: "/b" },
];

describe("AppBranchSelector", () => {
  beforeEach(() => {
    vi.stubGlobal("navigator", { vibrate: vi.fn(() => true) });
    window.matchMedia = vi.fn().mockImplementation((q: string) => ({
      matches: false,
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders both option titles", () => {
    const { getByText } = render(
      <AppBranchSelector question="Q?" options={opts as any} />,
    );
    expect(getByText("A")).toBeTruthy();
    expect(getByText("B")).toBeTruthy();
  });

  it("fires onSelect with the chosen option when clicked", () => {
    const onSelect = vi.fn();
    const { getByText } = render(
      <AppBranchSelector question="Q?" options={opts as any} onSelect={onSelect} />,
    );
    fireEvent.click(getByText("A"));
    expect(onSelect).toHaveBeenCalledWith(opts[0]);
  });

  it("calls navigator.vibrate(8) on tap (haptic)", () => {
    const { getByText } = render(
      <AppBranchSelector question="Q?" options={opts as any} />,
    );
    fireEvent.click(getByText("B"));
    expect(navigator.vibrate).toHaveBeenCalledWith(8);
  });
});
