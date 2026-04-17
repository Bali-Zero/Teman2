"use client";

import React from "react";
import type { DashboardRole } from "@/lib/dashboard-role";
import { useRoleMetrics } from "@/hooks/useRoleMetrics";
import { ZeroRoleWidget } from "./role-widgets/ZeroRoleWidget";
import { TeamRoleWidget } from "./role-widgets/TeamRoleWidget";
import { TaxRoleWidget } from "./role-widgets/TaxRoleWidget";
import { MarketingRoleWidget } from "./role-widgets/MarketingRoleWidget";
import { AccountingRoleWidget } from "./role-widgets/AccountingRoleWidget";

interface RoleWidgetProps {
  role: DashboardRole;
  userId: string;
}

export function RoleWidget({ role, userId }: RoleWidgetProps) {
  const { data, isLoading, isError } = useRoleMetrics(role, userId);

  return (
    <div
      className="glass-base glass-violet p-3.5 flex flex-col gap-2"
      style={{
        background:
          "linear-gradient(145deg, rgba(110,85,210,0.10) 0%, rgba(60,35,150,0.06) 100%)",
      }}
    >
      {isLoading && (
        <>
          <div className="h-3 w-20 rounded bg-white/5 animate-pulse" />
          <div className="h-6 w-16 rounded bg-white/5 animate-pulse" />
          <div className="h-3 w-24 rounded bg-white/5 animate-pulse" />
          <div className="h-px bg-white/5" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-7 rounded bg-white/5 animate-pulse" />
          ))}
        </>
      )}

      {isError && (
        <p className="text-[10px] text-accent-pink-editorial">
          Errore nel caricamento dati.
        </p>
      )}

      {!isLoading && !isError && data && (
        <div className="flex flex-col flex-1 min-h-0">
          {data.role === "zero" && (
            <ZeroRoleWidget metrics={data.metrics} alerts={data.alerts} />
          )}
          {data.role === "team" && (
            <TeamRoleWidget metrics={data.metrics} alerts={data.alerts} />
          )}
          {data.role === "tax" && (
            <TaxRoleWidget metrics={data.metrics} alerts={data.alerts} />
          )}
          {data.role === "marketing" && (
            <MarketingRoleWidget metrics={data.metrics} alerts={data.alerts} />
          )}
          {data.role === "accounting" && (
            <AccountingRoleWidget metrics={data.metrics} alerts={data.alerts} />
          )}
        </div>
      )}
    </div>
  );
}
