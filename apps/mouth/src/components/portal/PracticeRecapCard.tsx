import React from "react";
import { Info } from "lucide-react";
import type { DashboardRecap } from "@/lib/api/portal/portal.types";

/**
 * PracticeRecapCard — the client record recap hero (FASE 3, §3.5).
 *
 * Shows the facts-locked recap that the backend composes from audited structured
 * fields (open_actions + deadlines + unread). The client request path is fully
 * deterministic, and a permanent non-legal-advice disclaimer remains visible.
 *
 * Theme-aware: reads on the light client surface and the dark backoffice alike.
 */
export interface PracticeRecapCardProps {
  recap: DashboardRecap | null | undefined;
  loading?: boolean;
  className?: string;
}

export function PracticeRecapCard({
  recap,
  loading = false,
  className,
}: PracticeRecapCardProps) {
  if (loading) {
    return (
      <div
        className={`border-l-[3px] border-[var(--bz-copper)] bg-[var(--bz-card)] rounded-r-[0.5rem] px-6 py-5 ${className ?? ""}`}
      >
        <div
          className="h-4 w-24 rounded animate-pulse"
          style={{ background: "var(--bz-border)" }}
        />
        <div
          className="mt-3 h-4 w-full rounded animate-pulse"
          style={{ background: "var(--bz-border)" }}
        />
        <div
          className="mt-2 h-4 w-2/3 rounded animate-pulse"
          style={{ background: "var(--bz-border)" }}
        />
      </div>
    );
  }

  if (!recap) return null;

  return (
    <div
      className={`border-l-[3px] border-[var(--bz-copper)] bg-[var(--bz-card)] rounded-r-[0.5rem] px-6 py-5 ${className ?? ""}`}
    >
      <span className="block text-[10px] font-[650] uppercase tracking-[.14em] text-[var(--tx-secondary)]">
        Your update
      </span>

      <p
        className="mt-3 text-[21px] leading-[1.35] tracking-[-0.015em] text-[var(--tx-pure)]"
        style={{ fontFamily: "var(--font-serif, inherit)" }}
      >
        {recap.text}
      </p>

      {/* Permanent not-legal-advice disclaimer, never hidden */}
      <p className="mt-[10px] flex items-start gap-1.5 text-[12px] leading-snug text-[var(--tx-secondary)]">
        <Info className="w-3 h-3 mt-1 shrink-0" aria-hidden />
        <span>{recap.disclaimer}</span>
      </p>
    </div>
  );
}

export default PracticeRecapCard;
