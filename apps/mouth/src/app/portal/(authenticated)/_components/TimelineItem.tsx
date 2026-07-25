"use client";

/**
 * TimelineItem — extracted from the portal home so the timeline section
 * can be dynamic-imported, trimming the portal home's initial bundle.
 *
 * WS3 (GARUDA Day Edition, 2026-07-24): day-theme token alignment —
 * semantic --state-* tokens (WS2 AA light overrides) instead of dark-theme
 * neon/utility colors; no hardcoded hexes or white-alpha tints.
 */

import React from "react";
import {
  Clock,
  MessageCircle,
  FileText,
  Briefcase,
  AlertTriangle,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimelineEntry } from "@/lib/api/types/timeline.types";

export function TimelineItem({
  entry,
  isLast,
}: {
  entry: TimelineEntry;
  isLast: boolean;
}) {
  const isFuture =
    "isFuture" in entry
      ? Boolean((entry as unknown as { isFuture?: boolean }).isFuture)
      : false;

  const getIcon = () => {
    switch (entry.type) {
      case "message":
        return <MessageCircle className="w-4 h-4" />;
      case "document":
        return <FileText className="w-4 h-4" />;
      case "practice":
        return <Briefcase className="w-4 h-4" />;
      case "deadline":
        return <AlertTriangle className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  const getBgColor = () => {
    if (isFuture)
      return "bg-[color-mix(in_srgb,var(--state-warning)_12%,transparent)] text-[var(--state-warning)]";
    switch (entry.type) {
      case "message":
        return "bg-[color-mix(in_srgb,var(--state-info)_12%,transparent)] text-[var(--state-info)]";
      case "deadline":
        return "bg-[color-mix(in_srgb,var(--state-danger)_12%,transparent)] text-[var(--state-danger)]";
      default:
        return "text-[var(--tx-secondary)]";
    }
  };

  const getDotStyle = (): React.CSSProperties => {
    if (isFuture)
      return {
        background: "color-mix(in srgb, var(--state-warning) 10%, transparent)",
        color: "var(--state-warning)",
        borderColor: "var(--state-warning)",
      };
    switch (entry.type) {
      case "message":
        return {
          background: "color-mix(in srgb, var(--state-info) 10%, transparent)",
          color: "var(--state-info)",
          borderColor: "var(--state-info)",
        };
      case "deadline":
        return {
          background:
            "color-mix(in srgb, var(--state-danger) 10%, transparent)",
          color: "var(--state-danger)",
          borderColor: "var(--state-danger)",
        };
      default:
        return {
          background: "var(--glass-rim)",
          color: "var(--tx-secondary)",
          borderColor: "var(--bz-border-hover)",
        };
    }
  };

  const _isLast = isLast; // retained for API compatibility
  void _isLast;

  return (
    <div className="relative pl-6">
      <div
        className="absolute -left-[9px] top-0 w-4 h-4 rounded-full flex items-center justify-center border-2 border-[var(--bz-base)] shadow-[0_0_10px_currentColor]"
        style={getDotStyle()}
      >
        {/* Dot only */}
      </div>

      <div
        className="crystal-stat-card !border !p-4 !shadow-none"
        style={{
          ...(isFuture
            ? {
                background:
                  "color-mix(in srgb, var(--state-warning) 3%, transparent)",
              }
            : {}),
          borderColor: isFuture
            ? "color-mix(in srgb, var(--state-warning) 25%, transparent)"
            : "var(--glass-rim)",
        }}
      >
        <div className="flex items-center gap-2 mb-2">
          <div
            className={cn(
              "p-1.5 rounded-lg border border-[var(--bz-border)] bg-[var(--glass-rim)]",
              getBgColor(),
            )}
          >
            {getIcon()}
          </div>
          <span
            className="text-[10px] font-bold uppercase tracking-widest text-[var(--tx-secondary)]"
            title={new Date(entry.occurredAt).toLocaleDateString("en-US", {
              weekday: "long",
              month: "long",
              day: "numeric",
              year: "numeric",
            })}
          >
            {new Date(entry.occurredAt).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
            {isFuture && " (Upcoming)"}
          </span>
          {(() => {
            const diff = Math.round(
              (new Date(entry.occurredAt).getTime() - Date.now()) / 86400000,
            );
            if (diff === 0)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--state-success)_12%,transparent)] text-[var(--state-success)] font-semibold">
                  Today
                </span>
              );
            if (diff > 0)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[color-mix(in_srgb,var(--state-warning)_12%,transparent)] text-[var(--state-warning)] font-semibold">
                  ⏰ In {diff}d
                </span>
              );
            const abs = Math.abs(diff);
            if (abs <= 7)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--glass-rim)] text-[var(--bz-text-2)] font-semibold">
                  {abs}d ago
                </span>
              );
            if (abs <= 30)
              return (
                <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--glass-rim)] text-[var(--bz-text-2)] font-semibold">
                  {Math.floor(abs / 7)}w ago
                </span>
              );
            return null;
          })()}
        </div>

        <h3 className="font-bold text-[var(--tx-pure)] text-sm">
          {entry.title}
        </h3>
        <p className="text-xs mt-1.5 text-[var(--tx-secondary)] line-clamp-2">
          {entry.description}
        </p>

        {entry.type === "message" && entry.status === "team_to_client" && (
          <button
            type="button"
            onClick={() => {
              window.location.href = "/portal/chat";
            }}
            className="mt-3 text-[10px] font-bold uppercase tracking-widest flex items-center text-[var(--bz-copper-text)] hover:text-[var(--tx-pure)] transition-colors cursor-pointer w-fit inline-flex"
          >
            Reply <ChevronRight className="w-3 h-3 ml-1" />
          </button>
        )}
      </div>
    </div>
  );
}
