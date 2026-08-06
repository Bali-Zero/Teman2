import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VISA_ORACLE_RESUME_KEY } from "../_lib/resume-store";
import { OracleShell } from "./OracleShell";

describe("OracleShell non-engine authority guards", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("keeps resume off by default and writes no interview snapshot on Start", async () => {
    vi.stubEnv("NEXT_PUBLIC_VISA_ORACLE_MODE", "OFF");
    const fetchMock = vi.fn();
    global.fetch = fetchMock;
    render(<OracleShell />);

    expect(
      await screen.findByText(
        /save the full interview.*sensitive immigration/i,
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("checkbox", {
        name: /save my interview on this device for 2 hours/i,
      }),
    ).not.toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: /^start$/i }));
    await screen.findByRole("heading", {
      name: /are you in indonesia right now/i,
    });
    await waitFor(() =>
      expect(window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY)).toBeNull(),
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(document.querySelector(".oracle-constellation")).toBeNull();
  });

  it("persists only after explicit opt-in and supports manual clearing", async () => {
    vi.stubEnv("NEXT_PUBLIC_VISA_ORACLE_MODE", "OFF");
    render(<OracleShell />);

    fireEvent.click(
      await screen.findByRole("checkbox", {
        name: /save my interview on this device for 2 hours/i,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: /^start$/i }));
    await waitFor(() =>
      expect(
        window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY),
      ).not.toBeNull(),
    );

    fireEvent.click(
      screen.getByRole("button", { name: /clear saved interview/i }),
    );
    expect(window.sessionStorage.getItem(VISA_ORACLE_RESUME_KEY)).toBeNull();
    expect(
      screen.queryByRole("button", { name: /clear saved interview/i }),
    ).toBeNull();
  });

  it("production coerces PREVIEW to ENGINE instead of restoring mock authority", async () => {
    vi.stubEnv("NEXT_PUBLIC_VISA_ORACLE_MODE", "PREVIEW");
    vi.stubEnv("NODE_ENV", "production");
    render(<OracleShell />);

    expect(await screen.findByText("Visa decision support")).toBeVisible();
    expect(
      screen.queryByText(/developer preview mode cannot issue/i),
    ).toBeNull();
  });
});
