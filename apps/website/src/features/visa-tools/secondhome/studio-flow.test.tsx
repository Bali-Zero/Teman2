import "@testing-library/jest-dom/vitest";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StudioApp } from "./StudioApp";
import { emptyPlan, PLAN_STORAGE_KEY } from "./engine/plan-codec";
import { getCopy } from "./engine/copy";
const savedPlan = () => ({
  ...emptyPlan(),
  age: "under_55" as const,
  route: "deposit" as const,
  capital: "ready_130k" as const,
  horizon: "this_quarter" as const,
  location: "abroad" as const,
});
beforeEach(() => {
  localStorage.clear();
  history.replaceState(null, "", "/visa/second-home/studio");
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(Response.json({ available: false }, { status: 503 })),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
describe("Second Home Studio integration", () => {
  it("restores the complete plan, previews another route without changing it, and persists the checklist", async () => {
    localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(savedPlan()));
    render(<StudioApp />);
    expect(
      await screen.findByText(getCopy("verdict.bands.strong_fit.heading")),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", {
        name: getCopy("scenarioToggle.controlLabel"),
      }),
    );
    expect(screen.getByTestId("scenario-toggle-preview")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem(PLAN_STORAGE_KEY)!).route).toBe(
      "deposit",
    );
    fireEvent.click(
      screen.getByRole("button", { name: getCopy("scenarioToggle.back") }),
    );
    const checkbox = screen.getAllByRole("checkbox")[0];
    fireEvent.click(checkbox);
    expect(
      Object.values(
        JSON.parse(localStorage.getItem(PLAN_STORAGE_KEY)!).checklist,
      ),
    ).toContain(true);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      vi
        .mocked(fetch)
        .mock.calls.every(
          ([url, options]) =>
            String(url).startsWith("/api/service-price?") &&
            options?.method !== "POST",
        ),
    ).toBe(true);
  });
  it("reports clipboard failure honestly, offers the share fragment, and clears only after its second click", async () => {
    localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(savedPlan()));
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error("blocked")) },
    });
    render(<StudioApp />);
    fireEvent.click(
      await screen.findByRole("button", {
        name: getCopy("savePlanBar.copyLinkButton"),
      }),
    );
    expect(
      await screen.findByText(getCopy("savePlanBar.copyFailed")),
    ).toBeInTheDocument();
    expect(
      (
        screen.getByLabelText(
          getCopy("savePlanBar.manualLinkLabel"),
        ) as HTMLInputElement
      ).value,
    ).toContain("/visa/second-home/studio#p=");
    fireEvent.click(
      screen.getByRole("button", { name: getCopy("savePlanBar.clearButton") }),
    );
    expect(localStorage.getItem(PLAN_STORAGE_KEY)).not.toBeNull();
    fireEvent.click(
      screen.getByRole("button", {
        name: getCopy("savePlanBar.clearConfirmButton"),
      }),
    );
    expect(localStorage.getItem(PLAN_STORAGE_KEY)).toBeNull();
    expect(
      await screen.findByText(getCopy("wizard.age.heading")),
    ).toBeInTheDocument();
  });
  it("does not turn a malformed shared fragment into a restored fit result", async () => {
    localStorage.setItem(PLAN_STORAGE_KEY, JSON.stringify(savedPlan()));
    history.replaceState(null, "", "/visa/second-home/studio#p=invalid");
    render(<StudioApp />);
    expect(
      await screen.findByText(getCopy("wizard.age.heading")),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(getCopy("verdict.bands.strong_fit.heading")),
    ).not.toBeInTheDocument();
  });
});
