"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Clock,
  MessageCircle,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type {
  WaCaseIntelligenceCard,
  WaCaseIntelligenceResponse,
} from "@/lib/api/crm/crm.types";

interface WaCaseIntelligencePanelProps {
  clientId: number;
}

function formatRelativeTime(iso?: string | null): string {
  if (!iso) return "unknown";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "unknown";
  const diffMs = Date.now() - ts;
  const diffH = Math.floor(diffMs / 3600000);
  if (diffH < 1) return "<1h ago";
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 30) return `${diffD}d ago`;
  const diffM = Math.floor(diffD / 30);
  return `${diffM}mo ago`;
}

function statusClass(status: string): string {
  switch (status) {
    case "blocked":
      return "border-red-500/40 bg-red-500/10 text-red-300";
    case "waiting":
      return "border-yellow-500/40 bg-yellow-500/10 text-yellow-300";
    case "done":
      return "border-green-500/40 bg-green-500/10 text-green-300";
    default:
      return "border-blue-500/40 bg-blue-500/10 text-blue-300";
  }
}

function textBlock(label: string, value?: string | null) {
  if (!value) return null;
  return (
    <div>
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--bz-text-2)]">
        {label}
      </p>
      <p className="mt-1 whitespace-pre-line text-sm leading-relaxed text-[var(--bz-text-1)]">
        {value}
      </p>
    </div>
  );
}

function CaseRow({
  item,
  expanded,
  onToggle,
}: {
  item: WaCaseIntelligenceCard;
  expanded: boolean;
  onToggle: () => void;
}) {
  const Icon = expanded ? ChevronDown : ChevronRight;
  const flags = item.flags || [];

  return (
    <div className="border-t border-[var(--bz-border)] first:border-t-0">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.03]"
      >
        <Icon className="mt-1 h-4 w-4 shrink-0 text-[var(--bz-text-2)]" />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-semibold text-[var(--bz-text-1)]">
              {item.display_name || item.counterpart_key || "WhatsApp case"}
            </p>
            <span
              className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusClass(item.case_status)}`}
            >
              {item.case_status}
            </span>
            {item.case_type && (
              <span className="rounded-full border border-[var(--bz-border)] px-2 py-0.5 text-[10px] text-[var(--bz-text-2)]">
                {item.case_type}
              </span>
            )}
          </div>
          {item.recap && (
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-[var(--bz-text-2)]">
              {item.recap}
            </p>
          )}
          <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[var(--bz-text-2)]">
            <span className="inline-flex items-center gap-1">
              <MessageCircle className="h-3 w-3" />
              {item.message_count} messages
            </span>
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatRelativeTime(item.last_message_at)}
            </span>
            <span>{item.source_model}</span>
          </div>
        </div>
      </button>

      {expanded && (
        <div className="space-y-4 px-8 pb-4">
          {flags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {flags.map((flag, index) => (
                <span
                  key={`${flag.id || flag.label}-${index}`}
                  className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-200"
                >
                  <AlertTriangle className="h-3 w-3" />
                  {flag.label}
                </span>
              ))}
            </div>
          )}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {textBlock("Next action", item.next_action)}
            {textBlock("Ideal reply", item.ideal_reply)}
          </div>
          {textBlock("Evidence", item.evidence)}
          {textBlock("CRM note", item.crm_packet)}
        </div>
      )}
    </div>
  );
}

export function WaCaseIntelligencePanel({
  clientId,
}: WaCaseIntelligencePanelProps) {
  const [response, setResponse] = useState<WaCaseIntelligenceResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const fetchCases = useCallback(async () => {
    try {
      const data = await api.crm.getClientWaCaseIntelligence(clientId);
      setResponse(data);
      setExpandedId(data.cases[0]?.id ?? null);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      logger.error(`WA case intelligence fetch failed for client ${clientId}`, {
        component: "WaCaseIntelligencePanel",
        itemId: String(clientId),
        reason: msg,
      });
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Sparkles className="h-4 w-4 animate-pulse" />
          <span>Loading WhatsApp intelligence...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-700/40 bg-red-950/20 p-4">
        <div className="flex items-start gap-2 text-sm text-red-400">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <div className="font-medium">
              Failed to load WhatsApp intelligence
            </div>
            <div className="mt-1 text-xs text-red-300/70">{error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (!response || response.status === "not_generated") return null;

  return (
    <section className="overflow-hidden rounded-lg border border-emerald-500/30 bg-gray-900/40">
      <div className="flex items-start justify-between gap-3 border-b border-[var(--bz-border)] px-4 py-3">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-emerald-300" />
          <h3 className="text-sm font-semibold text-[var(--bz-text-1)]">
            WhatsApp Case Intelligence
          </h3>
          <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-200">
            {response.case_count}
          </span>
        </div>
        <button
          type="button"
          onClick={fetchCases}
          className="rounded p-1 text-[var(--bz-text-2)] transition-colors hover:bg-white/[0.06] hover:text-[var(--bz-text-1)]"
          title="Refresh WhatsApp intelligence"
          aria-label="Refresh WhatsApp intelligence"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      <div>
        {response.cases.map((item) => (
          <CaseRow
            key={item.id}
            item={item}
            expanded={expandedId === item.id}
            onToggle={() =>
              setExpandedId(expandedId === item.id ? null : item.id)
            }
          />
        ))}
      </div>
    </section>
  );
}
