import type { TaxMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props {
  metrics: TaxMetrics;
  alerts: RoleAlert[];
}

export function TaxRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">
        COMPLIANCE
      </span>
      {metrics.prossima_scadenza && (
        <>
          <span className="text-[10px] text-white/50">Prossima scadenza</span>
          <span className="text-lg font-black text-accent-pink-editorial leading-none">
            {metrics.prossima_scadenza}
          </span>
        </>
      )}
      <div className="h-px bg-white/[0.06]" />
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(92,184,138,0.08)] border border-[rgba(92,184,138,0.20)] text-[9px] font-semibold text-accent-sage">
        ✓ {metrics.clienti_compliant} clienti compliant
      </div>
      {metrics.scadenze_7gg > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(196,92,120,0.09)] border border-[rgba(196,92,120,0.22)] text-[9px] font-semibold text-accent-pink-editorial">
          🚨 {metrics.scadenze_7gg} scadenze &lt;7gg
        </div>
      )}
      {metrics.dichiarazioni_pending > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          ⏳ {metrics.dichiarazioni_pending} dichiarazioni pending
        </div>
      )}
    </div>
  );
}
