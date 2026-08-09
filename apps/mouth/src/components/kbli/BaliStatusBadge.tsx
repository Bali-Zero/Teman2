import { BALI_STATUS_CONFIG } from "@/lib/kbli-status-labels";
import { cn } from "@/lib/utils";

// L4 Bali status — the sovereign-local layer. National PMA openness (L2) != Bali registrability (L4).
// Source: schema-v2 l4_bali, injected into the KBLI data file (moratorium 2026-05-13,
// Gubernur letter B.27.000/642/PM/DPMPTSP).
export type BaliStatus =
  | "OK_or_HIGHER_RISK"
  | "APERTO_BALI_RISCHIO_ALTO"
  | "BLOCCATO_CLASSE_RISCHIO"
  | "BLOCCATO_DIPENDE_SCOPE"
  | "CHIUSO_PMA_NO_BESAR"
  | "CHIUSO_MORATORIA_BALI"
  | "CHIUSO_REGOLATORE_SETTORIALE"
  | "NEEDS_REVIEW_NO_OSS_SCOPE"
  | "CHIUSO_BALI"
  | "CHIUSO_BALI_PROPOSTO"
  | "TERTUTUP"
  | "TERBATAS"
  | "TERTUTUP_CANDIDATE"
  | "TERBATAS_CANDIDATE"
  | "NON_CLASSIFICABILE";

interface BaliStatusBadgeProps {
  status: string;
  reason?: string;
  confidence?: "HIGH" | "MEDIUM" | "LOW";
  needsReview?: boolean;
  /**
   * National PMA status. When "closed" (TERTUTUP / 0% foreign), it overrides a
   * moratorium-only "ok" l4 verdict: a nationally-closed code is not registrable
   * in Bali, no matter the Besar risk tier the #1814 pass scored.
   */
  pmaStatus?: "open" | "restricted" | "closed" | "unknown";
  size?: "sm" | "md";
}

// The label/icon/tone table now lives in `@/lib/kbli-status-labels` so the editorial
// renderer resolves a status to the SAME words this badge shows. Values unchanged.
const config = BALI_STATUS_CONFIG;

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
  pmaStatus,
  size = "md",
}: BaliStatusBadgeProps) {
  let c = config[status];
  if (!c) return null; // unknown status → render nothing rather than a broken badge
  // National-closed dominates Bali registrability. The #1814 risk-tier pass computes
  // l4 status from the Besar risk ALONE, so 58 codes that are nationally TERTUTUP
  // (0% foreign — e.g. 84111 Lembaga Legislatif, 60311 govt news agency) still got
  // l4 = OK_or_HIGHER_RISK → "✅ Registrable in Bali". A code closed to foreigners
  // nationwide is NOT registrable in Bali. When pmaStatus is closed, force the
  // verdict to "closed" regardless of the moratorium-only l4 status.
  if (
    pmaStatus === "closed" &&
    (c.tone === "ok" || status === "OK_or_HIGHER_RISK")
  ) {
    c = {
      label: "Closed to foreigners (national)",
      icon: "🚫",
      tone: "block",
    };
  }
  // `reason` used to reach the client ONLY via the `title` attribute — a hover
  // tooltip that never fires on mobile/touch (no hover event) and that most
  // screen readers do not announce either. For a badge that can read "Closed
  // to foreigners" the WHY is the load-bearing half of the claim, so it now
  // also renders as visible text beneath the pill. `title` stays too (free
  // desktop-hover affordance, never the only channel).
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
      {reason && (
        <span className="text-xs leading-snug text-[var(--kbli-text-muted)]">
          {reason}
        </span>
      )}
    </span>
  );
}
