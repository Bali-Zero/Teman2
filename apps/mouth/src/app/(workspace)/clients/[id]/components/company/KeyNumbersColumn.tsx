"use client";

import { formatCapitalFull } from "./editorial-tokens";

interface KeyNumbersProps {
  sharesCount?: number;
  shareNominalValue?: number;
  capital: string | null;
  aktaPerubahanNo?: string;
  aktaPerubahanDate?: string;
  foundingDate?: string;
  skNo?: string;
  addressStr?: string;
  city?: string;
  fullAddress?: string;
  formatDate: (d: string) => string;
}

export function KeyNumbersColumn({
  sharesCount,
  shareNominalValue,
  capital,
  aktaPerubahanNo,
  aktaPerubahanDate,
  foundingDate,
  skNo,
  addressStr,
  city,
  fullAddress,
  formatDate,
}: KeyNumbersProps) {
  const items: Array<{
    label: string;
    value: string;
    sub?: string;
    tag?: string;
    large?: boolean;
    valueStyle?: string;
  }> = [];

  // Authorized Capital
  const fullCapital = formatCapitalFull(sharesCount, shareNominalValue);
  if (fullCapital) {
    items.push({
      label: "Authorized Capital",
      value: fullCapital,
      sub: "IDR",
      tag: aktaPerubahanNo
        ? `Increased via Akta #${aktaPerubahanNo}${aktaPerubahanDate ? ` \u00B7 ${new Date(aktaPerubahanDate).getFullYear()}` : ""}`
        : undefined,
      large: true,
    });
  }

  // Share Structure
  if (sharesCount) {
    items.push({
      label: "Share Structure",
      value: `${sharesCount.toLocaleString()} shares`,
      sub: shareNominalValue
        ? `Rp ${(shareNominalValue / 1e6).toFixed(0)},000,000 par value per share`
        : undefined,
    });
  }

  // Incorporation Date
  if (foundingDate) {
    items.push({
      label: "Incorporation Date",
      value: formatDate(foundingDate),
      sub: skNo || undefined,
    });
  }

  // Last Amendment
  if (aktaPerubahanNo) {
    items.push({
      label: "Last Amendment",
      value: `Akta #${aktaPerubahanNo}`,
      sub: aktaPerubahanDate
        ? `${formatDate(aktaPerubahanDate)} \u00B7 Capital restructuring`
        : undefined,
    });
  }

  // Registered Address
  if (addressStr || city) {
    items.push({
      label: "Registered Address",
      value: city || addressStr || "",
      sub: fullAddress && fullAddress !== city ? fullAddress : undefined,
      valueStyle: "text-[15px] tracking-normal",
    });
  }

  if (items.length === 0) return null;

  return (
    <div className="flex flex-col">
      {items.map((item, i) => (
        <div
          key={item.label}
          className={`py-[22px] flex flex-col gap-1 ${i === 0 ? "pt-0" : ""} ${i < items.length - 1 ? "border-b border-[var(--kbli-border)]" : ""}`}
        >
          <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--kbli-text-muted)]">
            {item.label}
          </span>
          <span
            className={`font-bold text-[var(--kbli-text-primary)] leading-[1.15] tabular-nums tracking-[-0.02em] ${
              item.large
                ? "text-[28px] font-[800] text-[var(--kbli-accent)]"
                : item.valueStyle || "text-[22px]"
            }`}
          >
            {item.value}
          </span>
          {item.sub && (
            <span className="text-[12px] text-[var(--kbli-text-secondary)] mt-0.5">
              {item.sub}
            </span>
          )}
          {item.tag && (
            <span className="inline-block self-start px-2 py-0.5 rounded-[var(--kbli-radius-sm)] text-[10px] font-semibold mt-1 bg-[rgba(232,168,73,0.1)] text-[var(--kbli-amber)]">
              {item.tag}
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
