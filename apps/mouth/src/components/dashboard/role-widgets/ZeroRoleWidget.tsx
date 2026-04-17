import type { ZeroMetrics, RoleAlert } from "@/types/dashboard-role.types";
import {
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Server,
  FileWarning,
} from "lucide-react";

interface Props {
  metrics: ZeroMetrics;
  alerts: RoleAlert[];
}

function formatRevenue(rp: number): string {
  if (rp >= 1_000_000_000) return `Rp ${(rp / 1_000_000_000).toFixed(2)}B`;
  if (rp >= 1_000_000) return `Rp ${(rp / 1_000_000).toFixed(1)}M`;
  if (rp >= 1_000) return `Rp ${(rp / 1_000).toFixed(0)}K`;
  return `Rp ${rp.toFixed(0)}`;
}

export function ZeroRoleWidget({ metrics }: Props) {
  const hasAlerts = metrics.visti_scadenza > 0 || metrics.fatture_overdue > 0;

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Revenue block */}
      <div>
        <span className="text-[9px] font-bold text-[#9880d8]/70 tracking-[.12em] uppercase">
          Revenue · MTD
        </span>
        <div className="mt-1.5 flex items-end gap-2">
          <span className="text-[28px] font-black text-white leading-none tracking-tight">
            {formatRevenue(metrics.revenue_mtd)}
          </span>
        </div>
        <div className="flex items-center gap-1 mt-1">
          <TrendingUp size={10} className="text-accent-sage" />
          <span className="text-[9px] font-semibold text-accent-sage">
            +12% vs last month
          </span>
        </div>
      </div>

      {/* Divider */}
      <div className="h-px bg-white/[0.06]" />

      {/* Alert rows */}
      <div className="flex flex-col gap-1.5 flex-1">
        {metrics.visti_scadenza > 0 && (
          <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-[rgba(196,92,120,0.07)] border border-[rgba(196,92,120,0.18)]">
            <AlertTriangle size={11} className="text-accent-pink-editorial flex-shrink-0" />
            <span className="text-[10px] font-semibold text-accent-pink-editorial">
              {metrics.visti_scadenza} visti &lt; 7gg
            </span>
          </div>
        )}

        {metrics.fatture_overdue > 0 && (
          <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)]">
            <FileWarning size={11} className="text-[#b89a40] flex-shrink-0" />
            <span className="text-[10px] font-semibold text-[#b89a40]">
              {metrics.fatture_overdue}{" "}
              {metrics.fatture_overdue === 1 ? "fattura" : "fatture"} overdue
            </span>
          </div>
        )}

        {!hasAlerts && (
          <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-[rgba(92,184,138,0.06)] border border-[rgba(92,184,138,0.16)]">
            <CheckCircle2 size={11} className="text-accent-sage flex-shrink-0" />
            <span className="text-[10px] font-semibold text-accent-sage">
              No critical alerts
            </span>
          </div>
        )}

        {/* System status */}
        <div className="flex items-center gap-2 px-2.5 py-2 rounded-lg bg-[rgba(74,142,196,0.06)] border border-[rgba(74,142,196,0.16)]">
          <Server size={11} className="text-[#4a8ec4] flex-shrink-0" />
          <span className="text-[10px] font-semibold text-[#4a8ec4]">
            Fly.io {metrics.fly_uptime}%
          </span>
          <span
            className="ml-auto flex-shrink-0 w-1.5 h-1.5 rounded-full bg-accent-sage"
            style={{ boxShadow: "0 0 4px rgba(92,184,138,0.8)" }}
          />
        </div>
      </div>
    </div>
  );
}
