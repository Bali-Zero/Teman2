"use client";

import { Copy } from "lucide-react";
import { toast } from "sonner";
import { crystalCard, companyTypeSubtitles } from "./editorial-tokens";

interface IdentityRowProps {
  nib?: string;
  npwp?: string;
  companyType: string;
}

export function IdentityRow({ nib, npwp, companyType }: IdentityRowProps) {
  if (!nib && !npwp && !companyType) return null;

  const copyToClipboard = (text: string) => {
    void navigator.clipboard.writeText(text);
    toast.success("Copied");
  };

  const subtitle = companyTypeSubtitles[companyType] || companyType;

  return (
    <div
      className="grid grid-cols-1 md:grid-cols-3 gap-0 rounded-[var(--kbli-radius-lg)] overflow-hidden"
      style={crystalCard}
    >
      {/* NIB */}
      <div className="px-[22px] py-5 border-b md:border-b-0 md:border-r border-[var(--kbli-border)] flex flex-col gap-1 transition-colors hover:bg-white/[0.03] group cursor-pointer"
        onClick={() => nib && copyToClipboard(nib)}
      >
        <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-[var(--kbli-text-muted)]">
          NIB
        </span>
        <span className="text-[13px] font-semibold text-[var(--kbli-text-primary)] tabular-nums flex items-center gap-2">
          {nib || "—"}
          {nib && (
            <Copy className="w-2.5 h-2.5 text-[var(--kbli-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
          )}
        </span>
        <span className="text-[11px] text-[var(--kbli-text-secondary)]">
          Nomor Induk Berusaha
        </span>
      </div>

      {/* NPWP */}
      <div className="px-[22px] py-5 border-b md:border-b-0 md:border-r border-[var(--kbli-border)] flex flex-col gap-1 transition-colors hover:bg-white/[0.03] group cursor-pointer"
        onClick={() => npwp && copyToClipboard(npwp)}
      >
        <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-[var(--kbli-text-muted)]">
          NPWP
        </span>
        <span className="text-[13px] font-semibold text-[var(--kbli-text-primary)] tabular-nums flex items-center gap-2">
          {npwp || "—"}
          {npwp && (
            <Copy className="w-2.5 h-2.5 text-[var(--kbli-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
          )}
        </span>
        <span className="text-[11px] text-[var(--kbli-text-secondary)]">
          Tax Identification Number
        </span>
      </div>

      {/* Entity Type */}
      <div className="px-[22px] py-5 flex flex-col gap-1 transition-colors hover:bg-white/[0.03]">
        <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-[var(--kbli-text-muted)]">
          Entity Type
        </span>
        <span className="text-[13px] font-semibold text-[var(--kbli-text-primary)]">
          {companyType || "—"}
        </span>
        {subtitle && subtitle !== companyType && (
          <span className="text-[11px] text-[var(--kbli-text-secondary)]">
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
}
