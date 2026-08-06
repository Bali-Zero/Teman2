"use client";

import { Copy } from "lucide-react";
import { toast } from "sonner";
import { crystalCard, companyTypeSubtitles } from "./editorial-tokens";

interface IdentityRowProps {
  nib?: string;
  npwp?: string;
  companyType: string;
}

interface IdentifierCellProps {
  label: "NIB" | "NPWP";
  value?: string;
  description: string;
  onCopy: (value: string) => void;
}

const identifierCellClassName =
  "w-full px-[22px] py-5 border-b md:border-b-0 md:border-r border-[var(--kbli-border)] flex flex-col gap-1 transition-colors text-left";

function IdentifierCell({
  label,
  value,
  description,
  onCopy,
}: IdentifierCellProps) {
  const content = (
    <>
      <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-[var(--kbli-text-muted)]">
        {label}
      </span>
      <span className="text-[13px] font-semibold text-[var(--kbli-text-primary)] tabular-nums flex items-center gap-2">
        {value || "—"}
        {value && (
          <Copy className="w-2.5 h-2.5 text-[var(--kbli-text-muted)] opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 transition-opacity" />
        )}
      </span>
      <span className="text-[11px] text-[var(--kbli-text-secondary)]">
        {description}
      </span>
    </>
  );

  if (!value) {
    return <div className={identifierCellClassName}>{content}</div>;
  }

  return (
    <button
      type="button"
      aria-label={`Copy ${label}`}
      className={`${identifierCellClassName} group cursor-pointer bg-transparent hover:bg-[var(--glass-rim)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--bz-copper-text)]`}
      onClick={() => onCopy(value)}
    >
      {content}
    </button>
  );
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
      <IdentifierCell
        label="NIB"
        value={nib}
        description="Nomor Induk Berusaha"
        onCopy={copyToClipboard}
      />

      <IdentifierCell
        label="NPWP"
        value={npwp}
        description="Tax Identification Number"
        onCopy={copyToClipboard}
      />

      {/* Entity Type */}
      <div className="px-[22px] py-5 flex flex-col gap-1 transition-colors hover:bg-[var(--glass-rim)]">
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
