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
        background: "var(--bz-card)",
        borderColor: "var(--bz-border)",
      }}
    >
      {isLoading && (
        <>
          <div className="h-3 w-20 rounded bg-[var(--surface-raised)] animate-pulse" />
          <div className="h-6 w-16 rounded bg-[var(--surface-raised)] animate-pulse" />
          <div className="h-3 w-24 rounded bg-[var(--surface-raised)] animate-pulse" />
          <div className="h-px bg-[var(--bz-border)]" />
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-7 rounded bg-[var(--surface-raised)] animate-pulse"
            />
          ))}
        </>
      )}

      {isError && (
        <p className="text-[10px] text-[var(--state-danger)]">
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
