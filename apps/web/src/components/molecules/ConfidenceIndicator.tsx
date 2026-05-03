/**
 * ConfidenceIndicator — 6-factor confidence display.
 */

"use client";

import type { ConfidenceScores } from "@nuzantara/ts-schemas";
import { computeOverallConfidence } from "@nuzantara/ts-schemas";
import { Badge } from "@/components/atoms/Badge";

interface ConfidenceIndicatorProps {
  scores: ConfidenceScores;
  compact?: boolean;
}

const FACTOR_LABELS: Record<keyof ConfidenceScores, string> = {
  retrieval_relevance: "Retrieval",
  source_authority: "Authority",
  reasoning_coherence: "Reasoning",
  factual_grounding: "Facts",
  domain_coverage: "Coverage",
  answer_completeness: "Completeness",
};

export function ConfidenceIndicator({
  scores,
  compact = false,
}: ConfidenceIndicatorProps) {
  const overall = computeOverallConfidence(scores);
  const variant =
    overall >= 0.7 ? "success" : overall >= 0.4 ? "warning" : "error";
  const label =
    overall >= 0.7
      ? "High confidence"
      : overall >= 0.4
        ? "Medium confidence"
        : "Low confidence";

  if (compact) {
    return <Badge variant={variant}>{label}</Badge>;
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge variant={variant}>{label}</Badge>
        <span className="text-xs text-muted-foreground">
          {(overall * 100).toFixed(0)}%
        </span>
      </div>
      <div className="grid grid-cols-3 gap-1">
        {(
          Object.entries(FACTOR_LABELS) as [keyof ConfidenceScores, string][]
        ).map(([key, name]) => (
          <div key={key} className="text-xs">
            <span className="text-muted-foreground">{name}: </span>
            <span className="font-medium">
              {(scores[key] * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
