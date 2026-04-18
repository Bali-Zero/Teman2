"use client";
import {
  FileText,
  Image as ImgIcon,
  File as FileIcon,
  Download,
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
}

export function VaultFileGrid({ files, onDownload }: Props) {
  if (files.length === 0) {
    return (
      <p className="text-sm text-[#c9a96e]/60 py-8 text-center">
        No files in this view.
      </p>
    );
  }
  return (
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
            <div className="flex items-center justify-between text-[10px] text-[#c9a96e]/40">
              <span>{formatDate(f.created_at)}</span>
              {f.size_kb != null && <span>{f.size_kb} KB</span>}
            </div>
            {f.downloadable && onDownload && (
              <button
                onClick={() => onDownload(f)}
                className="text-[11px] uppercase tracking-[2px] text-[#d4845a] hover:underline inline-flex items-center gap-1"
              >
                <Download aria-hidden className="w-3 h-3" /> Download
              </button>
            )}
            {f.status && (
              <span className="text-[10px] uppercase tracking-[2px] text-[#c9a96e]/60">
                {f.status}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}
