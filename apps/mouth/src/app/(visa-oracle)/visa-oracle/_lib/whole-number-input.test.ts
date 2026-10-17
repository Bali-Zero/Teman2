import { describe, expect, it } from "vitest";
import { parseWholeNumberInput } from "./whole-number-input";
import { QUESTIONS } from "./tree";

const MAX = Number.MAX_SAFE_INTEGER;

describe("parseWholeNumberInput - raw whole-number syntax before conversion", () => {
  it.each([
    "9999999999.9999999",
    "1e10",
    "1E10",
    "10000000000.0",
    "1.5",
    "-1",
    "-10000000000",
    "+5",
    "",
    " ",
    "10 000",
    "10,000",
    "0x10",
    "9007199254740993",
  ])("rejects %j", (raw) => {
    expect(parseWholeNumberInput(raw, 0, MAX)).toBeNull();
  });

  it.each([
    ["10000000000", 10_000_000_000],
    ["0", 0],
    ["007", 7],
    ["9999999999", 9_999_999_999],
  ])("accepts %j", (raw, expected) => {
    expect(parseWholeNumberInput(raw, 0, MAX)).toBe(expected);
  });

  it("respects the question's own bounds", () => {
    expect(parseWholeNumberInput("0", 1, 10)).toBeNull();
    expect(parseWholeNumberInput("11", 1, 10)).toBeNull();
    expect(parseWholeNumberInput("5", 1, 10)).toBe(5);
  });

  it("every number question is a whole-number question (step 1), so the digits-only rule fits all of them", () => {
    const numbers = Object.values(QUESTIONS).filter((q) => q.kind === "number");
    expect(numbers.length).toBeGreaterThan(5);
    for (const q of numbers) {
      expect(q.numberInput?.step, q.id).toBe(1);
      expect(q.numberInput?.min, q.id).toBeGreaterThanOrEqual(0);
    }
  });
});
