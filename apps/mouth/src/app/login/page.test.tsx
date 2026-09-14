/**
 * The /login contract, on concept-K "SIAP".
 *
 * Three things are pinned here, and each one is pinned with a planted
 * violation AND an innocent case, because a guard that has only ever seen
 * green cannot be shown to be looking (cicatrix #3).
 *
 *   1. sameOriginPath  — the open redirect stays closed.
 *   2. stageForError   — a 500 is never reported as a wrong PIN.
 *   3. no red, no copper FILL — the alphabet's law, read off the rendered DOM.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";

const { mockLogin, mockLoggerError, mockLoggerWarn } = vi.hoisted(() => ({
  mockLogin: vi.fn(),
  mockLoggerError: vi.fn(),
  mockLoggerWarn: vi.fn(),
}));

vi.mock("@/lib/api", () => ({ api: { login: mockLogin } }));

vi.mock("@/lib/logger", () => ({
  logger: {
    error: mockLoggerError,
    warn: mockLoggerWarn,
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import { ApiError } from "@/lib/api/error-handler";
import LoginPage, { sameOriginPath, stageForError } from "./page";
import LoginError from "./error";
import LoginLoading from "./loading";

/**
 * Every red this surface must never show, as VALUES. The kita theme resolves
 * --state-danger to copper, so a literal red can only arrive by being typed
 * into a class or a style — which is exactly what this list catches.
 */
const REDS = [
  "#e45c5c",
  "#b91c1c",
  "#dc2626",
  "#ef4444",
  "text-destructive",
  "bg-destructive",
  "var(--state-danger)",
  "var(--bz-red",
];

/** Pure detector: which forbidden reds appear in this markup. */
export function findReds(markup: string): string[] {
  return REDS.filter((red) => markup.includes(red));
}

/**
 * Pure detector: a copper FILL behind a label. Copper is a person, not a
 * status, and it is never the ground a word sits on. A copper BORDER, a
 * copper RULE (the 3px masthead mark) and copper TEXT are all legal, so the
 * rule's own shape is subtracted and anything else that fills is returned.
 */
const COPPER_RULE = /h-\[3px\] w-14 rounded-sm bg-\[var\(--bz-copper\)\]/g;

export function findCopperFill(markup: string): string[] {
  const withoutRule = markup.replace(COPPER_RULE, "");
  return withoutRule.match(/bg-\[var\(--bz-copper[a-z-]*\)\]/g) ?? [];
}

const redirectReplace = vi.fn();
const realLocation = globalThis.location;

/**
 * jsdom's `location.replace` is read-only and its Location is unforgeable, so
 * the method cannot be spied on. The `location` PROPERTY of the global is
 * configurable, though, so the whole object is swapped for the two fields this
 * page actually reads. Restored after the file so nothing else inherits it.
 */
function atUrl(search: string) {
  Object.defineProperty(globalThis, "location", {
    configurable: true,
    value: {
      href: `http://localhost/login${search}`,
      pathname: "/login",
      origin: "http://localhost",
      search,
      replace: redirectReplace,
    },
  });
}

afterAll(() => {
  Object.defineProperty(globalThis, "location", {
    configurable: true,
    value: realLocation,
  });
});

beforeEach(() => {
  vi.clearAllMocks();
  redirectReplace.mockClear();
  atUrl("");
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("{}"));
});

describe("sameOriginPath — the redirect allowlist", () => {
  it("accepts a same-origin path, with or without a query (innocence)", () => {
    expect(sameOriginPath("/dashboard")).toBe("/dashboard");
    expect(sameOriginPath("/clients?filter=mine")).toBe("/clients?filter=mine");
    expect(sameOriginPath("/")).toBe("/");
  });

  it("rejects an absolute URL, any scheme (guilt)", () => {
    expect(sameOriginPath("https://evil.test/steal")).toBeNull();
    expect(sameOriginPath("http://evil.test")).toBeNull();
    expect(sameOriginPath("javascript:alert(1)")).toBeNull();
  });

  it("rejects the protocol-relative and backslash forms (guilt)", () => {
    // A browser resolves //evil.test as an absolute URL, and normalises
    // /\evil.test into it. Both leave the origin; neither starts with a scheme.
    expect(sameOriginPath("//evil.test")).toBeNull();
    expect(sameOriginPath("/\\evil.test")).toBeNull();
  });

  it("rejects nothing at all", () => {
    expect(sameOriginPath(null)).toBeNull();
    expect(sameOriginPath("")).toBeNull();
    expect(sameOriginPath("dashboard")).toBeNull();
  });
});

describe("stageForError — a broken service is not a wrong PIN", () => {
  it("401 and 403 are the credentials (guilt: these two only)", () => {
    expect(stageForError(new ApiError("no", 401))).toBe("denied");
    expect(stageForError(new ApiError("no", 403))).toBe("denied");
  });

  it("every other status is the service (innocence)", () => {
    expect(stageForError(new ApiError("boom", 500))).toBe("unreachable");
    expect(stageForError(new ApiError("slow", 504))).toBe("unreachable");
    expect(stageForError(new ApiError("busy", 429))).toBe("unreachable");
    expect(stageForError(new ApiError("teapot", 418))).toBe("unreachable");
  });

  it("a network throw is the service, not the credentials", () => {
    expect(stageForError(new TypeError("Failed to fetch"))).toBe("unreachable");
    expect(stageForError("a string")).toBe("unreachable");
  });
});

describe("the detectors themselves", () => {
  it("findReds names a planted red and clears innocent markup", () => {
    expect(findReds('<p class="text-destructive">x</p>')).toEqual([
      "text-destructive",
    ]);
    expect(findReds('<p style="color:#e45c5c">x</p>')).toEqual(["#e45c5c"]);
    expect(findReds('<p class="text-[var(--bz-copper-text)]">x</p>')).toEqual(
      [],
    );
  });

  it("findCopperFill names a planted fill and clears the legal rule", () => {
    const rule =
      '<div class="mb-5 h-[3px] w-14 rounded-sm bg-[var(--bz-copper)]"></div>';
    expect(findCopperFill(rule)).toEqual([]);
    expect(
      findCopperFill(
        rule + '<span class="bg-[var(--bz-copper)]">Blocked</span>',
      ),
    ).toEqual(["bg-[var(--bz-copper)]"]);
  });
});

describe("LoginPage — the five plates", () => {
  it("renders the idle plate: forest panel, copper rule, both fields", () => {
    const { container } = render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "Welcome back." })).toBeTruthy();
    expect(screen.getByLabelText("Email")).toBeTruthy();
    // The PIN is digits on the backend, so a phone must offer the number pad.
    expect(screen.getByLabelText("PIN").getAttribute("inputmode")).toBe(
      "numeric",
    );
    expect(
      container.querySelector('[style*="var(--bz-panel)"]'),
    ).not.toBeNull();
    expect(
      container.querySelector(".h-\\[3px\\].w-14.rounded-sm"),
    ).not.toBeNull();
  });

  it("none of the theatre survives: no overlay, no sound, no motion", () => {
    const { container } = render(<LoginPage />);
    const markup = container.innerHTML;

    expect(markup).not.toContain("ACCESS GRANTED");
    expect(markup).not.toContain("ACCESS DENIED");
    expect(container.querySelector(".fixed.inset-0")).toBeNull();
  });

  it("carries no red and no copper fill", () => {
    const { container } = render(<LoginPage />);

    expect(findReds(container.innerHTML)).toEqual([]);
    expect(findCopperFill(container.innerHTML)).toEqual([]);
  });

  it("a 401 says the credentials; a 500 says the service", async () => {
    mockLogin.mockRejectedValueOnce(new ApiError("bad", 401));
    const first = render(<LoginPage />);

    fireEvent.submit(first.container.querySelector("form")!);
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain("do not match");
    });
    // The denial is copper and a sentence, never a red.
    expect(findReds(first.container.innerHTML)).toEqual([]);
    first.unmount();

    mockLogin.mockRejectedValueOnce(new ApiError("down", 500));
    const second = render(<LoginPage />);
    fireEvent.submit(second.container.querySelector("form")!);
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toContain(
        "could not reach the service",
      );
    });
  });

  it("honours a same-origin ?redirect= (innocence)", async () => {
    atUrl("?redirect=/clients");
    mockLogin.mockResolvedValueOnce({ user: { name: "Ada", role: "staff" } });
    const { container } = render(<LoginPage />);

    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() =>
      expect(redirectReplace).toHaveBeenCalledWith("/clients"),
    );
    expect(mockLoggerWarn).not.toHaveBeenCalled();
  });

  it("refuses an off-origin ?redirect= and says so in the log (guilt)", async () => {
    // The same parameter, pointing off-origin: the role destination wins and
    // the refusal is recorded. This is the open redirect, closed.
    atUrl("?redirect=https://evil.test");
    mockLogin.mockResolvedValueOnce({ user: { name: "Ada", role: "staff" } });
    const { container } = render(<LoginPage />);

    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() =>
      expect(redirectReplace).toHaveBeenCalledWith("/dashboard"),
    );
    expect(mockLoggerWarn).toHaveBeenCalledTimes(1);
  });

  it("a client role still falls back to /portal", async () => {
    mockLogin.mockResolvedValueOnce({ user: { name: "Ada", role: "client" } });
    const { container } = render(<LoginPage />);

    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() =>
      expect(redirectReplace).toHaveBeenCalledWith("/portal"),
    );
  });

  it("the success plate greets by name and claims no destination", async () => {
    mockLogin.mockResolvedValueOnce({ user: { name: "Ada", role: "staff" } });
    const { container } = render(<LoginPage />);

    fireEvent.submit(container.querySelector("form")!);
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Welcome back, Ada." }),
      ).toBeTruthy(),
    );
    expect(screen.getByRole("status").textContent).toBe("One moment.");
    // It does not name a page it has not reached.
    expect(container.innerHTML).not.toContain("Redirecting");
  });
});

describe("the boundary and the skeleton wear the same alphabet", () => {
  it("the error boundary is copper and carries the words, never a red", () => {
    const { container } = render(
      <LoginError error={new Error("x")} reset={vi.fn()} />,
    );

    expect(findReds(container.innerHTML)).toEqual([]);
    expect(findCopperFill(container.innerHTML)).toEqual([]);
    expect(
      screen.getByRole("heading", { name: "The sign-in page did not load." }),
    ).toBeTruthy();
  });

  it("the boundary's button still calls reset", () => {
    const reset = vi.fn();
    render(<LoginError error={new Error("x")} reset={reset} />);

    fireEvent.click(screen.getByRole("button", { name: /Try again/ }));
    expect(reset).toHaveBeenCalledTimes(1);
  });

  it("the skeleton predicts the login's own silhouette", () => {
    const { container } = render(<LoginLoading />);

    // The forest band, the copper rule and two 52px fields — the same numbers
    // the page uses, so nothing jumps when the real page arrives.
    expect(
      container.querySelector('[style*="var(--bz-panel)"]'),
    ).not.toBeNull();
    expect(container.querySelectorAll(".h-\\[52px\\]").length).toBe(2);
    expect(findReds(container.innerHTML)).toEqual([]);
  });
});
