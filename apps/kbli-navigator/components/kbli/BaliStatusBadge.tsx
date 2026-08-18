import { cn } from "@/lib/utils";

// L4 Bali status — the sovereign-local layer. National PMA openness != Bali registrability.
// Source: schema-v2 l4_bali (moratorium 2026-05-13, Gubernur letter B.27.000/642 + research).
export type BaliStatus =
  | "OK_or_HIGHER_RISK"
  | "APERTO_BALI_RISCHIO_ALTO"
  | "BLOCCATO_CLASSE_RISCHIO"
  | "BLOCCATO_DIPENDE_SCOPE"
  | "CHIUSO_MORATORIA_BALI"
  | "CHIUSO_PMA_NO_BESAR"
  | "CHIUSO_REGOLATORE_SETTORIALE"
  | "CHIUSO_BALI"
  | "CHIUSO_BALI_PROPOSTO"
  | "TERTUTUP"
  | "TERBATAS"
  | "NON_CLASSIFICABILE";

interface BaliStatusBadgeProps {
  status: BaliStatus;
  reason?: string;
  confidence?: "HIGH" | "MEDIUM" | "LOW";
  needsReview?: boolean;
  size?: "sm" | "md";
}

const config: Record<
  BaliStatus,
  { label: string; icon: string; tone: "ok" | "warn" | "block" }
> = {
  OK_or_HIGHER_RISK: { label: "Registrable in Bali", icon: "✅", tone: "ok" },
  APERTO_BALI_RISCHIO_ALTO: {
    label: "Open in Bali (high-risk tier)",
    icon: "✅",
    tone: "ok",
  },
  BLOCCATO_CLASSE_RISCHIO: {
    label: "Blocked in Bali (risk-class moratorium)",
    icon: "🚫",
    tone: "block",
  },
  BLOCCATO_DIPENDE_SCOPE: {
    label: "Depends on scope — verify in OSS",
    icon: "⚠️",
    tone: "warn",
  },
  CHIUSO_MORATORIA_BALI: {
    label: "Closed in Bali (2026 moratorium)",
    icon: "🚫",
    tone: "block",
  },
  CHIUSO_PMA_NO_BESAR: {
    label: "Reserved for MSME — closed to PT PMA",
    icon: "🚫",
    tone: "block",
  },
  CHIUSO_REGOLATORE_SETTORIALE: {
    label: "Closed (sector regulator)",
    icon: "🚫",
    tone: "block",
  },
  CHIUSO_BALI: { label: "Closed for PMA in Bali", icon: "🚫", tone: "block" },
  CHIUSO_BALI_PROPOSTO: {
    label: "Closure proposed (Bali)",
    icon: "⚠️",
    tone: "warn",
  },
  TERTUTUP: { label: "Closed to foreigners", icon: "🚫", tone: "block" },
  TERBATAS: { label: "Restricted (Bali cap)", icon: "⚠️", tone: "warn" },
  NON_CLASSIFICABILE: {
    label: "Bali status not classifiable — verify",
    icon: "❓",
    tone: "warn",
  },
};

// Defense-in-depth: any l4_bali.status not in `config` must NOT crash the build (superscar #9 schema-drift).
const FALLBACK_BADGE = {
  label: "Bali status — verify in OSS",
  icon: "❓",
  tone: "warn" as const,
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
  const c = config[status] ?? FALLBACK_BADGE;
  const ariaLabel = `Bali status: ${c.label}${reason ? `. ${reason}` : ""}`;
  // `reason` used to reach the reader ONLY via `aria-label`/`title` — neither
  // fires on mobile/touch (no hover) and `title` is unreliable for screen
  // readers too. It now also renders as visible text under the pill.
  return (
    <span
      className={cn(
        "inline-flex max-w-full flex-col items-start gap-1",
        size === "sm" && "max-w-[220px]",
      )}
    >
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border font-medium",
          size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
          toneClass[c.tone],
        )}
        aria-label={ariaLabel}
        title={reason}
      >
        <span aria-hidden="true">🏝️</span>
        <span aria-hidden="true">{c.icon}</span>
        <span>{c.label}</span>
        {needsReview && (
          <span className="opacity-70" aria-hidden="true">
            · needs review
          </span>
        )}
        {confidence && confidence !== "HIGH" && (
          <span className="opacity-60" aria-hidden="true">
            · {confidence.toLowerCase()} conf.
          </span>
        )}
      </span>
      {reason && (
        <span className="text-xs leading-snug opacity-70" aria-hidden="true">
          {reason}
        </span>
      )}
    </span>
  );
}
