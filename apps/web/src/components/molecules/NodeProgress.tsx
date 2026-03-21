/**
 * NodeProgress — shows current graph node during SSE streaming.
 */

"use client";

import { Spinner } from "@/components/atoms/Spinner";

const NODE_LABELS: Record<string, string> = {
  pipeline: "Starting...",
  understand: "Understanding query...",
  retrieve: "Searching knowledge base...",
  grade_retrieval: "Evaluating results...",
  reason: "Reasoning...",
  grade_reasoning: "Evaluating reasoning...",
  synthesize: "Writing answer...",
  grade_answer: "Checking answer quality...",
  grade_hallucination: "Verifying facts...",
  subgraph_company: "Analyzing company setup...",
  subgraph_visa: "Checking visa requirements...",
  subgraph_property: "Reviewing property options...",
  subgraph_tax: "Calculating tax obligations...",
  tools: "Using tools...",
};

interface NodeProgressProps {
  currentNode: string;
  className?: string;
}

export function NodeProgress({
  currentNode,
  className = "",
}: NodeProgressProps) {
  if (!currentNode) return null;

  const label = NODE_LABELS[currentNode] ?? `Processing: ${currentNode}`;

  return (
    <div
      className={`flex items-center gap-2 text-sm text-muted-foreground ${className}`}
    >
      <Spinner size="sm" />
      <span>{label}</span>
    </div>
  );
}
