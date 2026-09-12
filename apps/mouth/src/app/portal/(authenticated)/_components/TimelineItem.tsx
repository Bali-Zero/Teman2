"use client";

/**
 * TimelineItem — extracted from the portal home so the timeline section
 * can be dynamic-imported, trimming the portal home's initial bundle.
 *
 * SAETTA-R19P W3 (2026-09-13): concept-F "RAPI" presentation pass. The card,
 * the icon chip and the coloured relative-date pills are gone: each event is
 * one entry on the page's hairline spine with a single 9px dot — copper and
 * filled when the event came from the client (a document, a message they
 * sent), hollow slate when it came from the team. Same props, same copy,
 * same reply handler.
 */

import React from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { TimelineEntry } from "@/lib/api/types/timeline.types";
import { usePortalDateFormat } from "@/lib/format/usePortalDateFormat";

/** Events the client themself produced: uploads and messages they sent. */
function isClientEvent(entry: TimelineEntry): boolean {
  if (entry.type === "document") return true;
  return entry.type === "message" && entry.status === "client_to_team";
}

function relativeLabel(occurredAt: string): string | null {
  const diff = Math.round(
    (new Date(occurredAt).getTime() - Date.now()) / 86400000,
  );
  if (diff === 0) return "Today";
  if (diff > 0) return `In ${diff}d`;
  const abs = Math.abs(diff);
  if (abs <= 7) return `${abs}d ago`;
  if (abs <= 30) return `${Math.floor(abs / 7)}w ago`;
  return null;
}

export function TimelineItem({
  entry,
  isLast,
}: {
  entry: TimelineEntry;
  isLast: boolean;
}) {
  const { formatDate } = usePortalDateFormat();
  const isFuture =
    "isFuture" in entry
      ? Boolean((entry as unknown as { isFuture?: boolean }).isFuture)
      : false;
  const fromClient = isClientEvent(entry);
  const relative = relativeLabel(entry.occurredAt);

  const _isLast = isLast; // retained for API compatibility
  void _isLast;

  return (
    <div className={cn("relative", isLast ? "pb-0" : "pb-[18px]")}>
      <div
        aria-hidden="true"
        className={cn(
          "absolute -left-[21px] top-[9px] h-[9px] w-[9px] rounded-full border-[1.5px]",
          fromClient
            ? "border-[var(--bz-copper)] bg-[var(--bz-copper)]"
            : "border-[var(--state-info)] bg-[var(--bz-base)]",
        )}
      />

      <div
        className="text-[10px] font-semibold uppercase tracking-[0.12em] tabular-nums text-[var(--tx-secondary)]"
        title={formatDate(entry.occurredAt, {
          weekday: "long",
          month: "long",
          day: "numeric",
          year: "numeric",
        })}
      >
        {formatDate(entry.occurredAt, { month: "short", day: "numeric" })}
        {relative ? ` · ${relative}` : ""}
        {isFuture && " · Upcoming"}
      </div>

      <h3 className="font-semibold text-[var(--tx-pure)]">{entry.title}</h3>
      {entry.description && (
        <p className="text-[13px] text-[var(--tx-secondary)] line-clamp-2">
          {entry.description}
        </p>
      )}

      {entry.type === "message" && entry.status === "team_to_client" && (
        <button
          type="button"
          onClick={() => {
            window.location.href = "/portal/chat";
          }}
          className="mt-1.5 inline-flex w-fit cursor-pointer items-center text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--bz-copper-text)] transition-colors hover:text-[var(--tx-pure)]"
        >
          Reply <ChevronRight className="w-3 h-3 ml-1" />
        </button>
      )}
    </div>
  );
}
