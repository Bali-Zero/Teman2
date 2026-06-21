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
      <p className="text-sm text-[#c9a96e]/60 py-8 text-center">
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
              className="flex items-center justify-between gap-3 p-3 rounded-lg border border-[#d4845a]/30 bg-white/5 text-xs text-[#f0ece4]"
            >
              <span className="truncate">
                Removed <strong>{f.name}</strong>. Recoverable for 30 days.
              </span>
              {onRestore && (
                <button
                  onClick={() => handleRestore(f)}
                  disabled={pendingId === f.id}
                  className="shrink-0 text-[11px] uppercase tracking-[2px] text-[#d4845a] hover:underline inline-flex items-center gap-1 disabled:opacity-50"
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
              className="p-3 rounded-lg border border-white/10 hover:border-white/30 flex flex-col gap-2"
            >
              <div className="flex items-start gap-2">
                <Icon
                  aria-hidden
                  className="w-8 h-8 text-[#c9a96e]/70 shrink-0"
                />
                <div className="min-w-0 flex-1">
                  <p className="text-xs text-[#f0ece4] truncate" title={f.name}>
                    {f.name}
                  </p>
                  <p className="text-[10px] uppercase tracking-[2px] text-[#c9a96e]/40 mt-1">
                    {f.type}
                  </p>
                </div>
              </div>
              {f.purpose && (
                <p
                  className="text-[11px] text-[#c9a96e]/70 italic line-clamp-2"
                  title={f.purpose}
                >
                  “{f.purpose}”
                </p>
              )}
              <div className="flex items-center justify-between text-[10px] text-[#c9a96e]/40">
                <span>{formatDate(f.created_at)}</span>
                {f.size_kb != null && <span>{f.size_kb} KB</span>}
              </div>
              <div className="flex items-center justify-between gap-2">
                {f.downloadable && onDownload ? (
                  <button
                    onClick={() => onDownload(f)}
                    className="text-[11px] uppercase tracking-[2px] text-[#d4845a] hover:underline inline-flex items-center gap-1"
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
                    className="text-[11px] uppercase tracking-[2px] text-[#c9a96e]/50 hover:text-[#c94a4a] inline-flex items-center gap-1 disabled:opacity-50"
                  >
                    <Trash2 aria-hidden className="w-3 h-3" /> Remove
                  </button>
                )}
              </div>
              {f.status && (
                <span className="text-[10px] uppercase tracking-[2px] text-[#c9a96e]/60">
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
