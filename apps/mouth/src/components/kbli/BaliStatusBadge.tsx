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

const config: Record<
  string,
  { label: string; icon: string; tone: "ok" | "warn" | "block" }
> = {
  OK_or_HIGHER_RISK: { label: "Registrable in Bali", icon: "✅", tone: "ok" },
  // Nationally TERBUKA and the Besar scale is Menengah-Tinggi/Tinggi → survives the
  // Bali risk-class moratorium → registrable by a PT PMA in Bali (#1814 risk-tier pass).
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
  // Nationally TERBUKA but the Besar scale is Rendah/Menengah-Rendah → blocked by the
  // 2026 Bali PMA moratorium (Gov. letter B.27.000/642). Resolved by #1814 risk-tier pass.
  CHIUSO_MORATORIA_BALI: {
    label: "Closed in Bali (2026 moratorium)",
    icon: "🚫",
    tone: "block",
  },
  // Closed by a national sector regulator regardless of risk tier (e.g. Bank Indonesia,
  // BAPETEN) — structurally closed to private/PMA capital. Resolved by #1814.
  CHIUSO_REGOLATORE_SETTORIALE: {
    label: "Closed (sector regulator)",
    icon: "🚫",
    tone: "block",
  },
  // Besar-scale risk is low on some ruang lingkup but higher on others: OSS computes
  // risk per (code × scope × scale), so registrability depends on the declared scope.
  // (deep research 2026-06-20: rejection is on "tingkat risiko", not on the code.)
  BLOCCATO_DIPENDE_SCOPE: {
    label: "Conditional in Bali — depends on declared scope",
    icon: "⚠️",
    tone: "warn",
  },
  // No Usaha Besar scale row in OSS → activity reserved for cooperatives/MSME under
  // Perpres 10/2021 (amended 49/2021), Lampiran II Pasal 5(1)(a). A PT PMA is Usaha
  // Besar by law (UU 6/2023 + Permeninves 5/2025) and cannot register it.
  CHIUSO_PMA_NO_BESAR: {
    label: "Reserved for MSME — closed to PT PMA",
    icon: "🚫",
    tone: "block",
  },
  // No OSS-RBA risk scope at all (404): special/sectoral regime — finance (OJK/BI),
  // pharma (BPOM), and other sensitive activities licensed outside the ordinary RBA
  // flow. Not mechanically caught by the low-risk Bali block → verify case-by-case.
  NEEDS_REVIEW_NO_OSS_SCOPE: {
    label: "Special regime — verify case-by-case",
    icon: "❓",
    tone: "warn",
  },
  CHIUSO_BALI: { label: "Closed for PMA in Bali", icon: "🚫", tone: "block" },
  CHIUSO_BALI_PROPOSTO: {
    label: "Closure proposed (Bali)",
    icon: "⚠️",
    tone: "warn",
  },
  TERTUTUP: { label: "Closed to foreigners", icon: "🚫", tone: "block" },
  TERBATAS: { label: "Restricted (foreign cap)", icon: "⚠️", tone: "warn" },
  TERTUTUP_CANDIDATE: {
    label: "Likely closed — verify",
    icon: "❓",
    tone: "warn",
  },
  TERBATAS_CANDIDATE: {
    label: "Likely restricted — verify",
    icon: "❓",
    tone: "warn",
  },
  // GARUDA-FILIERA Fase-1 cure #4 (2026-07-17): the risk tier this verdict
  // depended on was carried over from a different activity through a
  // code-number collision and has been detached — the moratorium
  // applicability is genuinely unresolved, not "verify a special regime"
  // (NEEDS_REVIEW_NO_OSS_SCOPE) or a known ok/blocked verdict.
  NON_CLASSIFICABILE: {
    label: "Bali status not classifiable — verify",
    icon: "❓",
    tone: "warn",
  },
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
