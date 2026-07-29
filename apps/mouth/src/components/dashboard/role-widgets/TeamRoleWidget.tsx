import type { TeamMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props {
  metrics: TeamMetrics;
  alerts: RoleAlert[];
}

export function TeamRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-[var(--bz-text-3)] tracking-[.12em]">
        MY CASES
      </span>
      <span className="text-2xl font-black text-[var(--state-success)] leading-none">
        {metrics.assigned_cases}
      </span>
      <span className="text-[10px] text-[var(--bz-text-2)]">
        assigned cases
      </span>
      <div className="h-px bg-[var(--bz-border)]" />
      {metrics.prossima_scadenza && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-danger)_9%,transparent)] border border-[color-mix(in_srgb,var(--state-danger)_22%,transparent)] text-[9px] font-semibold text-[var(--state-danger)]">
          ⏰ Deadline: {metrics.prossima_scadenza}
        </div>
      )}
      {metrics.stalled_count > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-warning)_9%,transparent)] border border-[color-mix(in_srgb,var(--state-warning)_22%,transparent)] text-[9px] font-semibold text-[var(--state-warning)]">
          ⚠️ {metrics.stalled_count} stalled &gt;14d
        </div>
      )}
      {metrics.doc_mancanti > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-warning)_7%,transparent)] border border-[color-mix(in_srgb,var(--state-warning)_18%,transparent)] text-[9px] font-semibold text-[var(--state-warning)]">
          📄 {metrics.doc_mancanti} missing documents
        </div>
      )}
    </div>
  );
}
