import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PENDING_COOKIE } from "../contract";

/**
 * The only page of the magic-link flow a human sees. Two invariants:
 * it redeems nothing at render time, and it holds no credential anywhere in
 * the document — the token lives in an HttpOnly cookie the page cannot read
 * into its markup.
 */

const notFoundMock = vi.hoisted(() =>
  vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
);
const cookieStore = vi.hoisted(() => ({
  value: undefined as string | undefined,
}));

vi.mock("next/navigation", () => ({ notFound: notFoundMock }));
vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) =>
      name === "garuda_magic_pending" && cookieStore.value !== undefined
        ? { name, value: cookieStore.value }
        : undefined,
  }),
}));

const TOKEN = "t".repeat(40);
const RESULT_ID = "R".repeat(24);

async function renderPage(sp: Record<string, string>) {
  const { default: Page } = await import("./page");
  return Page({ searchParams: Promise.resolve(sp) });
}

describe("/visa/voa/auth/continue", () => {
  const original = process.env.GARUDA_PUBLIC_ENABLED;

  beforeEach(() => {
    notFoundMock.mockClear();
    process.env.GARUDA_PUBLIC_ENABLED = "true";
    cookieStore.value = TOKEN;
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    if (original === undefined) delete process.env.GARUDA_PUBLIC_ENABLED;
    else process.env.GARUDA_PUBLIC_ENABLED = original;
    vi.unstubAllGlobals();
  });

  it("renders the form and redeems nothing at render time", async () => {
    const { container } = render(await renderPage({ result_id: RESULT_ID }));

    expect(fetch).not.toHaveBeenCalled();
    const form = container.querySelector("form");
    expect(form?.getAttribute("method")).toBe("post");
    expect(form?.getAttribute("action")).toBe("/visa/voa/auth/exchange");
    expect(
      screen.getByRole("button", { name: /continue/i }),
    ).toBeInTheDocument();
  });

  it("puts NO token anywhere in the document", async () => {
    const { container } = render(await renderPage({ result_id: RESULT_ID }));

    // The whole reason ../route.ts redirects instead of rendering: this
    // markup is what Google Analytics' page_view sits alongside.
    expect(container.innerHTML).not.toContain(TOKEN);
    expect(
      container.querySelector(`input[name="${PENDING_COOKIE}"]`),
    ).toBeNull();
    expect(container.querySelector('input[name="magic_token"]')).toBeNull();
    // Only the result id is submitted.
    const hidden = container.querySelector<HTMLInputElement>(
      'input[name="result_id"]',
    );
    expect(hidden?.getAttribute("value")).toBe(RESULT_ID);
  });

  it("404s when the dark-launch flag is off", async () => {
    delete process.env.GARUDA_PUBLIC_ENABLED;
    await expect(renderPage({ result_id: RESULT_ID })).rejects.toThrow(
      "NEXT_NOT_FOUND",
    );
    expect(notFoundMock).toHaveBeenCalled();
  });

  it("offers no button when no token is in flight", async () => {
    // Nothing to submit — a scanner that followed the redirect, or a stale
    // bookmark. Showing the button would be a lie.
    cookieStore.value = undefined;
    const { container } = render(await renderPage({ result_id: RESULT_ID }));

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/no longer valid/i)).toBeInTheDocument();
  });

  it.each([
    ["a malformed result_id", { result_id: "../.." }],
    ["no result_id", {}],
    ["an error marker from a refused exchange", { error: "invalid" }],
    [
      "an error marker even alongside a valid result_id",
      { error: "invalid", result_id: RESULT_ID },
    ],
  ])("offers no form for %s", async (_label, sp) => {
    const { container } = render(
      await renderPage(sp as Record<string, string>),
    );

    expect(container.querySelector("form")).toBeNull();
    expect(screen.getByText(/no longer valid/i)).toBeInTheDocument();
  });
});
