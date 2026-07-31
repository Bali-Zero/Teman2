import type { MarketingMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props {
  metrics: MarketingMetrics;
  alerts: RoleAlert[];
}

export function MarketingRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-[var(--bz-text-3)] tracking-[.12em]">
        MARKETING
      </span>
      <span className="text-2xl font-black text-[var(--state-info)] leading-none">
        +{metrics.subscriber_delta}
      </span>
      <span className="text-[10px] text-[var(--bz-text-2)]">
        nuovi iscritti
      </span>
      <div className="h-px bg-[var(--bz-border)]" />
      {metrics.articoli_in_review > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-warning)_7%,transparent)] border border-[color-mix(in_srgb,var(--state-warning)_18%,transparent)] text-[9px] font-semibold text-[var(--state-warning)]">
          ✍️ {metrics.articoli_in_review} articoli in review
        </div>
      )}
      <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-success)_8%,transparent)] border border-[color-mix(in_srgb,var(--state-success)_20%,transparent)] text-[9px] font-semibold text-[var(--state-success)]">
        📝 {metrics.articoli_pubblicati} pubblicati
      </div>
      {metrics.lead_nuovi > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-info)_8%,transparent)] border border-[color-mix(in_srgb,var(--state-info)_20%,transparent)] text-[9px] font-semibold text-[var(--state-info)]">
          🎯 {metrics.lead_nuovi} lead nuovi
        </div>
      )}
    </div>
  );
}
