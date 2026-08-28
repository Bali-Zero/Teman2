import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import GarudaVoaAuthPage from "./page";

/**
 * The landing page must CONSUME NOTHING. The token is single-use and mail
 * scanners issue unsolicited GETs on emailed links, so any redemption at
 * render time is a token burnt before the customer ever clicks.
 */

const notFoundMock = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);

vi.mock("next/navigation", () => ({ notFound: notFoundMock }));

const TOKEN = "t".repeat(40);
const RESULT_ID = "R".repeat(24);

function renderPage(sp: Record<string, string>) {
  return GarudaVoaAuthPage({ searchParams: Promise.resolve(sp) });
}

describe("/visa/voa/auth — magic-link landing", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;

  beforeEach(() => {
    notFoundMock.mockClear();
    process.env.GARUDA_PUBLIC_ENABLED = "true";
  });

  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
    vi.unstubAllGlobals();
  });

  it("renders a form and redeems nothing at render time", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(
      await renderPage({ magic_token: TOKEN, result_id: RESULT_ID }),
    );

    expect(fetchMock).not.toHaveBeenCalled();
    const form = container.querySelector("form");
    expect(form?.getAttribute("method")).toBe("post");
    expect(form?.getAttribute("action")).toBe("/visa/voa/auth/exchange");
    expect(
      screen.getByRole("button", { name: /continue/i }),
    ).toBeInTheDocument();
  });

  it("carries the token in a hidden field, never in a link or a visible URL", async () => {
    const { container } = render(
      await renderPage({ magic_token: TOKEN, result_id: RESULT_ID }),
    );

    const hidden = container.querySelector<HTMLInputElement>(
      'input[name="magic_token"]',
    );
    expect(hidden?.getAttribute("type")).toBe("hidden");
    expect(hidden?.getAttribute("value")).toBe(TOKEN);
    // Nothing anchor-shaped may carry it: an href would put a credential in
    // the referrer of whatever it points at.
    for (const a of container.querySelectorAll("a")) {
      expect(a.getAttribute("href") ?? "").not.toContain(TOKEN);
    }
  });

  it("404s when the dark-launch flag is off", async () => {
    delete process.env.GARUDA_PUBLIC_ENABLED;
    await expect(
      renderPage({ magic_token: TOKEN, result_id: RESULT_ID }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    expect(notFoundMock).toHaveBeenCalled();
  });

  it.each([
    [
      "a token one char too short",
      { magic_token: "t".repeat(31), result_id: RESULT_ID },
    ],
    ["a malformed result_id", { magic_token: TOKEN, result_id: "../.." }],
    ["no parameters at all", {}],
    ["an error marker from a refused exchange", { error: "invalid" }],
    [
      "an error marker even alongside a well-formed token",
      { error: "invalid", magic_token: TOKEN, result_id: RESULT_ID },
    ],
  ])("offers no form for %s", async (_label, sp) => {
    const { container } = render(
      await renderPage(sp as Record<string, string>),
    );

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/no longer valid/i)).toBeInTheDocument();
  });
});
