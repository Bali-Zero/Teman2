"use client";

import React from "react";
import {
  Globe,
  Plus,
  Calendar,
  Edit2,
  Trash2,
  Download,
  RefreshCw,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import { ALERT_COLORS } from "./constants";
import { extractDriveFileId, getDriveProxyUrl } from "./utils";
import {
  CellStack,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  LedgerSection,
  Numeral,
  StatePill,
  type PillTone,
} from "@/components/workspace/r19";
import { ValidityTrack } from "./ValidityTrack";

// Real `ClientDocument.status` -> the one status vocabulary. Not every
// document carries this field (intake vs. lifecycle status are different
// things), so an absent status renders a plain dash rather than a guess.
// "rejected" reads `wait` (muted, terminal) the same way ObligationsTable's
// STATUS_TONE does for its own `rejected` — no danger tone in this module.
const DOC_STATUS_TONE: Record<string, PillTone> = {
  verified: "ok",
  pending: "wait",
  received: "wait",
  rejected: "wait",
  expired: "wait",
};

/**
 * "Expired Xd ago" / "Expires today" / "⏰ Xd left" / "Xmo left" — the exact
 * wording the old per-card expiry chip used, extracted so the permit panel
 * and the legacy doc cards (Working Permit / Other, untouched by this PR)
 * share one label instead of drifting apart.
 */
function daysUntil(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86400000);
}

function expiryLabel(daysLeft: number): string {
  if (daysLeft < 0) return `Expired ${Math.abs(daysLeft)}d ago`;
  if (daysLeft === 0) return "Expires today";
  if (daysLeft <= 365) return `⏰ ${daysLeft}d left`;
  return `${Math.floor(daysLeft / 30)}mo left`;
}

/** Same eligibility check the old renewal button used — unchanged threshold. */
function isRenewable(doc: ClientDocument): boolean {
  if (!doc.expiry_date) return false;
  const daysLeft = daysUntil(doc.expiry_date);
  return (
    (daysLeft < 0 || daysLeft <= 90) &&
    (doc.document_type?.toLowerCase().includes("kitas") ||
      doc.document_type?.toLowerCase().includes("kitap") ||
      doc.document_type?.toLowerCase().includes("visa"))
  );
}

/**
 * Whether a visa-family document's expiry deserves the one kita warning
 * treatment. Restores the OLD chip's `alert_color` signal (server-driven,
 * independent of the date) alongside the date-math threshold, instead of
 * dropping it the way the first version of this panel silently did — a
 * "red"/"expired"/"yellow" `alert_color` is urgent even 91+ days out. The
 * server's `yellow` is a live signal same as `red`/`expired` (D-5's other
 * half; `constants.ts:20-22` routed it to a warning tone before this panel
 * existed). All three still route to the ONE `--state-warning` tone, never
 * the old per-bucket yellow/red hues (there is no fifth hue in this module).
 */
function isUrgent(doc: ClientDocument): boolean {
  if (
    doc.alert_color === "red" ||
    doc.alert_color === "expired" ||
    doc.alert_color === "yellow"
  )
    return true;
  if (!doc.expiry_date) return false;
  return daysUntil(doc.expiry_date) <= 90;
}

/** `.replace(/_/g, " ")` — the OLD card's normalisation, reused so the
 * permit panel and the history grid don't show a raw `e_voa`/`kitas_c317`. */
function formatDocType(type: string): string {
  return type.replace(/_/g, " ");
}

/** `permit_label` (resolved server-side from OCR/document_type, see
 * crm.types.ts) is the precise label when known; `document_type` stays the
 * fallback — never invent a label the backend found no evidence for. */
function permitDisplayLabel(doc: ClientDocument): string {
  return doc.permit_label || formatDocType(doc.document_type);
}

/** `permit_family_label` (e.g. "KITAS / ITAS — Limited Stay Permit") is a
 * secondary line — shown ONLY when it differs from the primary label (a
 * precise visa index like "E23 — Working KITAS" pushed the family down to
 * secondary; when no index was found the two strings are identical, and
 * showing the same text twice would just be noise). */
function permitFamilySecondaryLabel(doc: ClientDocument): string | undefined {
  const family = doc.permit_family_label;
  if (!family || family === permitDisplayLabel(doc)) return undefined;
  return family;
}

// A MERP (Multiple Exit Re-entry Permit) document. `document_type` is often
// the literal string "MERP" and never matches `isVisaFamilyDocument` above
// (it is not itself a stay permit) — before this resolver existed it fell
// into the generic "Other" bucket instead of riding along with the current
// permit it re-enters on.
const isMerpDocument = (
  d: Pick<ClientDocument, "document_type" | "permit_family">,
) =>
  d.permit_family === "merp" ||
  (d.document_type?.toLowerCase().includes("merp") ?? false);

/** Shared download handler — same proxy-download logic renderDocCard used. */
function downloadDocument(doc: ClientDocument) {
  const fileId = doc.google_drive_file_url
    ? extractDriveFileId(doc.google_drive_file_url)
    : null;
  if (!fileId) return;
  const link = document.createElement("a");
  link.href = `/api/documents/proxy/${fileId}`;
  link.download = doc.file_name || `${doc.document_type}.pdf`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// A document belongs to the "visa family" (current + previous-visa buckets):
// kitas, kitap, any visa (incl. e-visa), or a Visa on Arrival (incl. e-VOA).
// Single source of truth so the "current" and "history" matchers below
// cannot drift apart again — that drift is exactly what hid an unexpired
// VOA from "Actual Visa" while still surfacing it once expired.
export const isVisaFamilyDocument = (
  d: Pick<ClientDocument, "document_type">,
) => {
  const t = d.document_type?.toLowerCase() ?? "";
  return (
    t.includes("kitas") ||
    t.includes("kitap") ||
    t.includes("visa") || // also matches "e-visa" / "evisa"
    t.includes("voa") // also matches "e-voa" / "evoa"
  );
};

export function ImmigrationTab({
  clientId,
  documents,
  formatDate,
  onAddClick,
  onEditClick,
  onRefresh,
}: {
  clientId: number;
  documents: ClientDocument[];
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onEditClick: (doc: ClientDocument) => void;
  onRefresh: () => void;
}) {
  const router = useRouter();

  const handleDelete = (docId: number, fileName: string) => {
    toast(`Archive document "${fileName || "Document"}"?`, {
      action: {
        label: "Archive",
        onClick: async () => {
          try {
            await api.crm.deleteDocument(clientId, docId);
            toast.success("Document archived");
            onRefresh();
          } catch (err) {
            toast.error("Error", { description: (err as Error).message });
          }
        },
      },
      cancel: { label: "Cancel", onClick: () => toast.dismiss() },
    });
  };

  // Immigration docs: visas, permits, work authorizations — NO passports (shown in Overview)
  const isPassport = (d: ClientDocument) =>
    d.document_type?.toLowerCase().includes("passport");
  const immigrationDocs = documents.filter(
    (d) =>
      !isPassport(d) &&
      (d.document_category === "immigration" ||
        d.document_type?.toLowerCase().includes("kitas") ||
        d.document_type?.toLowerCase().includes("kitap") ||
        d.document_type?.toLowerCase().includes("visa") ||
        d.document_type?.toLowerCase().includes("permit") ||
        d.document_type?.toLowerCase().includes("imta") ||
        d.document_type?.toLowerCase().includes("rptka") ||
        d.document_type?.toLowerCase().includes("evisa") ||
        d.document_type?.toLowerCase().includes("voa")),
  );

  // Sort: most recent expiry first, then by type
  const sortedDocs = [...immigrationDocs].sort((a, b) => {
    if (a.expiry_date && b.expiry_date)
      return (
        new Date(b.expiry_date).getTime() - new Date(a.expiry_date).getTime()
      );
    if (a.expiry_date) return -1;
    return 1;
  });

  // Actual visa = most recent non-expired document in the visa family
  // (kitas/kitap/visa/e-visa/VOA/e-VOA — see isVisaFamilyDocument above)
  const now = new Date();
  const actualVisa = sortedDocs.find(
    (d) =>
      isVisaFamilyDocument(d) &&
      (!d.expiry_date ||
        new Date(d.expiry_date) > new Date(now.getTime() - 30 * 86400000)), // allow 30 days grace
  );

  // Previous visas = expired (or superseded) visa-family documents.
  // Excludes anything MERP-classified: a document whose stored document_type
  // is generic ("visa") but whose resolved permit_family is "merp" matches
  // BOTH isVisaFamilyDocument (via the "visa" substring) and isMerpDocument
  // — without this exclusion it rendered once here AND once in the MERP
  // chip row below (GUILT fixed 2026-09-21).
  const previousVisas = sortedDocs.filter(
    (d) => d !== actualVisa && isVisaFamilyDocument(d) && !isMerpDocument(d),
  );

  // Working permits
  const workingPermits = sortedDocs.filter(
    (d) =>
      d.document_type?.toLowerCase().includes("permit") ||
      d.document_type?.toLowerCase().includes("imta") ||
      d.document_type?.toLowerCase().includes("rptka"),
  );

  // MERP (re-entry permit) — tied to the current permit, never "Other".
  // Only pulled out of "Other" when there IS a current permit to tie it to;
  // with no actualVisa it stays in otherDocs rather than disappearing.
  const merpDocs = actualVisa
    ? sortedDocs.filter((d) => d !== actualVisa && isMerpDocument(d))
    : [];

  // Other immigration docs (not in above categories)
  const otherDocs = sortedDocs.filter(
    (d) =>
      d !== actualVisa &&
      !previousVisas.includes(d) &&
      !workingPermits.includes(d) &&
      !merpDocs.includes(d),
  );

  const renderDocCard = (doc: ClientDocument) => (
    <div key={doc.id} className="bz-product-panel overflow-hidden group">
      {doc.google_drive_file_url && (
        <div className="relative">
          <div
            className={`aspect-[3/2] overflow-hidden border-b bg-[var(--bz-base)] ${
              doc.alert_color === "expired" || doc.alert_color === "red"
                ? "border-[var(--state-warning)]/50"
                : doc.alert_color === "yellow"
                  ? "border-yellow-500/50"
                  : "border-[var(--bz-border)]"
            }`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={
                getDriveProxyUrl(doc.google_drive_file_url) ||
                doc.google_drive_file_url
              }
              alt={doc.document_type}
              className="w-full h-full object-contain"
              onError={(e) => {
                const img = e.target as HTMLImageElement;
                // Only attempt fallback once to prevent infinite error loop
                if (
                  !img.dataset.fallbackAttempted &&
                  doc.google_drive_file_url
                ) {
                  img.dataset.fallbackAttempted = "true";
                  img.src = doc.google_drive_file_url.replace(
                    "/view",
                    "/preview",
                  );
                } else {
                  img.style.display = "none";
                }
              }}
            />
          </div>
        </div>
      )}
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="min-w-0">
            <span
              className={cn(
                "text-sm font-medium text-[var(--bz-text-1)]",
                // Capitalizing an official catalogue name mangles it (e.g.
                // "Cabang atau Anak" -> "Cabang Atau Anak") — only the raw
                // document_type fallback wants the transform.
                !doc.permit_label && "capitalize",
              )}
            >
              {permitDisplayLabel(doc)}
            </span>
            {permitFamilySecondaryLabel(doc) && (
              <p className="text-[11px] text-[var(--bz-text-2)]">
                {permitFamilySecondaryLabel(doc)}
              </p>
            )}
          </div>
          <div className="flex items-center gap-1 shrink-0">
            {doc.google_drive_file_url && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => downloadDocument(doc)}
              >
                <Download className="w-3 h-3" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={() => onEditClick(doc)}
            >
              <Edit2 className="w-3 h-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)] hover:bg-[var(--bz-card)] opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={() =>
                handleDelete(doc.id, doc.file_name || doc.document_type)
              }
              aria-label="Remove document"
              title="Remove document"
            >
              <Trash2 className="w-3 h-3" />
            </Button>
          </div>
        </div>
        {doc.file_name && (
          <p
            className="text-xs text-[var(--bz-text-2)] truncate mb-1"
            title={doc.file_name}
          >
            {doc.file_name}
          </p>
        )}
        {doc.expiry_date &&
          (() => {
            const daysLeft = daysUntil(doc.expiry_date);
            const isExpired = daysLeft < 0;
            const isCritical = !isExpired && daysLeft <= 30;
            const isWarning = !isExpired && daysLeft > 30 && daysLeft <= 90;
            const chipClass = isExpired
              ? "bg-[var(--state-warning)]/20 text-[var(--state-warning)]"
              : isCritical
                ? "bg-[var(--state-warning)]/15 text-[var(--state-warning)]"
                : isWarning
                  ? "bg-yellow-500/15 text-yellow-400"
                  : ALERT_COLORS[doc.alert_color || "green"];
            return (
              <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                <div
                  className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${chipClass}`}
                  title={`Expires: ${formatDate(doc.expiry_date)}`}
                >
                  <Calendar className="w-3 h-3" />
                  {expiryLabel(daysLeft)}
                </div>
                {isRenewable(doc) && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      router.push(
                        `/process/new?client_id=${clientId}&type=visa_renewal`,
                      );
                    }}
                    className="text-xs bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 px-2 py-1 rounded inline-flex items-center gap-1 transition-colors"
                  >
                    <RefreshCw className="w-3 h-3" />
                    Start Renewal
                  </button>
                )}
              </div>
            );
          })()}
        {doc.family_member_name && (
          <p className="text-xs text-[var(--bz-text-2)] mt-1">
            {doc.family_member_name}
          </p>
        )}
      </div>
    </div>
  );

  // Working Permit / Other keep the pre-R6 card grid unchanged — the current
  // permit and visa history got the restyle below; these two are out of this
  // PR's scope (see PR body).
  const sections = [
    {
      title: "Working Permit",
      docs: workingPermits,
      color: "bg-purple-500/20 text-purple-400",
    },
    {
      title: "Other",
      docs: otherDocs,
      color: "bg-[var(--state-warning)]/20 text-[var(--state-warning)]",
    },
  ];

  const expiryTone = actualVisa
    ? isUrgent(actualVisa)
      ? "text-[var(--state-warning)]"
      : "text-[var(--tx-pure)]"
    : "text-[var(--tx-secondary)]";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">
          Immigration
        </h3>
        <Button
          size="sm"
          variant="outline"
          className="gap-2 border-[var(--state-success)] bg-[var(--state-success)] text-white hover:bg-[var(--state-success)] hover:opacity-90"
          onClick={onAddClick}
        >
          <Plus className="w-4 h-4" />
          Add Document
        </Button>
      </div>

      {actualVisa && (
        <div className="rounded-lg border border-[var(--bz-border)] bg-[var(--bz-card)] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="mb-2 text-[10px] font-[650] uppercase tracking-[0.14em] text-[var(--tx-secondary)]">
                Current permit
              </p>
              <span
                className={cn(
                  "inline-flex items-center rounded-[6px] bg-[var(--tx-pure)] px-3 py-1.5 text-[19px] font-medium text-[var(--bz-base)]",
                  // Same rule as renderDocCard: capitalize only the raw
                  // document_type fallback, never an official catalogue name.
                  !actualVisa.permit_label && "capitalize",
                )}
                style={{ fontFamily: "var(--font-serif)" }}
              >
                {permitDisplayLabel(actualVisa)}
              </span>
              {permitFamilySecondaryLabel(actualVisa) && (
                <p className="mt-1 text-[12px] text-[var(--tx-secondary)]">
                  {permitFamilySecondaryLabel(actualVisa)}
                </p>
              )}
              {actualVisa.file_name && (
                <p
                  className="mt-1.5 max-w-[240px] truncate text-[12px] text-[var(--tx-secondary)]"
                  title={actualVisa.file_name}
                >
                  {actualVisa.file_name}
                </p>
              )}
            </div>
            <div className="flex items-center gap-1">
              {actualVisa.google_drive_file_url && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => downloadDocument(actualVisa)}
                  aria-label="Download current permit"
                >
                  <Download className="w-3 h-3" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => onEditClick(actualVisa)}
                aria-label="Edit current permit"
              >
                <Edit2 className="w-3 h-3" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]"
                onClick={() =>
                  handleDelete(
                    actualVisa.id,
                    actualVisa.file_name || actualVisa.document_type,
                  )
                }
                aria-label="Remove current permit"
                title="Remove current permit"
              >
                <Trash2 className="w-3 h-3" />
              </Button>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-end gap-7">
            {actualVisa.issue_date && (
              <div>
                <Numeral
                  n={Math.max(0, -daysUntil(actualVisa.issue_date))}
                  size="kpi"
                  tone="wait"
                  className="text-[var(--tx-pure)]"
                />
                <p className="mt-1.5 text-[11px] font-[650] uppercase tracking-[0.06em] text-[var(--tx-secondary)]">
                  Days on this permit
                </p>
              </div>
            )}
            {actualVisa.expiry_date &&
              (() => {
                const daysLeft = daysUntil(actualVisa.expiry_date);
                const pastExpiry = daysLeft < 0;
                return (
                  <div>
                    <Numeral
                      n={Math.abs(daysLeft)}
                      size="kpi"
                      tone="wait"
                      className={expiryTone}
                    />
                    <p className="mt-1.5 text-[11px] font-[650] uppercase tracking-[0.06em] text-[var(--tx-secondary)]">
                      {pastExpiry ? "Days past expiry" : "Days to expiry"}
                    </p>
                  </div>
                );
              })()}
          </div>

          {actualVisa.issue_date && actualVisa.expiry_date && (
            <ValidityTrack
              issueDate={actualVisa.issue_date}
              expiryDate={actualVisa.expiry_date}
            />
          )}

          <div className="mt-1 flex flex-wrap gap-5 text-[12.5px] text-[var(--tx-secondary)]">
            {actualVisa.issue_date && (
              <span>
                Issued{" "}
                <b className="font-semibold text-[var(--tx-pure)]">
                  {formatDate(actualVisa.issue_date)}
                </b>
              </span>
            )}
            {actualVisa.expiry_date && (
              <span>
                Expires{" "}
                <b className={cn("font-semibold", expiryTone)}>
                  {formatDate(actualVisa.expiry_date)} ·{" "}
                  {expiryLabel(daysUntil(actualVisa.expiry_date))}
                </b>
              </span>
            )}
            {actualVisa.permit_number && (
              <span>
                Permit no.{" "}
                <b className="font-semibold text-[var(--tx-pure)]">
                  {actualVisa.permit_number}
                </b>
              </span>
            )}
            {actualVisa.permit_sponsor && (
              <span>
                Sponsor{" "}
                <b className="font-semibold text-[var(--tx-pure)]">
                  {actualVisa.permit_sponsor}
                </b>
              </span>
            )}
            {actualVisa.family_member_name && (
              <span>
                For{" "}
                <b className="font-semibold text-[var(--tx-pure)]">
                  {actualVisa.family_member_name}
                </b>
              </span>
            )}
          </div>

          {merpDocs.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {merpDocs.map((doc) => (
                <span
                  key={doc.id}
                  className="inline-flex items-center gap-1.5 rounded-[6px] border border-[var(--bz-border)] bg-[var(--bz-base)] px-2.5 py-1 text-[12px] text-[var(--tx-secondary)]"
                >
                  <RefreshCw className="w-3 h-3" />
                  {permitDisplayLabel(doc)}
                  {doc.expiry_date && ` · Exp ${formatDate(doc.expiry_date)}`}
                </span>
              ))}
            </div>
          )}

          {isRenewable(actualVisa) && (
            <Button
              variant="outline"
              size="sm"
              className="mt-3 gap-1.5 shadow-none"
              onClick={(e) => {
                e.stopPropagation();
                router.push(
                  `/process/new?client_id=${clientId}&type=visa_renewal`,
                );
              }}
            >
              <RefreshCw className="w-3 h-3" />
              Start Renewal
            </Button>
          )}
        </div>
      )}

      {previousVisas.length > 0 && (
        <LedgerSection
          n={1}
          title="Visa history"
          actions={
            <span className="text-[13px] text-[var(--tx-secondary)]">
              ({previousVisas.length})
            </span>
          }
        >
          <HairlineGrid
            cols="1.6fr 1fr 1fr 1fr 140px"
            colsCollapsed="1.6fr 1fr 1fr 140px"
            id="immigration-visa-history"
            // `colsCollapsed`'s own scoped style sets `--cols` under a media
            // query, but an inline `--cols` on the very same element already
            // wins over it (PR 6520, not this window's to fix — see
            // DocumentsTab.tsx:41-49, FamilyTab.tsx:444 and
            // ObligationsTable.tsx ~475-493, which document and route around
            // the same defect). Its `[data-collapse]{display:none}` half
            // does apply, so the "Issued" cells still leave the flow; only
            // the track count needed the same technique those three
            // siblings use: override `grid-template-columns` directly on
            // the `.grid` descendant, scoped and `!important`, at the same
            // 1360px breakpoint `colsCollapsed` was already targeting.
            //
            // Below 640px (`max-sm`) Status and Expires leave the grid the
            // same way, on top of the 1360px step above — their content
            // relocates onto the first cell's own secondary block instead,
            // the same technique DocumentsTab.tsx uses (PR 6889), narrowing
            // the row to Visa type + Actions on a phone width.
            className="max-[1360px]:[&_.grid]:!grid-cols-[1.6fr_1fr_1fr_140px] max-sm:[&_.grid]:!grid-cols-[minmax(0,1fr)_auto]"
          >
            <HairlineHead>
              <span>Visa type</span>
              <span className="max-sm:hidden">Status</span>
              <span data-collapse>Issued</span>
              <span className="max-sm:hidden">Expires</span>
              <span className="sr-only">Actions</span>
            </HairlineHead>
            <HairlineBody>
              {previousVisas.map((doc) => {
                const urgent = isUrgent(doc);
                const secondary = [
                  permitFamilySecondaryLabel(doc),
                  doc.file_name,
                  doc.family_member_name,
                ]
                  .filter(Boolean)
                  .join(" · ");
                const statusNode = doc.status ? (
                  <StatePill
                    tone={DOC_STATUS_TONE[doc.status] ?? "wait"}
                    label={doc.status}
                  />
                ) : (
                  "—"
                );
                const expiresText = doc.expiry_date
                  ? `${formatDate(doc.expiry_date)} · ${expiryLabel(
                      daysUntil(doc.expiry_date),
                    )}`
                  : "—";
                return (
                  <HairlineRow key={doc.id}>
                    <div className="min-w-0 px-2.5">
                      <CellStack
                        primary={permitDisplayLabel(doc)}
                        secondary={secondary || undefined}
                        collapsed={
                          doc.issue_date
                            ? `Issued ${formatDate(doc.issue_date)}`
                            : undefined
                        }
                      />
                      <span className="mt-1 flex flex-col gap-0.5 text-[11px] text-[var(--tx-secondary)] sm:hidden">
                        {statusNode}
                        <span
                          className={cn(
                            urgent &&
                              "font-semibold text-[var(--state-warning)]",
                          )}
                        >
                          {expiresText}
                        </span>
                      </span>
                    </div>
                    <span className="max-sm:hidden">{statusNode}</span>
                    <span data-collapse>
                      {doc.issue_date ? formatDate(doc.issue_date) : "—"}
                    </span>
                    <span
                      className={cn(
                        urgent && "font-semibold text-[var(--state-warning)]",
                        "max-sm:hidden",
                      )}
                    >
                      {expiresText}
                    </span>
                    <div className="flex items-center justify-end gap-0.5 px-2.5">
                      {isRenewable(doc) && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() =>
                            router.push(
                              `/process/new?client_id=${clientId}&type=visa_renewal`,
                            )
                          }
                          aria-label={`Start renewal for ${doc.document_type}`}
                          title="Start Renewal"
                        >
                          <RefreshCw className="w-3 h-3" />
                        </Button>
                      )}
                      {doc.google_drive_file_url && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => downloadDocument(doc)}
                          aria-label={`Download ${doc.document_type}`}
                        >
                          <Download className="w-3 h-3" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => onEditClick(doc)}
                        aria-label={`Edit ${doc.document_type}`}
                      >
                        <Edit2 className="w-3 h-3" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() =>
                          handleDelete(
                            doc.id,
                            doc.file_name || doc.document_type,
                          )
                        }
                        aria-label={`Remove ${doc.document_type}`}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </HairlineRow>
                );
              })}
            </HairlineBody>
          </HairlineGrid>
        </LedgerSection>
      )}

      {immigrationDocs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--bz-border)] bg-[var(--bz-card)] p-12 text-center shadow-[var(--bz-shadow-card)]">
          <Globe className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
          <p className="text-[var(--bz-text-2)]">
            No immigration documents yet
          </p>
          <p className="text-sm text-[var(--bz-text-2)] mt-1">
            Upload KITAS, visa, or working permit documents
          </p>
        </div>
      ) : (
        sections.map(({ title, docs: sectionDocs, color }) => {
          if (sectionDocs.length === 0) return null;
          return (
            <div key={title} className="space-y-3">
              <h4 className="font-medium text-[var(--bz-text-1)] flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${color}`}>
                  {title}
                </span>
                <span className="text-[var(--bz-text-2)]">
                  ({sectionDocs.length})
                </span>
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {sectionDocs.map(renderDocCard)}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
