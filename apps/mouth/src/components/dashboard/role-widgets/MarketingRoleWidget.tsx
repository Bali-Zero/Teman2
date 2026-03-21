"use client";
import React from "react";
import type { MarketingMetrics, RoleAlert } from "@/types/dashboard-role.types";

interface Props {
  metrics: MarketingMetrics;
  alerts: RoleAlert[];
}

export function MarketingRoleWidget({ metrics }: Props) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[9px] font-bold text-white/40 tracking-[.12em]">
        MARKETING
      </span>
      <span className="text-2xl font-black text-[#4a8ec4] leading-none">
        +{metrics.subscriber_delta}
      </span>
      <span className="text-[10px] text-white/50">nuovi iscritti</span>
      <div className="h-px bg-white/[0.06]" />
      {metrics.articoli_in_review > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(184,154,64,0.07)] border border-[rgba(184,154,64,0.18)] text-[9px] font-semibold text-[#b89a40]">
          ✍️ {metrics.articoli_in_review} articoli in review
        </div>
      )}
      <div className="px-2 py-1.5 rounded-lg bg-[rgba(92,184,138,0.08)] border border-[rgba(92,184,138,0.20)] text-[9px] font-semibold text-[#5cb88a]">
        📝 {metrics.articoli_pubblicati} pubblicati
      </div>
      {metrics.lead_nuovi > 0 && (
        <div className="px-2 py-1.5 rounded-lg bg-[rgba(74,142,196,0.08)] border border-[rgba(74,142,196,0.20)] text-[9px] font-semibold text-[#4a8ec4]">
          🎯 {metrics.lead_nuovi} lead nuovi
        </div>
      )}
    </div>
  );
}
