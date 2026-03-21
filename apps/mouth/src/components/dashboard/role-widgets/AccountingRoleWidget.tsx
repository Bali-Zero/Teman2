"use client";
import React from "react";
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
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">
        ACCOUNTING
      </span>
      <span className="text-2xl font-black text-[#c45c78] leading-none">
        {metrics.fatture_overdue}
      </span>
      <span className="text-[10px] text-white/50">fatture overdue</span>
      <div className="h-px bg-white/[0.06]" />
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(196,92,120,0.09)] border border-[rgba(196,92,120,0.22)] text-[9px] font-semibold text-[#c45c78]">
        💰 ${overdueK}K totale overdue
      </div>
      {metrics.fatture_pending > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          ⏳ {metrics.fatture_pending} pending
        </div>
      )}
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(92,184,138,0.08)] border border-[rgba(92,184,138,0.20)] text-[9px] font-semibold text-[#5cb88a]">
        ✓ {metrics.fatture_pagate_mtd} pagate (MTD)
      </div>
    </div>
  );
}
