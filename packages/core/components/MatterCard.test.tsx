import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { MatterCard } from "./MatterCard";

describe("MatterCard", () => {
  it("shows title, progress ring, pending docs, deadline", () => {
    const { getByText, container } = render(
      <MatterCard
        title="KITAS Marco"
        type="visa"
        progressPercent={70}
        pendingDocs={["passport scan", "photo"]}
        nextDeadline={new Date(Date.now() + 10 * 86400_000)}
      />,
    );
    expect(getByText("KITAS Marco")).toBeTruthy();
    expect(container.querySelector("[data-role='fill']")).toBeTruthy();
    expect(getByText(/2 document/i)).toBeTruthy();
  });
});
