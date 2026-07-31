/**
 * The three portal error boundaries decide between "Access Denied" and their
 * own generic copy. They used to decide it like this:
 *
 *   const is403 =
 *     (error as { status?: number })?.status === 403 ||
 *     error?.message?.includes("403");
 *
 * Both arms were wrong. Nothing ever set `.status` on a thrown error, so only
 * the substring arm could fire — and that arm is true of "Practice 4034 not
 * found", so a missing record showed a client "Access Denied. Your account
 * needs verification." They now read `ApiError.statusCode`.
 *
 * Every boundary gets both directions: a real 403 must produce the 403 copy
 * (guilt), and a non-403 carrying "403" in its message must not (innocence).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/logger", () => ({
  logger: { error: vi.fn(), info: vi.fn(), warn: vi.fn() },
}));

import { ApiError } from "@/lib/api/error-handler";
import FamilyError from "../family/error";
import MessagesError from "../messages/error";
import VisaError from "../visa/error";

const BOUNDARIES = [
  {
    name: "family",
    Component: FamilyError,
    generic: "Family data unavailable",
  },
  {
    name: "messages",
    Component: MessagesError,
    generic: "Couldn't Load Messages",
  },
  {
    name: "visa",
    Component: VisaError,
    generic: "Immigration data unavailable",
  },
] as const;

// A 404 whose message contains the literal "403" — the trap the old substring
// check fell into. Kept as a named constant so the intent survives edits.
const FOUR_OH_FOUR_MENTIONING_403 = () =>
  new ApiError("Practice 4034 not found", 404, {});

describe("portal error boundaries: 403 detection reads the status, not the text", () => {
  for (const { name, Component, generic } of BOUNDARIES) {
    it(`${name}: guilt — a real 403 renders Access Denied`, () => {
      render(
        <Component
          error={new ApiError("Forbidden", 403, {})}
          reset={vi.fn()}
        />,
      );
      expect(screen.getByText("Access Denied")).toBeTruthy();
      expect(screen.getByText("Your account needs verification.")).toBeTruthy();
      expect(screen.queryByText(generic)).toBeNull();
    });

    it(`${name}: innocence — a 404 whose message contains "403" keeps the generic copy`, () => {
      render(
        <Component error={FOUR_OH_FOUR_MENTIONING_403()} reset={vi.fn()} />,
      );
      expect(screen.getByText(generic)).toBeTruthy();
      expect(screen.queryByText("Access Denied")).toBeNull();
    });

    it(`${name}: innocence — a plain Error is not a 403`, () => {
      render(<Component error={new Error("403")} reset={vi.fn()} />);
      expect(screen.getByText(generic)).toBeTruthy();
      expect(screen.queryByText("Access Denied")).toBeNull();
    });
  }

  // Finding #2 of the review on #3474: this boundary IS /portal/messages, so
  // offering /portal/messages as the remedy sends the reader back into the page
  // that just failed. The other two keep their link because it goes elsewhere.
  it("messages: offers no link back to the page that just failed", () => {
    const { container } = render(
      <MessagesError
        error={new ApiError("Forbidden", 403, {})}
        reset={vi.fn()}
      />,
    );
    const selfLinks = Array.from(container.querySelectorAll("a")).filter(
      (a) => a.getAttribute("href") === "/portal/messages",
    );
    expect(selfLinks).toHaveLength(0);
  });

  it("family and visa DO keep an escape hatch to a different route", () => {
    for (const Component of [FamilyError, VisaError]) {
      const { container } = render(
        <Component
          error={new ApiError("Forbidden", 403, {})}
          reset={vi.fn()}
        />,
      );
      const links = Array.from(container.querySelectorAll("a")).map((a) =>
        a.getAttribute("href"),
      );
      expect(links).toContain("/portal/messages");
    }
  });
});
