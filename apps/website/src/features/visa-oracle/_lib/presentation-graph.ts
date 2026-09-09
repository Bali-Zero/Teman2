import { flowReducer, type FlowState, type OracleNode } from "./flow";
import { QUESTIONS } from "./tree";

export type GraphState = "answered" | "current" | "reachable-next-choice" | "not-selected" | "clarification-required" | "outcome";
export interface GraphNode { id: string; state: GraphState; questionId?: string; answerKey?: string; next?: OracleNode; blocked?: boolean }
export interface GraphEdge { from: string; to: string; answerKey?: string }

/** Projection only. The canonical reducer determines whether an answer is
 * accepted, including conflicts and follow-up return-to-verdict behavior. */
export function projectInterview(state: FlowState, today = new Date()): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const current = state.history.at(-1)!;
  const history = current.kind === "framing" ? [{ kind: "question", questionId: "in_indonesia" } as OracleNode] : state.history;
  const nodes: GraphNode[] = [], edges: GraphEdge[] = [];
  let previous: string | undefined;
  for (const entry of history) {
    if (entry.kind === "framing") continue;
    const id = entry.kind === "question" ? `q:${entry.questionId}` : entry.kind;
    const active = entry === history.at(-1);
    const questionId = entry.kind === "question" ? entry.questionId : undefined;
    nodes.push({ id, questionId, state: entry.kind === "verdict" ? "outcome" : active ? state.pendingFollowUp ? "clarification-required" : "current" : "answered" });
    if (previous) edges.push({ from: previous, to: id });
    previous = id;
    if (!questionId) continue;
    const question = QUESTIONS[questionId];
    const chosen = state.facts[questionId];
    const options = question.options.length ? question.options.map(o => o.key) : chosen !== undefined ? [chosen] : [];
    for (const key of options) {
      const answerId = `a:${questionId}:${question.options.length ? key : "value"}`;
      let next: OracleNode | undefined, blocked = false;
      if (active) {
        const base = current.kind === "framing" ? flowReducer(state, { type: "ADVANCE" }) : state;
        const after = flowReducer(base, { type: "ANSWER", questionId, value: key, today });
        blocked = after.blockedAnswer !== null;
        next = after.history.at(-1);
      }
      nodes.push({ id: answerId, questionId, answerKey: key, state: active ? "reachable-next-choice" : key === chosen ? "answered" : "not-selected", next, blocked });
      edges.push({ from: id, to: answerId, answerKey: key });
      if (!active && key === chosen) previous = answerId;
    }
  }
  return { nodes, edges };
}
