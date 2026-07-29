import type {
  AccountingMetrics,
  RoleAlert,
} from "@/types/dashboard-role.types";

interface Props {
  metrics: AccountingMetrics;
  alerts: RoleAlert[];
}

export function AccountingRoleWidget({ metrics }: Props) {
  const overdueK = (metrics.overdue_total / 1000).toFixed(1);
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-[var(--bz-text-3)] tracking-[.12em]">
        ACCOUNTING
      </span>
      <span className="text-2xl font-black text-[var(--state-danger)] leading-none">
        {metrics.fatture_overdue}
      </span>
      <span className="text-[10px] text-[var(--bz-text-2)]">
        fatture overdue
      </span>
      <div className="h-px bg-[var(--bz-border)]" />
      <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-danger)_9%,transparent)] border border-[color-mix(in_srgb,var(--state-danger)_22%,transparent)] text-[9px] font-semibold text-[var(--state-danger)]">
        💰 ${overdueK}K totale overdue
      </div>
      {metrics.fatture_pending > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-warning)_7%,transparent)] border border-[color-mix(in_srgb,var(--state-warning)_18%,transparent)] text-[9px] font-semibold text-[var(--state-warning)]">
          ⏳ {metrics.fatture_pending} pending
        </div>
      )}
      <div className="px-2 py-1.5 rounded-lg bg-[color-mix(in_srgb,var(--state-success)_8%,transparent)] border border-[color-mix(in_srgb,var(--state-success)_20%,transparent)] text-[9px] font-semibold text-[var(--state-success)]">
        ✓ {metrics.fatture_pagate_mtd} pagate (MTD)
      </div>
    </div>
  );
}
