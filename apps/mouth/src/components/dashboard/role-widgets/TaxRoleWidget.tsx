import type { TaxMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props {
  metrics: TaxMetrics;
  alerts: RoleAlert[];
}

export function TaxRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-[var(--bz-text-3)] tracking-[.12em]">
        COMPLIANCE
      </span>
      {metrics.prossima_scadenza && (
        <>
          <span className="text-[10px] text-[var(--bz-text-2)]">
            Prossima scadenza
          </span>
          <span className="text-lg font-black text-[var(--state-danger)] leading-none">
            {metrics.prossima_scadenza}
          </span>
        </>
      )}
      <div className="h-px bg-[var(--bz-border)]" />
      <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-success)_8%,transparent)] border border-[color-mix(in_srgb,var(--state-success)_20%,transparent)] text-[9px] font-semibold text-[var(--state-success)]">
        ✓ {metrics.clienti_compliant} clienti compliant
      </div>
      {metrics.scadenze_7gg > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-danger)_9%,transparent)] border border-[color-mix(in_srgb,var(--state-danger)_22%,transparent)] text-[9px] font-semibold text-[var(--state-danger)]">
          🚨 {metrics.scadenze_7gg} scadenze &lt;7gg
        </div>
      )}
      {metrics.dichiarazioni_pending > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-warning)_7%,transparent)] border border-[color-mix(in_srgb,var(--state-warning)_18%,transparent)] text-[9px] font-semibold text-[var(--state-warning)]">
          ⏳ {metrics.dichiarazioni_pending} dichiarazioni pending
        </div>
      )}
    </div>
  );
}
