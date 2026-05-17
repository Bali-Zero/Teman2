"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles,
  RefreshCw,
  AlertTriangle,
  Clock,
  CheckCircle2,
  Info,
} from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type {
  AiSummaryResponse,
  L1ClientSummary,
} from "@/lib/api/crm/crm.types";

/**
 * Section slot — selects which slice of the L1 summary to render.
 *
 * - "overview"    → archetype/tier/narrative/red_flags (used in OverviewTab)
 * - "company"     → legal_name/KBLI/capital/lkpm/tax (CompanyTab)
 * - "tax"         → tax_records + LKPM history + spt_tahunan (TaxTab)
 * - "immigration" → visa block (ImmigrationTab)
 * - "family"      → shareholders + family relationships (FamilyTab)
 * - "documents"   → documents inventory by doc_type (DocumentsTab)
 * - "process"     → red_flags + compliance signals (ProcessTab)
 * - "timeline"    → timeline events overlay (TimelineTab)
 */
export type AiSummarySection =
  | "overview"
  | "company"
  | "tax"
  | "immigration"
  | "family"
  | "documents"
  | "process"
  | "timeline";

interface AiSummaryCardProps {
  clientId: number;
  section: AiSummarySection;
  /** Auto-refresh interval in ms when status='pending'. Set to 0 to disable. */
  pollIntervalMs?: number;
}

const SECTION_TITLES: Record<AiSummarySection, string> = {
  overview: "AI Summary",
  company: "Company (AI)",
  tax: "Tax (AI)",
  immigration: "Visa (AI)",
  family: "Family (AI)",
  documents: "Documents (AI)",
  process: "Process Signals (AI)",
  timeline: "Timeline (AI)",
};

const ARCHETYPE_LABELS: Record<string, string> = {
  individual_expat: "Individual expat",
  individual_investor: "Individual investor",
  pt_pma_owner: "PT PMA owner",
  family_member: "Family member",
  property_holder: "Property holder",
  business_only: "Business only",
  other: "Other",
};

const TIER_BADGE_COLORS: Record<string, string> = {
  VIP: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  standard: "bg-blue-500/20 text-blue-300 border-blue-500/40",
  archive: "bg-gray-500/20 text-gray-400 border-gray-500/40",
  unknown: "bg-gray-700/20 text-gray-500 border-gray-700/40",
};

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "never";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "unknown";
  const diffMs = Date.now() - ts;
  const diffH = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffH < 1) return "<1h ago";
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return "1 day ago";
  if (diffD < 30) return `${diffD} days ago`;
  const diffM = Math.floor(diffD / 30);
  return diffM === 1 ? "1 month ago" : `${diffM} months ago`;
}

function freshnessColor(iso: string | null): string {
  if (!iso) return "text-gray-500";
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return "text-gray-500";
  const diffH = (Date.now() - ts) / (1000 * 60 * 60);
  if (diffH < 24) return "text-green-400";
  if (diffH < 24 * 7) return "text-yellow-400";
  return "text-red-400";
}

export function AiSummaryCard({
  clientId,
  section,
  pollIntervalMs = 30000,
}: AiSummaryCardProps) {
  const [response, setResponse] = useState<AiSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    try {
      const data = await api.crm.getClientAiSummary(clientId);
      setResponse(data);
      setError(null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      logger.error(`AiSummaryCard fetch failed for client ${clientId}`, {
        component: "AiSummaryCard",
        itemId: String(clientId),
        reason: msg,
      });
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  // Auto-poll while pending
  useEffect(() => {
    if (pollIntervalMs <= 0 || response?.status !== "pending") return;
    const id = setInterval(fetchSummary, pollIntervalMs);
    return () => clearInterval(id);
  }, [response?.status, pollIntervalMs, fetchSummary]);

  const title = SECTION_TITLES[section];

  // Loading state
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-4">
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Sparkles className="h-4 w-4 animate-pulse" />
          <span>Loading {title}…</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-lg border border-red-700/40 bg-red-950/20 p-4">
        <div className="flex items-start gap-2 text-sm text-red-400">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-medium">Failed to load {title}</div>
            <div className="text-xs text-red-300/70 mt-1">{error}</div>
          </div>
        </div>
      </div>
    );
  }

  if (!response) return null;

  // Empty states: not generated / pending
  if (response.status === "not_generated") {
    return (
      <div className="rounded-lg border border-gray-700/50 bg-gray-900/40 p-4">
        <div className="flex items-start gap-2 text-sm text-gray-400">
          <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
          <div>
            <div className="font-medium text-gray-300">
              {title} not generated yet
            </div>
            <div className="text-xs text-gray-500 mt-1">
              The CRM-Guardian worker has not processed this client. It will run
              automatically when Drive content changes.
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (response.status === "pending") {
    return (
      <div className="rounded-lg border border-blue-700/40 bg-blue-950/20 p-4">
        <div className="flex items-start gap-2 text-sm text-blue-300">
          <Clock className="h-4 w-4 mt-0.5 flex-shrink-0 animate-pulse" />
          <div>
            <div className="font-medium">{title} generation in progress</div>
            <div className="text-xs text-blue-200/70 mt-1">
              Worker is processing this client. Refreshing every{" "}
              {Math.round(pollIntervalMs / 1000)}s.
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Available — render section-specific body
  const summary = response.summary;
  if (!summary) return null;

  return (
    <div className="rounded-lg border border-amber-500/30 bg-gradient-to-br from-amber-950/10 to-gray-900/40 p-4">
      <CardHeader
        title={title}
        generatedAt={response.generated_at}
        confidence={summary.extraction_confidence ?? null}
        onRefresh={fetchSummary}
      />
      <div className="mt-3">
        <SectionBody section={section} summary={summary} />
      </div>
    </div>
  );
}

function CardHeader({
  title,
  generatedAt,
  confidence,
  onRefresh,
}: {
  title: string;
  generatedAt: string | null;
  confidence: number | null;
  onRefresh: () => void;
}) {
  const confidencePct =
    confidence !== null ? Math.round(confidence * 100) : null;
  const lowConfidence = confidence !== null && confidence < 0.6;

  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-amber-400" />
        <h3 className="text-sm font-semibold text-gray-100">{title}</h3>
        {lowConfidence && (
          <span
            className="rounded-full border border-yellow-500/40 bg-yellow-500/10 px-2 py-0.5 text-[10px] font-medium text-yellow-300"
            title="Extraction confidence below 0.6 — manual review recommended"
          >
            Review
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs">
        {confidencePct !== null && (
          <span
            className="text-gray-400"
            title={`Extraction confidence: ${confidence?.toFixed(2)}`}
          >
            {confidencePct}%
          </span>
        )}
        <span
          className={freshnessColor(generatedAt)}
          title={`Generated: ${generatedAt ?? "never"}`}
        >
          {formatRelativeTime(generatedAt)}
        </span>
        <button
          onClick={onRefresh}
          className="text-gray-400 hover:text-gray-200 transition-colors"
          title="Refresh summary"
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function SectionBody({
  section,
  summary,
}: {
  section: AiSummarySection;
  summary: L1ClientSummary;
}) {
  switch (section) {
    case "overview":
      return <OverviewBody summary={summary} />;
    case "company":
      return <CompanyBody summary={summary} />;
    case "tax":
      return <TaxBody summary={summary} />;
    case "immigration":
      return <ImmigrationBody summary={summary} />;
    case "family":
      return <FamilyBody summary={summary} />;
    case "documents":
      return <DocumentsBody summary={summary} />;
    case "process":
      return <ProcessBody summary={summary} />;
    case "timeline":
      return <TimelineBody summary={summary} />;
  }
}

// ============================================================
// Section bodies
// ============================================================

function OverviewBody({ summary }: { summary: L1ClientSummary }) {
  const profile = summary.profile;
  const archetypeLabel = profile?.archetype
    ? (ARCHETYPE_LABELS[profile.archetype] ?? profile.archetype)
    : "Unknown";
  const tier = profile?.tier ?? "unknown";
  const tierClass = TIER_BADGE_COLORS[tier] ?? TIER_BADGE_COLORS.unknown;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-gray-600/50 bg-gray-800/40 px-2 py-1 text-xs text-gray-300">
          {archetypeLabel}
        </span>
        <span
          className={`rounded border px-2 py-1 text-xs font-medium ${tierClass}`}
        >
          {tier === "unknown" ? "Unknown tier" : tier}
        </span>
        {profile?.primary_service && profile.primary_service !== "unknown" && (
          <span className="rounded border border-gray-600/50 bg-gray-800/40 px-2 py-1 text-xs text-gray-400">
            {profile.primary_service.replace(/_/g, " ")}
          </span>
        )}
      </div>
      {summary.narrative_en && (
        <p className="text-sm text-gray-300 leading-relaxed">
          {summary.narrative_en}
        </p>
      )}
      {summary.compliance?.red_flags &&
        summary.compliance.red_flags.length > 0 && (
          <div className="rounded border border-red-700/40 bg-red-950/20 p-2">
            <div className="flex items-center gap-1 text-xs font-medium text-red-300 mb-1">
              <AlertTriangle className="h-3 w-3" /> Red flags
            </div>
            <ul className="text-xs text-red-200/80 space-y-0.5 list-disc list-inside">
              {summary.compliance.red_flags.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          </div>
        )}
    </div>
  );
}

function CompanyBody({ summary }: { summary: L1ClientSummary }) {
  const c = summary.company;
  if (!c || !c.legal_name) {
    return <EmptySectionMsg text="No company linked to this client." />;
  }
  return (
    <div className="space-y-2 text-sm">
      <div className="font-medium text-gray-100">
        {c.legal_name}
        {c.legal_form && (
          <span className="ml-2 text-xs text-gray-500">({c.legal_form})</span>
        )}
      </div>
      <KvRow label="NIB" value={c.nib} />
      <KvRow label="NPWP Corporate" value={c.npwp_corporate} />
      <KvRow label="KBLI primary" value={c.kbli_primary} />
      {c.kbli_codes && c.kbli_codes.length > 0 && (
        <KvRow label="KBLI codes" value={c.kbli_codes.join(", ")} />
      )}
      {c.paid_up_capital_idr !== null &&
        c.paid_up_capital_idr !== undefined && (
          <KvRow
            label="Paid-up capital"
            value={`Rp ${c.paid_up_capital_idr.toLocaleString("id-ID")}`}
          />
        )}
      <KvRow label="Akta" value={c.akta_number} />
      <KvRow label="SK Kemenkumham" value={c.sk_kemenkumham} />
    </div>
  );
}

function TaxBody({ summary }: { summary: L1ClientSummary }) {
  const records = summary.company?.tax_records ?? [];
  const compliance = summary.compliance;

  if (records.length === 0 && !compliance?.spt_tahunan_last) {
    return <EmptySectionMsg text="No tax records extracted yet." />;
  }
  return (
    <div className="space-y-2 text-sm">
      {compliance?.spt_tahunan_last && (
        <KvRow label="Last SPT Tahunan" value={compliance.spt_tahunan_last} />
      )}
      {compliance?.lkpm_last_reported && (
        <KvRow label="Last LKPM" value={compliance.lkpm_last_reported} />
      )}
      {compliance?.lkpm_next_due && (
        <KvRow
          label="LKPM next due"
          value={compliance.lkpm_next_due}
          highlight={
            new Date(compliance.lkpm_next_due).getTime() <
            Date.now() + 7 * 24 * 60 * 60 * 1000
          }
        />
      )}
      {records.length > 0 && (
        <div className="mt-2 space-y-1">
          <div className="text-xs font-medium text-gray-400 mb-1">
            Tax records ({records.length})
          </div>
          {records.slice(0, 5).map((r, i) => (
            <div
              key={i}
              className="rounded border border-gray-700/40 bg-gray-900/40 px-2 py-1 text-xs"
            >
              <span className="font-medium text-gray-200">{r.period}</span>
              {r.spt_type && (
                <span className="ml-2 text-gray-500">{r.spt_type}</span>
              )}
              <span
                className={`ml-2 ${
                  r.status === "filed"
                    ? "text-green-400"
                    : r.status === "overdue"
                      ? "text-red-400"
                      : "text-gray-500"
                }`}
              >
                {r.status}
              </span>
              {r.amount_idr !== null && r.amount_idr !== undefined && (
                <span className="ml-2 text-gray-400">
                  Rp {r.amount_idr.toLocaleString("id-ID")}
                </span>
              )}
            </div>
          ))}
          {records.length > 5 && (
            <div className="text-xs text-gray-500">
              + {records.length - 5} more…
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ImmigrationBody({ summary }: { summary: L1ClientSummary }) {
  const v = summary.visa;
  const passportExp = summary.identity?.passport_expires_at;
  const visaExpDays = summary.compliance?.visa_days_until_expiry;
  const passportExpDays = summary.compliance?.passport_days_until_expiry;
  if (!v?.visa_type && !passportExp) {
    return <EmptySectionMsg text="No visa data extracted yet." />;
  }
  return (
    <div className="space-y-2 text-sm">
      <KvRow label="Visa type" value={v?.visa_type} />
      <KvRow label="Stay permit" value={v?.stay_permit_number} />
      <KvRow
        label="Valid until"
        value={v?.valid_until}
        highlight={
          visaExpDays !== null && visaExpDays !== undefined && visaExpDays < 60
        }
      />
      {visaExpDays !== null && visaExpDays !== undefined && (
        <KvRow
          label="Days to visa expiry"
          value={String(visaExpDays)}
          highlight={visaExpDays < 60}
        />
      )}
      <KvRow label="Sponsor" value={v?.sponsor_company} />
      <KvRow
        label="Passport expires"
        value={passportExp}
        highlight={
          passportExpDays !== null &&
          passportExpDays !== undefined &&
          passportExpDays < 180
        }
      />
    </div>
  );
}

function FamilyBody({ summary }: { summary: L1ClientSummary }) {
  const shareholders = summary.shareholders ?? [];
  if (shareholders.length === 0) {
    return <EmptySectionMsg text="No shareholder or family data extracted." />;
  }
  return (
    <div className="space-y-1 text-sm">
      <div className="text-xs font-medium text-gray-400 mb-1">
        Shareholders / persons ({shareholders.length})
      </div>
      {shareholders.map((s, i) => (
        <div
          key={i}
          className="rounded border border-gray-700/40 bg-gray-900/40 px-2 py-1 text-xs"
        >
          <span className="font-medium text-gray-200">{s.name}</span>
          {s.role && <span className="ml-2 text-gray-500">{s.role}</span>}
          {s.percentage !== null && s.percentage !== undefined && (
            <span className="ml-2 text-gray-400">{s.percentage}%</span>
          )}
          {s.nationality && (
            <span className="ml-2 text-gray-500">{s.nationality}</span>
          )}
        </div>
      ))}
    </div>
  );
}

function DocumentsBody({ summary }: { summary: L1ClientSummary }) {
  const docs = summary.documents ?? [];
  if (docs.length === 0) {
    return <EmptySectionMsg text="No documents catalogued yet." />;
  }
  // Group by doc_type
  const byType = docs.reduce<Record<string, number>>((acc, d) => {
    acc[d.doc_type] = (acc[d.doc_type] ?? 0) + 1;
    return acc;
  }, {});
  return (
    <div className="space-y-2 text-sm">
      <div className="text-xs text-gray-400">
        Total documents: <span className="text-gray-200">{docs.length}</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(byType)
          .sort((a, b) => b[1] - a[1])
          .map(([type, count]) => (
            <span
              key={type}
              className="rounded border border-gray-700/40 bg-gray-900/40 px-2 py-0.5 text-xs text-gray-300"
            >
              {type} <span className="text-gray-500">({count})</span>
            </span>
          ))}
      </div>
    </div>
  );
}

function ProcessBody({ summary }: { summary: L1ClientSummary }) {
  const flags = summary.compliance?.red_flags ?? [];
  const notes = summary.extraction_notes ?? [];

  if (flags.length === 0 && notes.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-green-400">
        <CheckCircle2 className="h-4 w-4" />
        <span>No red flags detected.</span>
      </div>
    );
  }
  return (
    <div className="space-y-2 text-sm">
      {flags.length > 0 && (
        <div className="rounded border border-red-700/40 bg-red-950/20 p-2">
          <div className="text-xs font-medium text-red-300 mb-1 flex items-center gap-1">
            <AlertTriangle className="h-3 w-3" /> Red flags ({flags.length})
          </div>
          <ul className="text-xs text-red-200/80 list-disc list-inside space-y-0.5">
            {flags.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      {notes.length > 0 && (
        <div className="rounded border border-gray-700/40 bg-gray-900/40 p-2">
          <div className="text-xs font-medium text-gray-400 mb-1">
            Extraction notes
          </div>
          <ul className="text-xs text-gray-300/80 list-disc list-inside space-y-0.5">
            {notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function TimelineBody({ summary }: { summary: L1ClientSummary }) {
  const events = summary.timeline ?? [];
  if (events.length === 0) {
    return <EmptySectionMsg text="No timeline events extracted." />;
  }
  // Sort descending by date
  const sorted = [...events].sort((a, b) =>
    b.event_date.localeCompare(a.event_date),
  );
  return (
    <div className="space-y-1 text-sm">
      <div className="text-xs font-medium text-gray-400 mb-1">
        {events.length} extracted events
      </div>
      {sorted.slice(0, 8).map((e, i) => (
        <div
          key={i}
          className="border-l-2 border-amber-500/30 pl-2 py-1 text-xs"
        >
          <div className="flex items-center gap-2">
            <span className="text-amber-300 font-medium">{e.event_date}</span>
            <span className="text-gray-500">{e.event_type}</span>
          </div>
          <div className="text-gray-300 mt-0.5">{e.description}</div>
        </div>
      ))}
      {sorted.length > 8 && (
        <div className="text-xs text-gray-500">
          + {sorted.length - 8} more events…
        </div>
      )}
    </div>
  );
}

// ============================================================
// Atoms
// ============================================================

function KvRow({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string | null | undefined;
  highlight?: boolean;
}) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-xs text-gray-500 min-w-[110px]">{label}:</span>
      <span
        className={`text-xs ${highlight ? "text-yellow-300 font-medium" : "text-gray-200"}`}
      >
        {value}
      </span>
    </div>
  );
}

function EmptySectionMsg({ text }: { text: string }) {
  return <div className="text-xs text-gray-500 italic">{text}</div>;
}
