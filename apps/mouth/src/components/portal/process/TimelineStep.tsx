"use client";
import type { ProcessStep } from "@/lib/schemas/process";
import { StateBadge } from "./StateBadge";
import { STATE_COLORS } from "./stateColors";

interface Props {
  step: ProcessStep;
  onSelect: (step: ProcessStep) => void;
  isLast: boolean;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

export function TimelineStep({ step, onSelect, isLast }: Props) {
  const c = STATE_COLORS[step.status];
  const dateText = formatDate(step.changed_at ?? null);

  return (
    <li className="relative flex gap-4">
      <div className="flex flex-col items-center">
        <span
          aria-hidden
          data-testid="timeline-step-dot"
          data-completed={step.completed ? "true" : "false"}
          data-current={step.is_current ? "true" : "false"}
          className={`w-3 h-3 rounded-full border-2 ${step.completed ? "bg-current" : ""} ${step.is_current ? "ring-2 ring-offset-2" : ""}`}
          style={{
            borderColor: c.border,
            color: c.fg,
            // Incomplete dot + ring offset cut out to the page bg (warm
            // paper on day, anthracite on dark) — was bg-black /
            // ring-offset-black, which reads as a dead pixel on paper.
            ...(step.completed ? {} : { backgroundColor: "var(--bz-base)" }),
            ["--tw-ring-offset-color" as string]: "var(--bz-base)",
          }}
        />
        {!isLast && (
          <span
            className="flex-1 w-px my-1"
            style={{ background: "var(--bz-border)" }}
          />
        )}
      </div>
      <button
        type="button"
        onClick={() => onSelect(step)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(step);
          }
        }}
        className="flex-1 text-left pb-6 rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent-warm)]"
      >
        <div className="flex items-center gap-3 mb-1 flex-wrap">
          <h3 className="text-sm font-medium text-[var(--tx-primary)]">
            {step.label}
          </h3>
          <StateBadge state={step.status} label={step.label} />
          {step.is_current && (
            <span className="text-[10px] uppercase tracking-[2px] text-[var(--bz-copper-text,var(--tx-secondary))]">
              current
            </span>
          )}
        </div>
        {dateText && (
          <p className="text-xs text-[var(--bz-copper-text,var(--tx-secondary))]">
            {dateText}
            {step.changed_by ? ` · ${step.changed_by}` : ""}
          </p>
        )}
      </button>
    </li>
  );
}
