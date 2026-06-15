import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AvatarWithFallback } from "./avatar-with-fallback";

const FALLBACK = <div data-testid="fallback">JD</div>;

describe("AvatarWithFallback", () => {
  it("renders the <img> when src is provided", () => {
    render(
      <AvatarWithFallback
        src="/static/team/adit.jpg"
        alt="Adit"
        fallback={FALLBACK}
      />,
    );
    const img = screen.getByAltText("Adit") as HTMLImageElement;
    expect(img.tagName).toBe("IMG");
    expect(img.getAttribute("src")).toBe("/static/team/adit.jpg");
    expect(screen.queryByTestId("fallback")).not.toBeInTheDocument();
  });

  it("renders the fallback when src is missing", () => {
    render(<AvatarWithFallback src={null} alt="Adit" fallback={FALLBACK} />);
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
    expect(screen.queryByAltText("Adit")).not.toBeInTheDocument();
  });

  it("renders the fallback when src is an empty string", () => {
    render(<AvatarWithFallback src="" alt="Adit" fallback={FALLBACK} />);
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
  });

  it("swaps to the fallback when the image fails to load (404)", () => {
    render(
      <AvatarWithFallback
        src="/static/team/adit.png"
        alt="Adit"
        fallback={FALLBACK}
      />,
    );
    // Initially the img is shown...
    const img = screen.getByAltText("Adit");
    expect(img).toBeInTheDocument();
    // ...then the load fails (the .png was removed in the 2026-06-15 cutover).
    fireEvent.error(img);
    expect(screen.queryByAltText("Adit")).not.toBeInTheDocument();
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
  });

  it("applies the className to the <img>", () => {
    render(
      <AvatarWithFallback
        src="/static/team/adit.jpg"
        alt="Adit"
        className="w-8 h-8 rounded-full"
        fallback={FALLBACK}
      />,
    );
    expect(screen.getByAltText("Adit").className).toContain("rounded-full");
  });

  it("recovers (re-attempts the image) when src changes after an error", () => {
    const { rerender } = render(
      <AvatarWithFallback src="/broken.png" alt="A" fallback={FALLBACK} />,
    );
    fireEvent.error(screen.getByAltText("A"));
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
    // Reassigned to a different member with a valid photo → try again.
    rerender(
      <AvatarWithFallback
        src="/static/team/ari.jpg"
        alt="A"
        fallback={FALLBACK}
      />,
    );
    const img = screen.getByAltText("A") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/static/team/ari.jpg");
    expect(screen.queryByTestId("fallback")).not.toBeInTheDocument();
  });
});
