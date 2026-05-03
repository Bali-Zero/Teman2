"use client";
import type { ProcessStep } from "@/lib/schemas/process";
import { TimelineStep } from "./TimelineStep";

interface Props {
  steps: ProcessStep[];
  onSelect: (step: ProcessStep) => void;
}

export function ProcessTimeline({ steps, onSelect }: Props) {
  if (steps.length === 0) {
    return (
      <p className="text-sm text-[#c9a96e]/60 py-8 text-center">
        This practice has no steps yet. The team will set them up shortly.
      </p>
    );
  }

  return (
    <ol className="list-none p-0 m-0" aria-label="Practice timeline">
      {steps.map((step, i) => (
        <TimelineStep
          key={`${step.status}-${i}`}
          step={step}
          onSelect={onSelect}
          isLast={i === steps.length - 1}
        />
      ))}
    </ol>
  );
}
