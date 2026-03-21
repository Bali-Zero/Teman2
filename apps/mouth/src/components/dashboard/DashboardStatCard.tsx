"use client";

import React from "react";
import type { DashboardStatConfig } from "@/types/dashboard-role.types";

const COLOR_CLASS: Record<DashboardStatConfig["colorVariant"], string> = {
  green: "glass-green",
  red: "glass-red",
  yellow: "glass-yellow",
  blue: "glass-blue",
};

const VALUE_COLOR: Record<DashboardStatConfig["colorVariant"], string> = {
  green: "text-[#5cb88a]",
  red: "text-[#c45c78]",
  yellow: "text-[#b89a40]",
  blue: "text-[#4a8ec4]",
};

const TREND_COLOR = VALUE_COLOR;

interface DashboardStatCardProps extends DashboardStatConfig {
  className?: string;
}

export const DashboardStatCard = React.memo(function DashboardStatCard({
  icon,
  value,
  label,
  trend,
  colorVariant,
  className = "",
}: DashboardStatCardProps) {
  return (
    <div
      className={`glass-base ${COLOR_CLASS[colorVariant]} p-3 flex flex-col gap-1 ${className}`}
    >
      <span className="text-base">{icon}</span>
      <span
        className={`text-2xl font-extrabold leading-none tracking-tight ${VALUE_COLOR[colorVariant]}`}
      >
        {value}
      </span>
      <span className="text-[9px] uppercase tracking-widest text-white/35">
        {label}
      </span>
      <span
        className={`text-[9px] font-semibold mt-0.5 ${TREND_COLOR[colorVariant]}`}
      >
        {trend}
      </span>
    </div>
  );
});
