import type { TeamMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props {
  metrics: TeamMetrics;
  alerts: RoleAlert[];
}

export function TeamRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">
        MY CASES
      </span>
      <span className="text-2xl font-black text-accent-sage leading-none">
        {metrics.pratiche_assegnate}
      </span>
      <span className="text-[10px] text-white/50">assigned cases</span>
      <div className="h-px bg-white/[0.06]" />
      {metrics.prossima_scadenza && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(196,92,120,0.09)] border border-[rgba(196,92,120,0.22)] text-[9px] font-semibold text-accent-pink-editorial">
          ⏰ Deadline: {metrics.prossima_scadenza}
        </div>
      )}
      {metrics.stalled_count > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.09)] border border-[rgba(184,154,64,0.22)] text-[9px] font-semibold text-[#b89a40]">
          ⚠️ {metrics.stalled_count} stalled &gt;14d
        </div>
      )}
      {metrics.doc_mancanti > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          📄 {metrics.doc_mancanti} missing documents
        </div>
      )}
    </div>
  );
}
