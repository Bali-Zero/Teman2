"use client";

import React from "react";
import { Users, ChevronDown } from "lucide-react";
import { useChatLocale } from "@/hooks/useChatLocale";
import type { Locale } from "@/i18n/types";

const LABELS: Record<
  Locale,
  {
    consulting: (domain?: string) => string;
    verified: (domain?: string) => string;
  }
> = {
  en: {
    consulting: (d) => `Our${d ? ` ${d}` : ""} specialists are verifying...`,
    verified: (d) => `Verified by${d ? ` ${d}` : ""} team`,
  },
  it: {
    consulting: (d) =>
      `I nostri specialisti${d ? ` ${d}` : ""} stanno verificando...`,
    verified: (d) => `Verificato dal team${d ? ` ${d}` : ""}`,
  },
  id: {
    consulting: (d) =>
      `Spesialis${d ? ` ${d}` : ""} kami sedang memverifikasi...`,
    verified: (d) => `Diverifikasi oleh tim${d ? ` ${d}` : ""}`,
  },
  fr: {
    consulting: (d) => `Nos spécialistes${d ? ` ${d}` : ""} vérifient...`,
    verified: (d) => `Vérifié par l'équipe${d ? ` ${d}` : ""}`,
  },
  ru: {
    consulting: (d) => `Наши специалисты${d ? ` ${d}` : ""} проверяют...`,
    verified: (d) => `Проверено командой${d ? ` ${d}` : ""}`,
  },
};

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
  const locale = useChatLocale();
  const labels = LABELS[locale];

  if (status === "not_needed") return null;

  if (status === "consulting") {
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium text-zinc-400 mt-3 select-none animate-pulse">
        <Users size={13} />
        <span>{labels.consulting(domainLabel)}</span>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onToggleCitations}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium text-amber-600 hover:text-amber-500 mt-3 select-none transition-colors cursor-pointer focus-ring"
    >
      <Users size={13} />
      <span>{labels.verified(domainLabel)}</span>
      <ChevronDown size={11} className="ml-0.5 opacity-60" />
    </button>
  );
};
