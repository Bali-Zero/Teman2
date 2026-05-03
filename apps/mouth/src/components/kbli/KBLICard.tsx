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
  const isGold = code.tier === "gold";
  return (
    <Link
      href={`/kbli/${code.code}`}
      className={`group block rounded-2xl border p-5 transition-all duration-300 backdrop-blur-xl
                 hover:-translate-y-1 hover:border-[var(--kbli-accent)]/40 hover:bg-white/5
                 hover:shadow-[0_8px_32px_rgba(220,38,38,0.15)]
                 ${
                   isGold
                     ? "border-[rgba(212,132,90,0.2)] bg-[rgba(255,255,255,0.03)]"
                     : "border-[rgba(255,255,255,0.06)] bg-[rgba(255,255,255,0.02)]"
                 }`}
      style={
        isGold
          ? {
              boxShadow:
                "inset 0 1px 0 0 rgba(212,132,90,0.12), 0 4px 24px rgba(0,0,0,0.2)",
            }
          : { boxShadow: "0 4px 24px rgba(0,0,0,0.2)" }
      }
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {/* Code + Section */}
          <div className="mb-1.5 flex items-center gap-2">
            <span className="font-mono text-sm font-bold text-[var(--kbli-accent)]">
              {code.code}
            </span>
            <span className="text-xs text-[var(--foreground-muted)]">
              Section {code.section}
            </span>
            {isGold && (
              <span
                className="text-xs text-[var(--kbli-accent)]"
                title="Curated content available"
                aria-label="Curated content available"
              >
                ★
              </span>
            )}
          </div>

          {/* Title */}
          <h3
            className="text-base font-semibold leading-snug text-[var(--foreground)]
                        transition-colors group-hover:text-[var(--kbli-accent)]"
          >
            {code.titleEn}
          </h3>
          <p className="mt-0.5 text-sm text-[var(--foreground-muted)] line-clamp-1">
            {code.titleId}
          </p>
        </div>

        {/* Arrow */}
        <span
          className="mt-1 shrink-0 text-[var(--foreground-muted)]
                     transition-transform group-hover:translate-x-0.5 group-hover:text-[var(--kbli-accent)]"
        >
          →
        </span>
      </div>

      {/* Badges */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <PMABadge
          status={code.pma.status}
          maxForeign={code.pma.maxForeign}
          size="sm"
        />
        {code.licensing[0] && (
          <RiskBadge riskCategory={code.licensing[0].riskCategory} size="sm" />
        )}
        {showTransition && code.transition.mappingStatus && (
          <TransitionBadge status={code.transition.mappingStatus} />
        )}
      </div>
    </Link>
  );
}
