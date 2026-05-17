"use client";

import React, { useState, useMemo } from "react";
import {
  Clock,
  MessageCircle,
  Mail,
  Phone,
  Send,
  Calendar,
  FileText,
} from "lucide-react";
import type { Interaction } from "@/lib/api/crm/crm.types";
import { AiSummaryCard } from "./AiSummaryCard";

const CHANNEL_STYLES: Record<
  string,
  { icon: typeof MessageCircle; bg: string; text: string }
> = {
  whatsapp: {
    icon: MessageCircle,
    bg: "bg-green-500/20",
    text: "text-green-400",
  },
  email: { icon: Mail, bg: "bg-blue-500/20", text: "text-blue-400" },
  call: { icon: Phone, bg: "bg-purple-500/20", text: "text-purple-400" },
  telegram: { icon: Send, bg: "bg-sky-500/20", text: "text-sky-400" },
  meeting: { icon: Calendar, bg: "bg-orange-500/20", text: "text-orange-400" },
  note: { icon: FileText, bg: "bg-yellow-500/20", text: "text-yellow-400" },
};

const SENTIMENT_STYLES: Record<string, string> = {
  positive: "bg-green-500/20 text-green-400",
  neutral: "bg-gray-500/20 text-gray-400",
  negative: "bg-red-500/20 text-red-400",
  mixed: "bg-yellow-500/20 text-yellow-400",
};

export function TimelineTab({
  interactions,
  formatDate,
  formatTime,
  clientCreatedAt,
  clientFirstContact,
  clientId,
}: {
  interactions: Interaction[];
  formatDate: (d: string) => string;
  formatTime: (d: string) => string;
  clientCreatedAt?: string;
  clientFirstContact?: string;
  clientId: number;
}) {
  const [filterType, setFilterType] = useState<string>("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const toggleExpand = (id: number) =>
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  // Get unique interaction types
  const types = useMemo(
    () => Array.from(new Set(interactions.map((i) => i.interaction_type))),
    [interactions],
  );

  const filtered = useMemo(
    () =>
      filterType === "all"
        ? interactions
        : interactions.filter((i) => i.interaction_type === filterType),
    [interactions, filterType],
  );

  // Stats
  const sentimentCount = useMemo(() => {
    const counts: Record<string, number> = {
      positive: 0,
      negative: 0,
      neutral: 0,
    };
    interactions.forEach((i) => {
      if (i.sentiment && counts[i.sentiment] !== undefined)
        counts[i.sentiment]++;
    });
    return counts;
  }, [interactions]);

  if (interactions.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-10 text-center shadow-xl space-y-3">
        <Clock className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-2 opacity-40" />
        <p className="text-sm font-medium text-[var(--bz-text-1)]">
          No interactions recorded yet
        </p>
        <p className="text-xs text-[var(--bz-text-2)] opacity-70">
          Interactions from WhatsApp, Telegram, email, calls, and notes will
          appear here.
        </p>
        {(clientCreatedAt || clientFirstContact) && (
          <div className="mt-4 flex flex-col items-center gap-2 text-xs text-[var(--bz-text-2)]">
            {clientCreatedAt && (
              <span>
                Client added:{" "}
                <span className="text-[var(--bz-text-1)]">
                  {formatDate(clientCreatedAt)}
                </span>
              </span>
            )}
            {clientFirstContact && (
              <span>
                First contact:{" "}
                <span className="text-[var(--bz-text-1)]">
                  {formatDate(clientFirstContact)}
                </span>
              </span>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* AI Summary (CRM-Guardian L1 cross-folder, timeline events overlay) */}
      <AiSummaryCard clientId={clientId} section="timeline" />
      {/* Header + stats */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">
            Activity Timeline
          </h3>
          <p className="text-sm text-[var(--bz-text-2)] mt-0.5">
            {interactions.length} interactions total
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {sentimentCount.positive > 0 && (
            <span className="text-xs bg-green-500/20 text-green-400 px-2 py-1 rounded-full">
              {sentimentCount.positive} positive
            </span>
          )}
          {sentimentCount.negative > 0 && (
            <span className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded-full">
              {sentimentCount.negative} negative
            </span>
          )}
        </div>
      </div>

      {/* Channel filter */}
      {types.length > 1 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          {(["all", ...types] as string[]).map((t) => (
            <button
              key={t}
              onClick={() => setFilterType(t)}
              className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                filterType === t
                  ? "bg-[var(--bz-accent)] text-white"
                  : "bg-[var(--bz-surface)] text-[var(--bz-text-2)] hover:bg-[var(--bz-card)]"
              }`}
            >
              {t === "all"
                ? `All (${interactions.length})`
                : `${t} (${interactions.filter((i) => i.interaction_type === t).length})`}
            </button>
          ))}
        </div>
      )}

      {/* Timeline */}
      <div className="space-y-1">
        {filtered.map((interaction, idx) => {
          const style =
            CHANNEL_STYLES[interaction.interaction_type] || CHANNEL_STYLES.note;
          const Icon = style.icon;
          const isExpanded = expandedIds.has(interaction.id);
          const hasLongSummary = (interaction.summary?.length ?? 0) > 120;

          return (
            <div key={interaction.id} className="flex gap-3">
              {/* Icon + connector */}
              <div className="flex flex-col items-center shrink-0">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${style.bg} ${style.text}`}
                >
                  <Icon className="w-3.5 h-3.5" />
                </div>
                {idx < filtered.length - 1 && (
                  <div className="w-px flex-1 min-h-[24px] bg-[var(--bz-border)] mt-1" />
                )}
              </div>

              {/* Card */}
              <div className="flex-1 pb-3 min-w-0">
                <div className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] p-3 hover:border-[var(--bz-accent)]/30 transition-colors">
                  {/* Row 1: type + direction + date */}
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className={`text-xs font-semibold capitalize ${style.text}`}
                      >
                        {interaction.interaction_type}
                      </span>
                      {interaction.direction && (
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                            interaction.direction === "inbound"
                              ? "bg-blue-500/15 text-blue-400"
                              : "bg-green-500/15 text-green-400"
                          }`}
                        >
                          {interaction.direction === "inbound"
                            ? "← In"
                            : "→ Out"}
                        </span>
                      )}
                      {interaction.sentiment && (
                        <span
                          className={`text-[10px] px-1.5 py-0.5 rounded-full ${SENTIMENT_STYLES[interaction.sentiment] || "bg-gray-500/20 text-gray-400"}`}
                        >
                          {interaction.sentiment}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {(() => {
                        const ageDays = Math.floor(
                          (Date.now() -
                            new Date(interaction.interaction_date).getTime()) /
                            86400000,
                        );
                        const label =
                          ageDays === 0
                            ? "today"
                            : ageDays === 1
                              ? "1d ago"
                              : ageDays >= 30
                                ? `${Math.floor(ageDays / 30)}mo ago`
                                : ageDays >= 7
                                  ? `${Math.floor(ageDays / 7)}w ago`
                                  : `${ageDays}d ago`;
                        return (
                          <span
                            className="text-[9px] px-1.5 py-0.5 rounded tabular-nums"
                            style={{
                              background:
                                ageDays === 0
                                  ? "rgba(34,197,94,0.12)"
                                  : ageDays <= 7
                                    ? "rgba(255,255,255,0.05)"
                                    : "rgba(255,255,255,0.04)",
                              color:
                                ageDays === 0 ? "#4ade80" : "var(--bz-text-2)",
                            }}
                          >
                            {label}
                          </span>
                        );
                      })()}
                      <span className="text-[10px] text-[var(--bz-text-2)]">
                        {formatDate(interaction.interaction_date)}{" "}
                        <span className="opacity-70">
                          {formatTime(interaction.interaction_date)}
                        </span>
                      </span>
                    </div>
                  </div>

                  {/* Subject */}
                  {interaction.subject && (
                    <p className="text-sm font-medium text-[var(--bz-text-1)] mb-1 truncate">
                      {interaction.subject}
                    </p>
                  )}

                  {/* Summary */}
                  {interaction.summary && (
                    <div>
                      <p
                        className={`text-xs text-[var(--bz-text-2)] ${!isExpanded && hasLongSummary ? "line-clamp-2" : ""}`}
                      >
                        {interaction.summary}
                      </p>
                      {hasLongSummary && (
                        <button
                          onClick={() => toggleExpand(interaction.id)}
                          className="text-[10px] text-[var(--bz-accent)] hover:underline mt-0.5"
                        >
                          {isExpanded ? "Show less" : "Show more"}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Footer */}
                  {(interaction.team_member || interaction.channel) && (
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] text-[var(--bz-text-2)]">
                      {interaction.team_member && (
                        <span>{interaction.team_member.split("@")[0]}</span>
                      )}
                      {interaction.channel &&
                        interaction.channel !==
                          interaction.interaction_type && (
                          <span>via {interaction.channel}</span>
                        )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
