import React from "react";
import type { LiveActivityEvent } from "@/types/dashboard-role.types";

const TYPE_BORDER: Record<LiveActivityEvent["type"], string> = {
  critical:
    "border-l-[var(--state-danger)] bg-[color-mix(in_srgb,var(--state-danger)_6%,transparent)]",
  ok: "border-l-[var(--state-success)] bg-[color-mix(in_srgb,var(--state-success)_6%,transparent)]",
  warning:
    "border-l-[var(--state-warning)] bg-[color-mix(in_srgb,var(--state-warning)_6%,transparent)]",
  info: "border-l-[var(--state-info)] bg-[color-mix(in_srgb,var(--state-info)_6%,transparent)]",
  live: "border-l-[var(--state-success)] bg-[color-mix(in_srgb,var(--state-success)_6%,transparent)]",
};

const TAG_COLOR: Record<LiveActivityEvent["type"], string> = {
  critical:
    "bg-[color-mix(in_srgb,var(--state-danger)_14%,transparent)] text-[var(--state-danger)]",
  ok: "bg-[color-mix(in_srgb,var(--state-success)_14%,transparent)] text-[var(--state-success)]",
  warning:
    "bg-[color-mix(in_srgb,var(--state-warning)_14%,transparent)] text-[var(--state-warning)]",
  info: "bg-[color-mix(in_srgb,var(--state-info)_14%,transparent)] text-[var(--state-info)]",
  live: "bg-[color-mix(in_srgb,var(--state-success)_14%,transparent)] text-[var(--state-success)]",
};

interface LiveActivityFeedProps {
  events: LiveActivityEvent[];
  isLoading: boolean;
}

export function LiveActivityFeed({ events, isLoading }: LiveActivityFeedProps) {
  if (isLoading) {
    return (
      <div className="glass-base glass-teal p-3.5 col-span-3 min-h-[240px]">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-8 h-8 rounded bg-[var(--surface-raised)] animate-pulse" />
          <div className="h-3 w-24 rounded bg-[var(--surface-raised)] animate-pulse" />
        </div>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-8 rounded bg-[var(--surface-raised)] animate-pulse mb-2"
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className="glass-base glass-teal p-3.5 col-span-3 min-h-[240px]"
      style={{
        background: "var(--bz-card)",
        borderColor: "var(--bz-border)",
        boxShadow:
          "inset 0 0 30px color-mix(in srgb, var(--state-success) 4%, transparent)",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-2 h-2 rounded-full bg-[var(--state-success)] flex-shrink-0 live-dot-pulse"
          style={{
            boxShadow:
              "0 0 0 2px color-mix(in srgb, var(--state-success) 18%, transparent), 0 0 7px color-mix(in srgb, var(--state-success) 55%, transparent)",
          }}
        />
        <span className="text-[10px] font-bold text-[var(--state-success)] tracking-[.12em]">
          LIVE ACTIVITY
        </span>
        <span className="ml-auto text-[9px] text-[var(--bz-text-3)]">
          {events.length} events
        </span>
      </div>

      {/* Feed */}
      <div
        className="flex flex-col gap-1.5 overflow-y-auto"
        style={{
          maxHeight: 160,
          scrollbarWidth: "thin",
          scrollbarColor:
            "color-mix(in srgb, var(--state-success) 30%, transparent) transparent",
        }}
      >
        {events.map((e) => (
          <div
            key={e.id}
            className={`flex items-start gap-2 px-2.5 py-1.5 rounded-lg border-l-[2.5px] text-[11px] leading-snug ${TYPE_BORDER[e.type]}`}
          >
            <span className="text-sm flex-shrink-0 mt-px">{e.icon}</span>
            <span className="text-[var(--bz-text-2)] flex-1">
              {e.text}
              {e.tag && (
                <span
                  className={`inline-block ml-1.5 px-1.5 py-px rounded text-[8px] font-semibold tracking-wider ${TAG_COLOR[e.type]}`}
                >
                  {e.tag}
                </span>
              )}
            </span>
            <span className="text-[9px] text-[var(--bz-text-3)] flex-shrink-0">
              {e.timestamp}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
