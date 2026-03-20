"use client";
import React from "react";
import type { ZeroMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props { metrics: ZeroMetrics; alerts: RoleAlert[]; }

const ALERT_STYLE: Record<RoleAlert["type"], string> = {
  critical: "bg-[rgba(196,92,120,0.09)] border-[rgba(196,92,120,0.22)] text-[#c45c78]",
  warning:  "bg-[rgba(184,154,64,0.09)]  border-[rgba(184,154,64,0.22)]  text-[#b89a40]",
  ok:       "bg-[rgba(92,184,138,0.08)]  border-[rgba(92,184,138,0.20)]  text-[#5cb88a]",
  info:     "bg-[rgba(74,142,196,0.08)]  border-[rgba(74,142,196,0.20)]  text-[#4a8ec4]",
};

function formatRevenue(rp: number): string {
  if (rp >= 1_000_000_000) return `Rp ${(rp / 1_000_000_000).toFixed(2)}B`;
  if (rp >= 1_000_000) return `Rp ${(rp / 1_000_000).toFixed(1)}M`;
  if (rp >= 1_000) return `Rp ${(rp / 1_000).toFixed(0)}K`;
  return `Rp ${rp.toFixed(0)}`;
}

export function ZeroRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-[#9880d8]/85 tracking-[.12em]">REVENUE · MTD</span>
      <span className="text-2xl font-black text-white leading-none tracking-tight">{formatRevenue(metrics.revenue_mtd)}</span>
      <span className="text-[10px] font-medium text-[#5cb88a]">▲ +12% vs last month</span>
      <div className="h-px bg-white/[0.06]" />
      {metrics.visti_scadenza > 0 && (
        <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.critical}`}>
          🚨 {metrics.visti_scadenza} visti &lt;7gg
        </div>
      )}
      {metrics.fatture_overdue > 0 && (
        <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.warning}`}>
          ⚠️ {metrics.fatture_overdue} fatture overdue
        </div>
      )}
      {metrics.fatture_overdue === 0 && metrics.visti_scadenza === 0 && (
        <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.ok}`}>
          ✓ No critical alerts
        </div>
      )}
      <div className={`flex items-center gap-1.5 px-2 py-1.5 rounded-lg border text-[9px] font-semibold ${ALERT_STYLE.info}`}>
        🚀 Fly.io {metrics.fly_uptime}%
      </div>
    </div>
  );
}
