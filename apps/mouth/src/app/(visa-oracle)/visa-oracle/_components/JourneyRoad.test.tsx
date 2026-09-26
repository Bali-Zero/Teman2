import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import type { OracleNode } from "../_lib/flow";
import { JourneyRoad } from "./JourneyRoad";

const HISTORY: OracleNode[] = [
  { kind: "framing" },
  { kind: "question", questionId: "in_indonesia" },
  { kind: "question", questionId: "holds_stay_permit" },
];

function renderRoad(onEdit = vi.fn()) {
  render(
    <JourneyRoad
      language="en"
      current={{ kind: "question", questionId: "holds_stay_permit" }}
      history={HISTORY}
      facts={{ in_indonesia: "no" }}
      visitedVerdict={false}
      headStatus="head"
      reducedMotion
      onEdit={onEdit}
    >
      <h1>Head question</h1>
    </JourneyRoad>,
  );
  return onEdit;
}

describe("JourneyRoad — the list is the truth, the drawing is decoration", () => {
  it("renders answered questions as one ordered list, the open one as the head", () => {
    renderRoad();
    const road = screen.getByRole("list", { name: "Your answers so far" });
    expect(road.tagName).toBe("OL");
    const records = within(road).getAllByRole("listitem");
    expect(records).toHaveLength(1);
    expect(records[0]).toHaveAttribute("data-road-record", "in_indonesia");
    // the head is a fieldset whose legend names the stage, never a record
    const head = screen.getByRole("group");
    expect(head.tagName).toBe("FIELDSET");
    expect(head.querySelector("legend")?.textContent).toMatch(
      /^Stage \d of 5 · /,
    );
    expect(within(road).queryByText("Head question")).toBeNull();
  });

  it("Change re-opens exactly that question", async () => {
    const onEdit = renderRoad();
    await userEvent.click(
      screen.getByRole("button", { name: /^Change your answer: / }),
    );
    expect(onEdit).toHaveBeenCalledWith("in_indonesia");
  });

  it("keeps the drawing out of the accessibility tree", () => {
    renderRoad();
    const canvas = document.querySelector(".oracle-road__canvas");
    expect(canvas).not.toBeNull();
    expect(canvas).toHaveAttribute("aria-hidden", "true");
  });

  it("never shows an engine fact id", () => {
    renderRoad();
    expect(document.body.textContent).not.toMatch(/\b[a-z]+\.[a-z_]+\b/);
  });
});
