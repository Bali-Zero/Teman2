"use client";

import React from "react";
import { Users, ChevronDown } from "lucide-react";

interface TeamVerificationBadgeProps {
  status: "consulting" | "verified" | "not_needed";
  domainLabel?: string;
  onToggleCitations?: () => void;
}

export const TeamVerificationBadge: React.FC<TeamVerificationBadgeProps> = ({
  status,
  domainLabel,
  onToggleCitations,
}) => {
  if (status === "not_needed") {
    return null;
  }

  if (status === "consulting") {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium text-zinc-400 mt-3 select-none animate-pulse">
        <Users size={13} />
        <span>
          I nostri specialisti{domainLabel ? ` ${domainLabel}` : ""} stanno
          verificando...
        </span>
      </div>
    );
  }

  // status === "verified"
  return (
    <button
      onClick={onToggleCitations}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium text-amber-600 hover:text-amber-500 mt-3 select-none transition-colors cursor-pointer"
    >
      <Users size={13} />
      <span>Verificato dal team{domainLabel ? ` ${domainLabel}` : ""}</span>
      <ChevronDown size={11} className="ml-0.5 opacity-60" />
    </button>
  );
};
