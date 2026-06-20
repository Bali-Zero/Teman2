import React from "react";
import { Sparkles, Info } from "lucide-react";
import type { DashboardRecap } from "@/lib/api/portal/portal.types";

/**
 * PracticeRecapCard — the "highly AI-smart with recaps" hero (FASE 3, §3.5).
 *
 * Shows the facts-locked, prose-polished recap that the backend composes from
 * audited structured fields (open_actions + deadlines + unread). The numbers and
 * dates are deterministic; the LLM only warms the tone. A permanent disclaimer
 * makes the AI provenance and non-legal-advice status unmissable (cures the
 * DeepSeek "hallucinated lawyer" liability — AP3).
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
        className={`rounded-2xl border p-5 ${className ?? ""}`}
        style={{
          background: "var(--bz-elevated)",
          borderColor: "var(--bz-border)",
        }}
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
      className={`rounded-2xl border p-5 ${className ?? ""}`}
      style={{
        background: "var(--bz-elevated)",
        borderColor: "var(--bz-border-accent)",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <Sparkles
          className="w-4 h-4"
          style={{ color: "var(--bz-accent-warm)" }}
          aria-hidden
        />
        <span
          className="text-xs font-bold uppercase tracking-wider"
          style={{ color: "var(--bz-accent-warm)" }}
        >
          Your update
        </span>
      </div>

      <p
        className="text-base leading-relaxed"
        style={{
          color: "var(--bz-text-1)",
          fontFamily: "var(--font-serif, inherit)",
        }}
      >
        {recap.text}
      </p>

      {/* Permanent disclaimer — AI provenance + not-legal-advice, never hidden */}
      <p
        className="mt-3 flex items-start gap-1.5 text-[11px] leading-snug"
        style={{ color: "var(--bz-text-3)" }}
      >
        <Info className="w-3 h-3 mt-0.5 shrink-0" aria-hidden />
        <span>{recap.disclaimer}</span>
      </p>
    </div>
  );
}

export default PracticeRecapCard;
