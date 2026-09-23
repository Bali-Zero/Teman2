"use client";

import React, { useState } from "react";
import {
  User,
  Edit2,
  FileText,
  Phone,
  Clock,
  Activity,
  Copy,
  Check,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type {
  ClientProfile,
  ClientDocument,
  ExpiryAlert,
} from "@/lib/api/crm/crm.types";
import { formatPhoneNumber, isBirthdayToday } from "./utils";
import { PassportCard } from "./PassportCard";
import { VisaCard } from "./VisaCard";
import { AiSummaryCard } from "./AiSummaryCard";
import { OracleChat } from "./OracleChat";
import { WaCaseIntelligencePanel } from "./WaCaseIntelligencePanel";
import {
  LedgerSection,
  NumberedList,
  StatePill,
} from "@/components/workspace/r19";
import { passportLabel } from "../../client-row-model";

/** "kitas_card" -> "Kitas Card" — formatting only, never invents a value. */
function documentTypeLabel(documentType: string): string {
  return documentType
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Expired-vs-expiring wording mirrors the strip this ledger sits above
 * (ClientDetailClient.tsx ~682-760): only `expired`/`red` alerts are urgent
 * enough to need attention, expired sorts first, then soonest expiry.
 */
function urgentAlerts(alerts: ExpiryAlert[]): ExpiryAlert[] {
  return alerts
    .filter((a) => a.alert_color === "expired" || a.alert_color === "red")
    .slice()
    .sort((a, b) => {
      if (a.alert_color !== b.alert_color) {
        return a.alert_color === "expired" ? -1 : 1;
      }
      return a.days_until_expiry - b.days_until_expiry;
    });
}

const ATTENTION_ROW_CAP = 5;

export function OverviewTab({
  client,
  stats,
  documents,
  activePractices,
  completedPractices,
  expiryAlerts,
  needsViewerAction,
  formatDate,
  formatCurrency,
  onEditClick,
  onDeleteClick,
  canDeleteClient,
  isDeletingClient,
  onRefresh,
  clientId,
}: {
  client: ClientProfile["client"];
  stats: ClientProfile["stats"];
  documents: ClientDocument[];
  activePractices: ClientProfile["practices"];
  completedPractices: ClientProfile["practices"];
  /** Real `expiry_alerts` from the profile — the only source for the
   *  "Needs attention" ledger. Practices carry no waiting-on/next-actor
   *  field today, so this ledger cannot include them (2026-09-19). */
  expiryAlerts: ClientProfile["expiry_alerts"];
  /** Same ownership predicate the masthead subtitle already uses
   *  (ClientDetailClient.tsx `needsViewerAction`) — copper is never
   *  derived a second way. */
  needsViewerAction: boolean;
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  onEditClick: () => void;
  /** Opens the soft-delete confirmation. Only reachable when
   *  `canDeleteClient` is true — the parent owns both. */
  onDeleteClick: () => void;
  /** `viewerCanDeleteClient(client, viewerEmail, viewerRole)` as computed by the
   *  parent. FALSE while the viewer is still unknown, so the button never
   *  appears on a guess (same law as the copper stamp). */
  canDeleteClient: boolean;
  isDeletingClient: boolean;
  onRefresh: () => Promise<void>;
  clientId: number;
}) {
  const isClientBirthday = isBirthdayToday(client.date_of_birth);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [showAllAttention, setShowAllAttention] = useState(false);

  const attentionRows = urgentAlerts(expiryAlerts);
  const visibleAttentionRows = showAllAttention
    ? attentionRows
    : attentionRows.slice(0, ATTENTION_ROW_CAP);

  const copyToClipboard = (value: string, field: string) => {
    void navigator.clipboard.writeText(value).then(() => {
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    });
  };

  return (
    <div className="space-y-6">
      {/* Needs attention — real expiry_alerts only, zero rows renders nothing */}
      {attentionRows.length > 0 && (
        <LedgerSection
          n={1}
          tone={needsViewerAction ? "you" : "wait"}
          title="Needs attention"
        >
          <div className="py-3">
            <NumberedList
              owned={needsViewerAction}
              items={visibleAttentionRows.map((alert) => ({
                id: `${alert.entity_type}-${alert.entity_id}-${alert.document_type}`,
                title: `${documentTypeLabel(alert.document_type)} ${
                  alert.alert_color === "expired" ? "expired" : "expires soon"
                }`,
                detail:
                  alert.entity_type === "family_member"
                    ? `${passportLabel(alert.days_until_expiry)} · ${alert.entity_name}`
                    : passportLabel(alert.days_until_expiry),
                right: (
                  <StatePill
                    tone={needsViewerAction ? "you" : "wait"}
                    label={needsViewerAction ? "You" : "Wait"}
                  />
                ),
              }))}
            />
            {attentionRows.length > ATTENTION_ROW_CAP && !showAllAttention && (
              <button
                type="button"
                onClick={() => setShowAllAttention(true)}
                className="mt-2 min-h-6 text-xs text-[var(--tx-secondary)] underline decoration-dotted hover:text-[var(--tx-pure)]"
              >
                Show all ({attentionRows.length})
              </button>
            )}
          </div>
        </LedgerSection>
      )}
      {/* AI Summary (CRM-Guardian Phase 1 cross-folder L1) */}
      <AiSummaryCard clientId={clientId} section="overview" />
      {/* Oracle Chat — NLM-powered Q&A */}
      <OracleChat clientId={clientId} />
      {/* WhatsApp Case Intelligence — GPT-5.5 case cards linked to this CRM profile */}
      <WaCaseIntelligencePanel clientId={clientId} />
      {/* 3 Columns Layout - Team Member | Passport | Visa */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-stretch">
        {/* COLUMN 1: Client Info */}
        <div className="flex flex-col h-full">
          {/* Client Info Card */}
          <div
            className="bz-product-panel bz-product-panel--interactive transition-all duration-300 overflow-hidden flex-1 flex flex-col h-full hover:-translate-y-1"
            style={{
              borderColor: isClientBirthday
                ? "color-mix(in srgb, var(--state-warning) 40%, transparent)"
                : undefined,
              background: isClientBirthday
                ? "color-mix(in srgb, var(--state-warning) 10%, var(--bz-card))"
                : undefined,
              boxShadow: isClientBirthday
                ? "0 0 24px color-mix(in srgb, var(--state-warning) 15%, transparent), var(--bz-shadow-card)"
                : undefined,
            }}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--bz-border)]">
              <h3 className="font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
                Client Info
                {isClientBirthday && (
                  <span
                    className="text-base"
                    title="Birthday today!"
                    aria-label="Birthday today!"
                  >
                    🎂
                  </span>
                )}
              </h3>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0"
                  onClick={onEditClick}
                  aria-label="Edit client info"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </Button>
                {canDeleteClient && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 w-7 p-0 text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]"
                    onClick={onDeleteClick}
                    disabled={isDeletingClient}
                    aria-label="Delete client"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                )}
              </div>
            </div>
            <div className="p-4 space-y-4 flex-1">
              {/* Full Name */}
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-[var(--bz-card)] flex items-center justify-center">
                  <User className="w-4 h-4 text-[var(--tx-secondary)]" />
                </div>
                <div className="flex-1">
                  <p className="text-xs text-[var(--bz-text-2)]">Full Name</p>
                  <p className="text-base font-semibold">{client.full_name}</p>
                </div>
              </div>

              <div className="border-t border-[var(--bz-border)]" />

              {/* Contact Info */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Email
                  </p>
                  <div className="flex items-center gap-1.5 group/copy">
                    <p className="text-sm font-medium truncate">
                      {client.email || (
                        <span className="text-[var(--bz-text-2)] italic text-xs">
                          Not provided
                        </span>
                      )}
                    </p>
                    {client.email && (
                      <button
                        onClick={() => copyToClipboard(client.email!, "email")}
                        className="opacity-0 group-hover/copy:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--bz-card)]"
                        title="Copy email"
                        aria-label="Copy email"
                      >
                        {copiedField === "email" ? (
                          <Check className="w-3 h-3 text-green-400" />
                        ) : (
                          <Copy className="w-3 h-3 text-[var(--bz-text-2)]" />
                        )}
                      </button>
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Phone
                  </p>
                  <div className="flex items-center gap-1.5 group/copy">
                    <p className="text-sm font-medium">
                      {client.phone ? (
                        formatPhoneNumber(client.phone)
                      ) : (
                        <span className="text-[var(--bz-text-2)] italic text-xs">
                          Not provided
                        </span>
                      )}
                    </p>
                    {client.phone && (
                      <button
                        onClick={() => copyToClipboard(client.phone!, "phone")}
                        className="opacity-0 group-hover/copy:opacity-100 transition-opacity p-0.5 rounded hover:bg-[var(--bz-card)]"
                        title="Copy phone"
                        aria-label="Copy phone"
                      >
                        {copiedField === "phone" ? (
                          <Check className="w-3 h-3 text-green-400" />
                        ) : (
                          <Copy className="w-3 h-3 text-[var(--bz-text-2)]" />
                        )}
                      </button>
                    )}
                  </div>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Nationality
                  </p>
                  <p className="text-sm font-medium">
                    {client.nationality || (
                      <span className="text-[var(--bz-text-2)] italic text-xs">
                        —
                      </span>
                    )}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                    Gender
                  </p>
                  <p className="text-sm font-medium">
                    {client.gender === "M" ? (
                      "Male"
                    ) : client.gender === "F" ? (
                      "Female"
                    ) : (
                      <span className="text-[var(--bz-text-2)] italic text-xs">
                        —
                      </span>
                    )}
                  </p>
                </div>
              </div>

              {/* Birthplace — not shown on PassportCard (which already
                  covers passport number/expiry and date of birth) */}
              {client.birthplace && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3">
                    <div>
                      <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                        Birthplace
                      </p>
                      <p className="text-sm font-medium">{client.birthplace}</p>
                    </div>
                  </div>
                </>
              )}

              {/* Address */}
              <div className="border-t border-[var(--bz-border)]" />
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)]">
                  Address
                </p>
                <p className="text-sm font-medium">
                  {client.address || (
                    <span className="text-[var(--bz-text-2)] italic text-xs">
                      Not provided
                    </span>
                  )}
                </p>
              </div>

              {/* Strategic Recap — primary intelligent auto-summary (bold + distinct) */}
              {(client as any).strategic_recap && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div
                    className="rounded-lg p-4 -mx-1"
                    style={{
                      background: "var(--bz-card)",
                      border: "1px solid var(--bz-border)",
                    }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-[11px] uppercase tracking-[0.15em] font-semibold text-[var(--tx-secondary)] flex items-center gap-1.5">
                        <span>◆</span>
                        Strategic recap
                      </p>
                      {(client as any).strategic_recap_source && (
                        <span className="text-[9px] uppercase tracking-wider opacity-60 font-mono">
                          {(client as any).strategic_recap_source.replace(
                            "_",
                            " ",
                          )}
                        </span>
                      )}
                    </div>
                    <p
                      className="font-bold leading-[1.55] whitespace-pre-line text-[var(--bz-text-1)]"
                      style={{ fontSize: "0.97rem" }}
                    >
                      {(client as any).strategic_recap}
                    </p>
                  </div>
                </>
              )}

              {/* Notes — machine log, collapsed by default */}
              {client.notes && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <details className="text-xs">
                    <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)]">
                      Audit log ({client.notes.length} chars)
                    </summary>
                    <p className="text-xs text-[var(--bz-text-2)] leading-relaxed whitespace-pre-line mt-2 max-h-64 overflow-y-auto font-mono opacity-70">
                      {client.notes}
                    </p>
                  </details>
                </>
              )}

              {/* Quick Actions — WhatsApp/Email dropped: the page header already
                  offers both for this client. Call (tel:) is kept: it's not
                  offered anywhere else on this page. */}
              {client.phone && (
                <>
                  <div className="border-t border-[var(--bz-border)]" />
                  <div className="flex items-center gap-2">
                    <a
                      href={`tel:${client.phone}`}
                      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all"
                      style={{
                        background:
                          "color-mix(in srgb, var(--state-info) 12%, transparent)",
                        color: "var(--state-info)",
                        border:
                          "1px solid color-mix(in srgb, var(--state-info) 25%, transparent)",
                      }}
                      title={`Call ${client.phone}`}
                    >
                      <Phone className="w-3.5 h-3.5" />
                      Call
                    </a>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Stats Row */}
          {(() => {
            // Coerce with Number(): BE serializes numeric(15,2) as string.
            const amountOf = (p: (typeof activePractices)[number]) =>
              Number(p.actual_price ?? p.quoted_price ?? 0);
            const pipelineValue = activePractices.reduce(
              (sum, p) => sum + amountOf(p),
              0,
            );
            const unpaidValue = [...activePractices, ...completedPractices]
              .filter(
                (p) =>
                  p.payment_status === "unpaid" ||
                  p.payment_status === "partial",
              )
              .reduce((sum, p) => sum + amountOf(p), 0);
            return (
              <div className="grid grid-cols-2 gap-3 mt-4">
                {/* Family tile dropped — the Family tab label already shows
                    `Family (${stats.family_count})`, same source value. */}
                <div className="bz-product-panel bz-product-panel--interactive p-3 transition-all duration-300 hover:-translate-y-1">
                  <div className="flex items-center gap-1.5 mb-1">
                    <FileText className="w-3.5 h-3.5 text-purple-500" />
                    <span className="text-[10px] text-[var(--bz-text-2)]">
                      Docs
                    </span>
                  </div>
                  <p className="text-lg font-bold">{stats.documents_count}</p>
                </div>
                {pipelineValue > 0 && (
                  <div className="bz-product-panel bz-product-panel--interactive p-3 transition-all duration-300 hover:-translate-y-1">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Activity className="w-3.5 h-3.5 text-yellow-500" />
                      <span className="text-[10px] text-[var(--bz-text-2)]">
                        Pipeline
                      </span>
                    </div>
                    <p className="text-sm font-bold text-[var(--state-warning)] truncate">
                      {formatCurrency(pipelineValue)}
                    </p>
                  </div>
                )}
                {unpaidValue > 0 && (
                  <div
                    className="bz-product-panel bz-product-panel--interactive p-3 transition-all duration-300 hover:-translate-y-1"
                    style={{
                      borderColor:
                        "color-mix(in srgb, var(--state-warning) 22%, transparent)",
                    }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <Clock className="w-3.5 h-3.5 text-[var(--state-warning)]" />
                      <span className="text-[10px] text-[var(--bz-text-2)]">
                        Unpaid
                      </span>
                    </div>
                    <p className="text-sm font-bold text-[var(--state-warning)] truncate">
                      {formatCurrency(unpaidValue)}
                    </p>
                  </div>
                )}
              </div>
            );
          })()}
        </div>

        {/* COLUMN 2: Passport */}
        <div className="flex flex-col h-full">
          <PassportCard
            client={client}
            documents={documents}
            formatDate={formatDate}
            onRefresh={onRefresh}
            clientId={clientId}
          />
        </div>

        {/* COLUMN 3: Visa */}
        <div className="flex flex-col h-full">
          <VisaCard
            client={client}
            documents={documents}
            activePractices={activePractices}
            formatDate={formatDate}
            formatCurrency={formatCurrency}
            onRefresh={onRefresh}
            clientId={clientId}
          />
        </div>
      </div>
    </div>
  );
}
