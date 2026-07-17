import { describe, expect, it } from "vitest";
import {
  computeNextNode,
  flowReducer,
  getTreeSteps,
  initialFlowState,
  isEditableTreeStep,
  type FlowState,
} from "./flow";

function step(
  state: FlowState,
  action: Parameters<typeof flowReducer>[1],
): FlowState {
  return flowReducer(state, action);
}

describe("flow.ts — full happy path", () => {
  it("walks framing → in_indonesia → category → tourism_duration → review_gate → confirmation → verdict", () => {
    let state = initialFlowState("en");
    expect(state.history).toEqual([{ kind: "framing" }]);

    state = step(state, { type: "ADVANCE" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "in_indonesia",
    });

    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "category",
    });

    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "tourism",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "tourism_duration",
    });

    state = step(state, {
      type: "ANSWER",
      questionId: "tourism_duration",
      value: "short",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "review_gate",
    });

    state = step(state, {
      type: "ANSWER",
      questionId: "review_gate",
      value: "none",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "confirmation",
    });

    state = step(state, { type: "ADVANCE" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "verdict",
    });

    expect(state.facts).toEqual({
      in_indonesia: "no",
      category: "tourism",
      tourism_duration: "short",
      review_gate: "none",
    });
  });

  it("onshore + urgent date skips straight to review_gate (design doc §4, no algorithmic routing)", () => {
    const today = new Date(Date.UTC(2026, 6, 17));
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "yes",
      today,
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "permit_expiry",
    });

    state = step(state, {
      type: "ANSWER",
      questionId: "permit_expiry",
      value: "2026-07-18",
      today,
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "review_gate",
    });
  });
});

describe("flow.ts — back navigation", () => {
  it("restores the previous node, keeping facts still reachable on the truncated history", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "work",
    });
    const beforeBack = state;

    state = step(state, { type: "BACK" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "category",
    });
    // "category" is still on the truncated history, so its fact survives —
    // unaffected by finding #1's pruning (that only drops facts for
    // questions no longer reachable from the current history).
    expect(state.facts).toEqual(beforeBack.facts);

    state = step(state, { type: "BACK" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "in_indonesia",
    });
  });

  it("is a no-op at the framing root", () => {
    const state = initialFlowState("en");
    const after = step(state, { type: "BACK" });
    expect(after).toEqual(state);
  });
});

describe("flow.ts — fact pruning across an abandoned branch (finding #1, adversarial review 2026-07-17)", () => {
  it("drops facts from a branch abandoned via Back once a different branch is chosen", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "work",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "work_payer",
      value: "yes",
    });
    expect(state.facts.work_payer).toBe("yes");
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "review_gate",
    });

    // Back past review_gate, back past work_payer, to category — then take
    // a DIFFERENT branch that never asks work_payer.
    state = step(state, { type: "BACK" });
    state = step(state, { type: "BACK" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "category",
    });

    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "tourism",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "tourism_duration",
    });

    // Before finding #1's fix, `work_payer: "yes"` from the abandoned
    // "work" branch would still be sitting in `state.facts` here, silently
    // feeding `mock-engine.ts`'s candidate matching and completeness check
    // even though the user is now on the tourism branch and was never
    // asked work_payer again.
    expect(state.facts.work_payer).toBeUndefined();
    expect(state.facts.category).toBe("tourism");
  });

  it("also prunes on EDIT (confirmation screen jump-back), not only BACK", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "remote",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "remote_clients",
      value: "foreign",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "remote_income",
      value: "above",
    });
    expect(state.facts.remote_clients).toBe("foreign");
    expect(state.facts.remote_income).toBe("above");

    state = step(state, { type: "EDIT", questionId: "category" });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "tourism",
    });

    expect(state.facts.remote_clients).toBeUndefined();
    expect(state.facts.remote_income).toBeUndefined();
  });
});

describe("flow.ts — edit from confirmation", () => {
  it("jumps back to the target question, truncating the stack", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "work",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "work_payer",
      value: "yes",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "review_gate",
      value: "none",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "confirmation",
    });

    state = step(state, { type: "EDIT", questionId: "category" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "category",
    });
    // facts from the edited-past answer are retained until re-answered
    expect(state.facts.category).toBe("work");

    // re-answering re-derives the forward path from the new facts
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "tourism",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "tourism_duration",
    });
  });
});

describe("flow.ts — SELECT_CATEGORY and REVIEW_ANSWERS (finding #15)", () => {
  it("SELECT_CATEGORY jumps back to category, re-answers it, and prunes the abandoned branch's facts", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "work",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "work_payer",
      value: "no",
    });
    expect(state.facts.work_payer).toBe("no");

    state = step(state, { type: "SELECT_CATEGORY", category: "remote" });
    expect(state.facts.category).toBe("remote");
    expect(state.facts.work_payer).toBeUndefined();
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "remote_clients",
    });
  });

  it("REVIEW_ANSWERS jumps back to confirmation without discarding facts ahead of it", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "tourism",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "tourism_duration",
      value: "short",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "review_gate",
      value: "none",
    });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "confirmation",
    });
    state = step(state, { type: "ADVANCE" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "verdict",
    });

    state = step(state, { type: "REVIEW_ANSWERS" });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "confirmation",
    });
    expect(state.facts.tourism_duration).toBe("short");
  });
});

describe("flow.ts — permit_expiry NotSure short-circuits to review (finding #7)", () => {
  it("routes straight to review_gate on an unsure compliance deadline, never guessing a lane", () => {
    const current = { kind: "question" as const, questionId: "permit_expiry" };
    const next = computeNextNode(current, {
      in_indonesia: "yes",
      permit_expiry: "unsure",
    });
    expect(next).toEqual({ kind: "question", questionId: "review_gate" });
  });
});

describe("flow.ts — language switch preserves facts", () => {
  it("SET_LANGUAGE never touches history or facts", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "work",
    });
    const beforeSwitch = { history: state.history, facts: state.facts };

    state = step(state, { type: "SET_LANGUAGE", language: "id" });
    expect(state.language).toBe("id");
    expect(state.history).toEqual(beforeSwitch.history);
    expect(state.facts).toEqual(beforeSwitch.facts);
  });
});

describe("flow.ts — computeNextNode determinism", () => {
  it("is a pure function of (current, facts, today)", () => {
    const current = { kind: "question" as const, questionId: "category" };
    const facts = { category: "remote" };
    const a = computeNextNode(current, facts);
    const b = computeNextNode(current, { ...facts });
    expect(a).toEqual(b);
    expect(a).toEqual({ kind: "question", questionId: "remote_clients" });
  });
});

describe("flow.ts — getTreeSteps", () => {
  it("marks the trunk done/current/pending and fans out category leaves once reached", () => {
    const current = { kind: "question" as const, questionId: "category" };
    const facts = { in_indonesia: "no" };
    const { trunk, categoryLeaves } = getTreeSteps(current, facts);

    const categoryStep = trunk.find((s) => s.id === "category");
    expect(categoryStep?.status).toBe("current");
    const framingStep = trunk.find((s) => s.id === "framing");
    expect(framingStep?.status).toBe("done");

    expect(categoryLeaves).not.toBeNull();
    expect(categoryLeaves?.length).toBe(10);
    expect(categoryLeaves?.every((l) => l.status === "pending")).toBe(true);
  });

  it("prunes every leaf except the chosen category once answered", () => {
    const current = { kind: "question" as const, questionId: "work_payer" };
    const facts = { in_indonesia: "no", category: "work" };
    const { categoryLeaves } = getTreeSteps(current, facts);

    const chosen = categoryLeaves?.find((l) => l.key === "work");
    expect(chosen?.status).toBe("done");
    const others = categoryLeaves?.filter((l) => l.key !== "work") ?? [];
    expect(others.every((l) => l.status === "pruned")).toBe(true);
  });

  it("returns no category leaves before the category step is reached", () => {
    const current = { kind: "question" as const, questionId: "in_indonesia" };
    const { categoryLeaves } = getTreeSteps(current, {});
    expect(categoryLeaves).toBeNull();
  });
});

describe("flow.ts — isEditableTreeStep (tree tap-to-edit, interaction #6)", () => {
  it("is editable: a completed real question step", () => {
    expect(
      isEditableTreeStep({
        id: "category",
        labelI18nKey: "tree.category",
        status: "done",
      }),
    ).toBe(true);
  });

  it("is NOT editable: 'framing'/'confirmation'/'verdict' even when marked done — EDIT only truncates to a question node", () => {
    for (const id of ["framing", "confirmation", "verdict"]) {
      expect(
        isEditableTreeStep({ id, labelI18nKey: `tree.${id}`, status: "done" }),
      ).toBe(false);
    }
  });

  it("is NOT editable: a real question step that isn't 'done' yet", () => {
    for (const status of ["current", "pending", "pruned"] as const) {
      expect(
        isEditableTreeStep({
          id: "category",
          labelI18nKey: "tree.category",
          status,
        }),
      ).toBe(false);
    }
  });

  it("end-to-end: dispatching EDIT on an editable step id truncates history exactly like the confirmation card's Edit button", () => {
    let state = initialFlowState("en");
    state = step(state, { type: "ADVANCE" });
    state = step(state, {
      type: "ANSWER",
      questionId: "in_indonesia",
      value: "no",
    });
    state = step(state, {
      type: "ANSWER",
      questionId: "category",
      value: "tourism",
    });
    const { trunk } = getTreeSteps(
      state.history[state.history.length - 1],
      state.facts,
    );
    const categoryStep = trunk.find((s) => s.id === "category")!;
    expect(isEditableTreeStep(categoryStep)).toBe(true);

    state = step(state, { type: "EDIT", questionId: categoryStep.id });
    expect(state.history[state.history.length - 1]).toEqual({
      kind: "question",
      questionId: "category",
    });
  });
});
