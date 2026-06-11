/**
 * Canonical IDR/USD formatters — the ONLY place money formatting lives.
 *
 * Two notations, used everywhere (P0.3 audit 2026-06-11 found 4 competing
 * ones: `Rp 1.15B` / `Rp 45,2 jt` / `Rp 800 rb` / `Rp 1.850.000`):
 *  - formatIDR(n)        → "Rp 1.850.000"  (full, id-ID grouping) — detail
 *    views, invoices, payroll, tooltips.
 *  - formatIDRCompact(n) → "Rp 1.85M"      (K/M/B suffixes)       — KPIs,
 *    stat chips, dense tables.
 */

const IDR_FORMATTER = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

// en-US compact gives the K/M/B suffixes; the "Rp " prefix is added by hand
// because en-US currency style would render "IDR" instead of "Rp".
const IDR_COMPACT_FORMATTER = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 2,
});

const USD_FORMATTER = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatIDR(amount: number): string {
  return IDR_FORMATTER.format(amount);
}

export function formatIDRCompact(amount: number): string {
  return `Rp ${IDR_COMPACT_FORMATTER.format(amount)}`;
}

export function formatUSD(amount: number): string {
  return USD_FORMATTER.format(amount);
}

export function formatCurrency(
  amount: number,
  currency: string = "IDR",
): string {
  if (currency === "USD") return formatUSD(amount);
  return formatIDR(amount);
}
