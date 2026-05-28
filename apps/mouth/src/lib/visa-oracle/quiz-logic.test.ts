import { describe, expect, it } from "vitest";
import {
  DURATION_OPTIONS,
  FAMILY_OPTIONS,
  PURPOSE_OPTIONS,
  getStepTitle,
  isQuizComplete,
} from "./quiz-logic";
import type { QuizAnswers } from "./types";

const completeAnswers: QuizAnswers = {
  nationality: "IT",
  purpose: "invest",
  duration: "long",
  family: "spouse_children",
};

describe("visa oracle quiz options", () => {
  it("keeps option values aligned with quiz answer choices", () => {
    expect(PURPOSE_OPTIONS.map((option) => option.value)).toEqual([
      "visit",
      "work",
      "invest",
      "retire",
      "digital_nomad",
      "family",
      "study",
    ]);
    expect(DURATION_OPTIONS.map((option) => option.value)).toEqual([
      "short",
      "medium",
      "long",
      "permanent",
    ]);
    expect(FAMILY_OPTIONS.map((option) => option.value)).toEqual([
      "solo",
      "spouse",
      "children",
      "spouse_children",
    ]);
  });
});

describe("getStepTitle", () => {
  it("returns the display title for each quiz step", () => {
    expect(getStepTitle(1)).toBe("What is your nationality?");
    expect(getStepTitle(2)).toBe(
      "What is your main purpose for coming to Bali?",
    );
    expect(getStepTitle(3)).toBe("How long do you plan to stay?");
    expect(getStepTitle(4)).toBe("Who are you travelling with?");
  });
});

describe("isQuizComplete", () => {
  it("accepts answers only when all required fields are present", () => {
    expect(isQuizComplete(completeAnswers)).toBe(true);
  });

  it("rejects empty nationality even when select answers are present", () => {
    expect(
      isQuizComplete({
        ...completeAnswers,
        nationality: "",
      }),
    ).toBe(false);
  });

  it("rejects partial answers with any missing select answer", () => {
    const { duration: _duration, ...withoutDuration } = completeAnswers;

    expect(isQuizComplete(withoutDuration)).toBe(false);
    expect(isQuizComplete({ nationality: "IT" })).toBe(false);
  });
});
