"use client";
import { useState } from "react";
import {
  FileText,
  Image as ImgIcon,
  File as FileIcon,
  Download,
  Trash2,
  Undo2,
} from "lucide-react";
import type { VaultFile } from "@/lib/schemas/vault";

function iconFor(type: string) {
  const t = type.toLowerCase();
  if (t.includes("pdf") || t.includes("document")) return FileText;
  if (
    t.includes("image") ||
    t.includes("photo") ||
    t.includes("jpg") ||
    t.includes("png")
  )
    return ImgIcon;
  return FileIcon;
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

interface Props {
  files: VaultFile[];
  onDownload?: (file: VaultFile) => void;
  /** FASE 5 — soft-delete a document (recoverable). */
  onDelete?: (file: VaultFile) => void | Promise<unknown>;
  /** FASE 5 — restore a just-removed document (undo). */
  onRestore?: (file: VaultFile) => void | Promise<unknown>;
  /** id currently mid-action (for disabling the row's buttons). */
  pendingId?: number | null;
}

export function VaultFileGrid({
  files,
  onDownload,
  onDelete,
  onRestore,
  pendingId,
}: Props) {
  // Track ids removed in THIS session so we can offer a transient "Undo".
  // The SWR list drops the row on revalidation; we keep a local undo card.
  const [undoable, setUndoable] = useState<Record<number, VaultFile>>({});

  if (files.length === 0 && Object.keys(undoable).length === 0) {
    return (
      <p
        className="text-sm py-8 text-center"
        style={{ color: "var(--bz-text-2)" }}
      >
        No files in this view.
      </p>
    );
  }

  const handleDelete = async (f: VaultFile) => {
    if (!onDelete) return;
    await onDelete(f);
    setUndoable((prev) => ({ ...prev, [f.id]: f }));
  };

  const handleRestore = async (f: VaultFile) => {
    if (onRestore) await onRestore(f);
    setUndoable((prev) => {
      const next = { ...prev };
      delete next[f.id];
      return next;
    });
  };

  return (
    <div className="space-y-3">
      {Object.values(undoable).length > 0 && (
        <ul aria-label="Recently removed" className="space-y-2">
          {Object.values(undoable).map((f) => (
            <li
              key={`undo-${f.id}`}
              className="flex items-center justify-between gap-3 p-3 rounded-lg border text-xs"
              style={{
                background: "var(--bz-card)",
                borderColor:
                  "color-mix(in srgb, var(--bz-copper) 35%, transparent)",
                color: "var(--bz-text-1)",
              }}
            >
              <span className="truncate">
                Removed <strong>{f.name}</strong>. Recoverable for 30 days.
              </span>
              {onRestore && (
                <button
                  onClick={() => handleRestore(f)}
                  disabled={pendingId === f.id}
                  className="shrink-0 text-[11px] uppercase tracking-[2px] hover:underline inline-flex items-center gap-1 disabled:opacity-50"
                  style={{
                    color: "var(--bz-copper-text, var(--tx-secondary))",
                  }}
                >
                  <Undo2 aria-hidden className="w-3 h-3" /> Undo
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <ul
        aria-label="Vault files"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
      >
        {files.map((f) => {
          const Icon = iconFor(f.type);
          return (
            <li
              key={f.id}
              className="p-3 rounded-lg border flex flex-col gap-2 transition-colors"
              style={{
                background: "var(--bz-card)",
                borderColor: "var(--bz-border)",
                boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.borderColor = "var(--bz-border-hover)")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.borderColor = "var(--bz-border)")
              }
            >
              <div className="flex items-start gap-2">
                <Icon
                  aria-hidden
                  className="w-8 h-8 shrink-0"
                  style={{ color: "var(--bz-copper)" }}
                />
                <div className="min-w-0 flex-1">
                  <p
                    className="text-xs truncate"
                    title={f.name}
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    {f.name}
                  </p>
                  <p
                    className="text-[10px] uppercase tracking-[2px] mt-1"
                    style={{
                      color: "var(--text-tertiary, var(--tx-tertiary))",
                    }}
                  >
                    {f.type}
                  </p>
                </div>
              </div>
              {f.purpose && (
                <p
                  className="text-[11px] italic line-clamp-2"
                  title={f.purpose}
                  style={{ color: "var(--bz-text-2)" }}
                >
                  “{f.purpose}”
                </p>
              )}
              <div
                className="flex items-center justify-between text-[10px]"
                style={{ color: "var(--text-tertiary, var(--tx-tertiary))" }}
              >
                <span>{formatDate(f.created_at)}</span>
                {f.size_kb != null && <span>{f.size_kb} KB</span>}
              </div>
              <div className="flex items-center justify-between gap-2">
                {f.downloadable && onDownload ? (
                  <button
                    onClick={() => onDownload(f)}
                    className="text-[11px] uppercase tracking-[2px] hover:underline inline-flex items-center gap-1"
                    style={{
                      color: "var(--bz-copper-text, var(--tx-secondary))",
                    }}
                  >
                    <Download aria-hidden className="w-3 h-3" /> Download
                  </button>
                ) : (
                  <span />
                )}
                {onDelete && (
                  <button
                    onClick={() => handleDelete(f)}
                    disabled={pendingId === f.id}
                    aria-label={`Remove ${f.name}`}
                    className="text-[11px] uppercase tracking-[2px] hover:text-[var(--state-danger)] inline-flex items-center gap-1 disabled:opacity-50"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <Trash2 aria-hidden className="w-3 h-3" /> Remove
                  </button>
                )}
              </div>
              {f.status && (
                <span
                  className="text-[10px] uppercase tracking-[2px]"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  {f.status}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
