import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Shortlist, ShortlistButton, parseShortlist } from "./Shortlist";
beforeEach(() => localStorage.clear());
describe("KBLI working shortlist", () => {
  it("accepts only unique five-digit codes and caps the saved selection", () => {
    expect(parseShortlist("not json")).toEqual([]);
    expect(
      parseShortlist(
        JSON.stringify(["56101", "56101", "../private", 33, "12345"]),
      ),
    ).toEqual(["56101", "12345"]);
    expect(
      parseShortlist(
        JSON.stringify(Array.from({ length: 10 }, (_, i) => String(10000 + i))),
      ),
    ).toHaveLength(6);
  });
  it("adds and removes a code across the card and shortlist with accessible state", async () => {
    const user = userEvent.setup();
    render(
      <>
        <ShortlistButton code="56101" />
        <Shortlist />
      </>,
    );
    const button = screen.getByRole("button", { name: "＋ Shortlist" });
    await user.click(button);
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("heading", { name: "1 of 6 codes shortlisted" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Remove 56101 from shortlist" }),
    );
    expect(button).toHaveAttribute("aria-pressed", "false");
    expect(localStorage.getItem("bz-kbli-shortlist-v1")).toBe("[]");
  });
});
