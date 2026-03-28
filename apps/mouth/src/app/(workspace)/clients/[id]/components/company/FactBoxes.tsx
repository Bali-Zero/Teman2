"use client";

import { glassCard, computeAge } from "./editorial-tokens";

interface FactBoxesProps {
  capital: string | null;
  aktaPerubahanNo?: string;
  aktaPerubahanDate?: string;
  foundingDate?: string;
  documentCount: number;
}

export function FactBoxes({
  capital,
  aktaPerubahanNo,
  aktaPerubahanDate,
  foundingDate,
  documentCount,
}: FactBoxesProps) {
  const age = computeAge(foundingDate);

  const formatDateShort = (d?: string) => {
    if (!d) return "";
    const date = new Date(d);
    return date.toLocaleDateString("en-US", {
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
      {/* Capital */}
      <div
        className="p-[18px_20px] rounded-[var(--kbli-radius-md)] flex flex-col gap-1.5 transition-all hover:translate-y-[-1px]"
        style={glassCard}
      >
        <span
          className="text-[28px] font-[800] tracking-[-0.03em] tabular-nums leading-none"
          style={{ color: "var(--kbli-accent)" }}
        >
          {capital || "—"}
        </span>
        <span className="text-[11px] text-[var(--kbli-text-secondary)]">
          Authorized Capital
        </span>
        {aktaPerubahanNo && (
          <span className="text-[10px] text-[var(--kbli-text-muted)]">
            Post-Akta #{aktaPerubahanNo}
            {aktaPerubahanDate &&
              `, ${new Date(aktaPerubahanDate).getFullYear()}`}
          </span>
        )}
      </div>

      {/* Company Age */}
      <div
        className="p-[18px_20px] rounded-[var(--kbli-radius-md)] flex flex-col gap-1.5 transition-all hover:translate-y-[-1px]"
        style={glassCard}
      >
        <span
          className="text-[28px] font-[800] tracking-[-0.03em] tabular-nums leading-none"
          style={{ color: "var(--kbli-pma-open)" }}
        >
          {age ? age.label : "—"}
        </span>
        <span className="text-[11px] text-[var(--kbli-text-secondary)]">
          Company Age
        </span>
        {foundingDate && (
          <span className="text-[10px] text-[var(--kbli-text-muted)]">
            Incorporated {formatDateShort(foundingDate)}
          </span>
        )}
      </div>

      {/* Documents */}
      <div
        className="p-[18px_20px] rounded-[var(--kbli-radius-md)] flex flex-col gap-1.5 transition-all hover:translate-y-[-1px]"
        style={glassCard}
      >
        <span
          className="text-[28px] font-[800] tracking-[-0.03em] tabular-nums leading-none"
          style={{ color: "var(--kbli-amber)" }}
        >
          {documentCount}
        </span>
        <span className="text-[11px] text-[var(--kbli-text-secondary)]">
          Documents on File
        </span>
        <span className="text-[10px] text-[var(--kbli-text-muted)]">
          Legal vault, Drive-synced
        </span>
      </div>
    </div>
  );
}
