import { cn } from "@/lib/utils";

// L4 Bali status — the sovereign-local layer. National PMA openness (L2) != Bali registrability (L4).
// Source: schema-v2 l4_bali, injected into the KBLI data file (moratorium 2026-05-13,
// Gubernur letter B.27.000/642/PM/DPMPTSP).
export type BaliStatus =
  | "OK_or_HIGHER_RISK"
  | "BLOCCATO_CLASSE_RISCHIO"
  | "CHIUSO_BALI"
  | "CHIUSO_BALI_PROPOSTO"
  | "TERTUTUP"
  | "TERBATAS"
  | "TERTUTUP_CANDIDATE"
  | "TERBATAS_CANDIDATE";

interface BaliStatusBadgeProps {
  status: string;
  reason?: string;
  confidence?: "HIGH" | "MEDIUM" | "LOW";
  needsReview?: boolean;
  size?: "sm" | "md";
}

const config: Record<
  string,
  { label: string; icon: string; tone: "ok" | "warn" | "block" }
> = {
  OK_or_HIGHER_RISK: { label: "Registrable in Bali", icon: "✅", tone: "ok" },
  BLOCCATO_CLASSE_RISCHIO: {
    label: "Blocked in Bali (risk-class moratorium)",
    icon: "🚫",
    tone: "block",
  },
  CHIUSO_BALI: { label: "Closed for PMA in Bali", icon: "🚫", tone: "block" },
  CHIUSO_BALI_PROPOSTO: { label: "Closure proposed (Bali)", icon: "⚠️", tone: "warn" },
  TERTUTUP: { label: "Closed to foreigners", icon: "🚫", tone: "block" },
  TERBATAS: { label: "Restricted (foreign cap)", icon: "⚠️", tone: "warn" },
  TERTUTUP_CANDIDATE: { label: "Likely closed — verify", icon: "❓", tone: "warn" },
  TERBATAS_CANDIDATE: { label: "Likely restricted — verify", icon: "❓", tone: "warn" },
};

const toneClass = {
  ok: "bg-[var(--kbli-pma-open-bg)] text-[var(--kbli-pma-open)] border-[var(--kbli-pma-open)]/20",
  warn: "bg-[var(--kbli-pma-restricted-bg)] text-[var(--kbli-pma-restricted)] border-[var(--kbli-pma-restricted)]/20",
  block:
    "bg-[var(--kbli-pma-closed-bg)] text-[var(--kbli-pma-closed)] border-[var(--kbli-pma-closed)]/20",
};

export function BaliStatusBadge({
  status,
  reason,
  confidence,
  needsReview,
  size = "md",
}: BaliStatusBadgeProps) {
  const c = config[status];
  if (!c) return null; // unknown status → render nothing rather than a broken badge
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        toneClass[c.tone],
      )}
      title={reason}
    >
      <span aria-hidden="true">🏝️</span>
      <span aria-hidden="true">{c.icon}</span>
      <span>{c.label}</span>
      {needsReview && <span className="opacity-70">· needs review</span>}
      {confidence && confidence !== "HIGH" && (
        <span className="opacity-60">· {confidence.toLowerCase()} conf.</span>
      )}
    </span>
  );
}
