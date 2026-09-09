import { describe, expect, it } from "vitest";
import { flowReducer, initialFlowState, type FlowState } from "./flow";
import { projectInterview } from "./presentation-graph";
const today = new Date("2026-09-06T00:00:00Z");
function answer(state: FlowState, questionId: string, value: string): FlowState {
  return flowReducer(state, { type: "ANSWER", questionId, value, today });
}
describe("decision atlas projection", () => {
  it("projects the actual root and different outgoing reducer destinations", () => {
    const graph = projectInterview(initialFlowState(), today);
    expect(graph.nodes[0]).toMatchObject({ id: "q:in_indonesia", state: "current" });
    const yes = graph.nodes.find(n => n.id === "a:in_indonesia:yes")!;
    const no = graph.nodes.find(n => n.id === "a:in_indonesia:no")!;
    expect(yes.next).toEqual({ kind: "question", questionId: "permit_expiry" });
    expect(no.next).toEqual({ kind: "question", questionId: "holds_stay_permit" });
    expect(graph.edges).toContainEqual({ from: "q:in_indonesia", to: no.id, answerKey: "no" });
  });
  it("edits an ancestor through canonical pruning, retaining neither stale facts nor graph nodes", () => {
    let state = flowReducer(initialFlowState(), { type: "ADVANCE" });
    state = answer(state, "in_indonesia", "no");
    state = answer(state, "holds_stay_permit", "no");
    state = answer(state, "overstay_days", "0");
    state = flowReducer(state, { type: "EDIT", questionId: "in_indonesia" });
    state = answer(state, "in_indonesia", "yes");
    expect(state.facts).toEqual({ in_indonesia: "yes" });
    const graph = projectInterview(state, today);
    expect(graph.nodes.some(n => n.questionId === "holds_stay_permit")).toBe(false);
    expect(graph.nodes.find(n => n.id === "a:in_indonesia:no")?.state).toBe("not-selected");
    expect(graph.nodes.find(n => n.id === "q:permit_expiry")?.state).toBe("current");
  });
  it("preserves the route and projects follow-up answers directly back to the verdict", () => {
    const state: FlowState = { ...initialFlowState(), history: [{kind:"framing"},{kind:"question",questionId:"in_indonesia"},{kind:"verdict"}], facts: {in_indonesia:"no",category:"retirement",retirement_basis:"property"} };
    const follow = flowReducer(state, { type: "ASK_FOLLOW_UP", questionId: "family_sponsor_confirmed" });
    const graph = projectInterview(follow, today);
    expect(follow.facts).toEqual(state.facts);
    expect(graph.nodes.find(n => n.id === "q:family_sponsor_confirmed")?.state).toBe("clarification-required");
    expect(graph.nodes.filter(n => n.questionId === "family_sponsor_confirmed" && n.answerKey).every(n => n.next?.kind === "verdict")).toBe(true);
  });
  it("does not encode a typed answer in node identifiers", () => {
    let state = flowReducer(initialFlowState(), { type: "ADVANCE" });
    for (const [q,v] of [["in_indonesia","no"],["holds_stay_permit","no"],["overstay_days","0"]]) state=answer(state,q,v);
    expect(projectInterview(state,today).nodes.find(n=>n.questionId==="overstay_days" && n.answerKey)?.id).toBe("a:overstay_days:value");
  });
});
