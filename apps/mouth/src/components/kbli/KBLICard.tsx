import Link from "next/link";
import { PMABadge } from "./PMABadge";
import { RiskBadge } from "./RiskBadge";
import { TransitionBadge } from "./TransitionBadge";
import type { KBLICode } from "@/lib/kbli-types";

interface KBLICardProps {
  code: KBLICode;
  showTransition?: boolean;
}

export function KBLICard({ code, showTransition = false }: KBLICardProps) {
  return (
    <Link
      href={`/kbli/${code.code}`}
      className="group block rounded-xl border border-[var(--border)] bg-[var(--kbli-bg-card)]
                 p-5 transition-all duration-200
                 hover:border-[var(--kbli-accent)]/30 hover:bg-[var(--kbli-bg-card-hover)]
                 hover:shadow-[0_0_30px_rgba(245,158,11,0.05)]"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* Code + Section */}
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-mono text-sm font-bold text-[var(--kbli-accent)]">
              {code.code}
            </span>
            <span className="text-xs text-[var(--foreground-muted)]">
              Section {code.section}
            </span>
          </div>

          {/* Title */}
          <h3
            className="text-base font-semibold text-[var(--foreground)] leading-snug
                          group-hover:text-[var(--kbli-accent)] transition-colors"
          >
            {code.titleEn}
          </h3>
          <p className="text-sm text-[var(--foreground-muted)] mt-0.5 line-clamp-1">
            {code.titleId}
          </p>
        </div>

        {/* Arrow */}
        <span
          className="text-[var(--foreground-muted)] group-hover:text-[var(--kbli-accent)]
                         transition-transform group-hover:translate-x-0.5 mt-1 shrink-0"
        >
          →
        </span>
      </div>

      {/* Badges */}
      <div className="flex flex-wrap items-center gap-2 mt-3">
        <PMABadge
          status={code.pma.status}
          maxForeign={code.pma.maxForeign}
          size="sm"
        />
        {code.licensing[0] && (
          <RiskBadge riskCategory={code.licensing[0].riskCategory} size="sm" />
        )}
        {showTransition && code.transition.status && (
          <TransitionBadge status={code.transition.status} />
        )}
      </div>
    </Link>
  );
}
