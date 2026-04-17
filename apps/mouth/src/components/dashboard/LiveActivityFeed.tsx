import React from "react";
import type { LiveActivityEvent } from "@/types/dashboard-role.types";

const TYPE_BORDER: Record<LiveActivityEvent["type"], string> = {
  critical: "border-l-[#c45c78] bg-[rgba(196,92,120,0.045)]",
  ok: "border-l-[#5cb88a] bg-[rgba(92,184,138,0.045)]",
  warning: "border-l-[#b89a40] bg-[rgba(184,154,64,0.045)]",
  info: "border-l-[#4a8ec4] bg-[rgba(74,142,196,0.045)]",
  live: "border-l-[#48be9b] bg-[rgba(72,190,155,0.045)]",
};

const TAG_COLOR: Record<LiveActivityEvent["type"], string> = {
  critical: "bg-[rgba(196,92,120,0.16)] text-accent-pink-editorial",
  ok: "bg-[rgba(92,184,138,0.16)]  text-accent-sage",
  warning: "bg-[rgba(184,154,64,0.16)]  text-[#b89a40]",
  info: "bg-[rgba(74,142,196,0.16)]  text-[#4a8ec4]",
  live: "bg-[rgba(72,190,155,0.16)]  text-[#48be9b]",
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
          <div className="w-8 h-8 rounded bg-white/5 animate-pulse" />
          <div className="h-3 w-24 rounded bg-white/5 animate-pulse" />
        </div>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-8 rounded bg-white/5 animate-pulse mb-2" />
        ))}
      </div>
    );
  }

  return (
    <div
      className="glass-base glass-teal p-3.5 col-span-3 min-h-[240px]"
      style={{ boxShadow: "inset 0 0 30px rgba(72,190,155,0.03)" }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-2 h-2 rounded-full bg-[#48be9b] flex-shrink-0 live-dot-pulse"
          style={{
            boxShadow:
              "0 0 0 2px rgba(72,190,155,0.15), 0 0 7px rgba(72,190,155,0.5)",
          }}
        />
        <span className="text-[10px] font-bold text-[#48be9b] tracking-[.12em]">
          LIVE ACTIVITY
        </span>
        <span className="ml-auto text-[9px] text-white/25">
          {events.length} eventi
        </span>
      </div>

      {/* Feed */}
      <div
        className="flex flex-col gap-1.5 overflow-y-auto"
        style={{
          maxHeight: 160,
          scrollbarWidth: "thin",
          scrollbarColor: "rgba(72,190,155,0.2) transparent",
        }}
      >
        {events.map((e) => (
          <div
            key={e.id}
            className={`flex items-start gap-2 px-2.5 py-1.5 rounded-lg border-l-[2.5px] text-[11px] leading-snug ${TYPE_BORDER[e.type]}`}
          >
            <span className="text-sm flex-shrink-0 mt-px">{e.icon}</span>
            <span className="text-white/65 flex-1">
              {e.text}
              {e.tag && (
                <span
                  className={`inline-block ml-1.5 px-1.5 py-px rounded text-[8px] font-semibold tracking-wider ${TAG_COLOR[e.type]}`}
                >
                  {e.tag}
                </span>
              )}
            </span>
            <span className="text-[9px] text-white/22 flex-shrink-0">
              {e.timestamp}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
