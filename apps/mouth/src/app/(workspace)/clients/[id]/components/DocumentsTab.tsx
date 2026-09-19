"use client";

import React, { useMemo, useState } from "react";
import { Eye, Pencil, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ClientDocument } from "@/lib/api/crm/crm.types";
import {
  CellStack,
  DeskStrip,
  EmptyState,
  FOCUS,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  StatePill,
  TABULAR,
  type PillTone,
} from "@/components/workspace/r19";
import { getDocumentOpenUrl } from "./utils";

const CATEGORY_ORDER = [
  "immigration",
  "pma",
  "tax",
  "personal",
  "family",
  "other",
];

const CATEGORY_LABELS: Record<string, string> = {
  immigration: "Immigration",
  pma: "Company",
  tax: "Tax",
  personal: "Personal",
  family: "Family",
  other: "Other",
};

/**
 * The grid's column order, desktop width. Below 640px the two hidden columns
 * (Status, Expires) leave the grid — their content relocates onto Document's
 * own secondary line — and the row narrows to Document + Actions, mirroring
 * the same override `ObligationsTable.tsx` uses: `HairlineGrid`'s native
 * `colsCollapsed`+`id` scoped style is inert against the inline `--cols` it
 * sets on the very element it targets (#6520, not this window's to fix), so
 * the override targets the rows/head directly instead of the variable.
 */
const COLS = "minmax(180px,1.7fr) 104px 100px 92px";

/**
 * Real-fields-only status: `deleted_at` (client removed it), `expiry_date`
 * (a date, checked before status), then `status` itself. No field is
 * invented — a document with none of these renders `wait`/"Missing".
 */
function documentPillState(d: ClientDocument): {
  tone: PillTone;
  label: string;
} {
  if (d.deleted_at) return { tone: "wait", label: "Removed" };
  if (d.expiry_date) {
    const daysLeft = Math.ceil(
      (new Date(d.expiry_date).getTime() - Date.now()) / 86400000,
    );
    if (daysLeft < 0) return { tone: "you", label: "Expired" };
    if (daysLeft <= 30) return { tone: "you", label: "Expiring" };
  }
  if (d.status === "verified") return { tone: "ok", label: "Valid" };
  if (d.status === "received") return { tone: "ours", label: "Processing" };
  if (d.status === "rejected") return { tone: "wait", label: "Rejected" };
  return { tone: "wait", label: "Missing" };
}

/** Nearest expiry first; documents without one sort last. */
function byExpiryUrgency(a: ClientDocument, b: ClientDocument): number {
  const rank = (d: ClientDocument) =>
    d.expiry_date
      ? new Date(d.expiry_date).getTime()
      : Number.POSITIVE_INFINITY;
  return rank(a) - rank(b);
}

export function DocumentsTab({
  clientId,
  documents,
  documentsByCategory,
  formatDate,
  onAddClick,
  onEditClick,
}: {
  clientId: number;
  documents: ClientDocument[];
  documentsByCategory: Record<string, ClientDocument[]>;
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onEditClick: (doc: ClientDocument) => void;
}) {
  const [activeCategory, setActiveCategory] = useState<string>("all");

  const sortedCategories = useMemo(
    () =>
      Object.keys(documentsByCategory).sort(
        (a, b) => CATEGORY_ORDER.indexOf(a) - CATEGORY_ORDER.indexOf(b),
      ),
    [documentsByCategory],
  );

  // Reverse lookup so a flat ("All") row still knows its own category —
  // `documentsByCategory` is the single source of truth for that grouping,
  // never `doc.document_category` alone (a doc can be bucketed under "other"
  // without that field set).
  const categoryByDocId = useMemo(() => {
    const map = new Map<number, string>();
    for (const [cat, docs] of Object.entries(documentsByCategory)) {
      for (const d of docs) map.set(d.id, cat);
    }
    return map;
  }, [documentsByCategory]);

  const filteredDocuments = useMemo(() => {
    const base =
      activeCategory === "all"
        ? documents
        : (documentsByCategory[activeCategory] ?? []);
    return [...base].sort(byExpiryUrgency);
  }, [activeCategory, documents, documentsByCategory]);

  if (documents.length === 0) {
    return (
      <EmptyState
        action={
          <Button
            size="sm"
            variant="outline"
            onClick={onAddClick}
            className="gap-2"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add document
          </Button>
        }
      >
        No documents on file yet.
      </EmptyState>
    );
  }

  return (
    <div data-client-id={clientId}>
      <DeskStrip
        count={filteredDocuments.length}
        countLabel="Documents"
        filters={
          <>
            <StatePill
              tone="wait"
              label="All"
              pressed={activeCategory === "all"}
              onClick={() => setActiveCategory("all")}
            />
            {sortedCategories.map((cat) => (
              <StatePill
                key={cat}
                tone="wait"
                label={CATEGORY_LABELS[cat] || cat}
                pressed={activeCategory === cat}
                onClick={() => setActiveCategory(cat)}
              />
            ))}
          </>
        }
        right={
          <Button
            size="sm"
            variant="outline"
            onClick={onAddClick}
            className="gap-2"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Add document
          </Button>
        }
        className="mb-2"
      />

      <HairlineGrid
        cols={COLS}
        className="max-sm:[&_.grid]:!grid-cols-[minmax(0,1fr)_auto]"
      >
        <HairlineHead>
          <span>Document</span>
          <span className="max-sm:hidden">Status</span>
          <span className="max-sm:hidden">Expires</span>
          <span aria-hidden="true" />
        </HairlineHead>
        <HairlineBody>
          {filteredDocuments.map((d) => {
            const cat =
              categoryByDocId.get(d.id) ?? d.document_category ?? "other";
            const catLabel = CATEGORY_LABELS[cat] || cat;
            const displayName = d.file_name || d.document_type;
            const openUrl = getDocumentOpenUrl(d);
            const { tone, label } = documentPillState(d);
            const expiresLabel = d.expiry_date
              ? formatDate(d.expiry_date)
              : "—";
            const uploadedLabel = d.created_at
              ? formatDate(d.created_at)
              : undefined;

            return (
              <HairlineRow key={d.id}>
                <div className="min-w-0 px-2.5">
                  <CellStack
                    primary={
                      openUrl ? (
                        <a
                          href={openUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label={`Open ${displayName}`}
                          className={cn("rounded hover:underline", FOCUS)}
                        >
                          {displayName}
                        </a>
                      ) : (
                        displayName
                      )
                    }
                    secondary={
                      uploadedLabel
                        ? `${catLabel} · ${uploadedLabel}`
                        : catLabel
                    }
                  />
                  <span className="mt-1 flex flex-col gap-0.5 text-[11px] text-[var(--tx-secondary)] sm:hidden">
                    <StatePill tone={tone} label={label} />
                    <span style={TABULAR}>Expires {expiresLabel}</span>
                  </span>
                </div>

                <span className="max-sm:hidden">
                  <StatePill tone={tone} label={label} />
                </span>

                <span
                  className="max-sm:hidden text-[var(--tx-pure)]"
                  style={TABULAR}
                >
                  {expiresLabel}
                </span>

                <div className="flex items-center justify-end gap-1 px-2.5">
                  {openUrl ? (
                    <a
                      href={openUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`View ${displayName}`}
                      className={cn(
                        "inline-flex h-7 w-7 items-center justify-center border border-transparent text-[var(--tx-secondary)] hover:border-[var(--line-control)] hover:text-[var(--tx-pure)]",
                        FOCUS,
                      )}
                    >
                      <Eye className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                  ) : (
                    <span
                      className="text-[10px] leading-tight text-[var(--tx-secondary)]"
                      title="File tidak tersedia"
                    >
                      File tidak tersedia
                    </span>
                  )}
                  <button
                    type="button"
                    aria-label={`Edit ${displayName}`}
                    onClick={() => onEditClick(d)}
                    className={cn(
                      "inline-flex h-7 w-7 items-center justify-center border border-transparent text-[var(--tx-secondary)] hover:border-[var(--line-control)] hover:text-[var(--tx-pure)]",
                      FOCUS,
                    )}
                  >
                    <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                  </button>
                </div>
              </HairlineRow>
            );
          })}
        </HairlineBody>
      </HairlineGrid>
    </div>
  );
}
