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

  it("reads semantic day-theme tokens (WS3), never hardcoded colors", () => {
    const { getByText, container } = render(
      <MatterCard
        title="KITAS Marco"
        type="visa"
        progressPercent={70}
        pendingDocs={["passport scan"]}
        nextStep="Upload passport scan"
      />,
    );
    const article = container.querySelector("article");
    expect(article?.style.background).toBe(
      "var(--surface-matter, var(--surface-raised))",
    );
    expect(article?.style.border).toContain("var(--border-default");
    // Pending-docs warning reads the AA state token (was the undefined
    // --color-status-warn, which silently inherited).
    expect(getByText(/1 document/i).style.color).toBe("var(--state-warning)");
    // English copy on the English portal (was "Prossimo:").
    expect(getByText(/Next: Upload passport scan/)).toBeTruthy();
    expect(container.innerHTML).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
