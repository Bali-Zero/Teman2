"use client";

import React from "react";
import { Users, ChevronDown } from "lucide-react";
import { useChatLocale } from "@/hooks/useChatLocale";

const LABELS = {
  consulting: {
    en: (domain?: string) =>
      `Our${domain ? ` ${domain}` : ""} specialists are verifying...`,
    it: (domain?: string) =>
      `I nostri specialisti${domain ? ` ${domain}` : ""} stanno verificando...`,
    id: (domain?: string) =>
      `Spesialis${domain ? ` ${domain}` : ""} kami sedang memverifikasi...`,
    fr: (domain?: string) =>
      `Nos spécialistes${domain ? ` ${domain}` : ""} vérifient...`,
    ru: (domain?: string) =>
      `Наши специалисты${domain ? ` ${domain}` : ""} проверяют...`,
  },
  verified: {
    en: (domain?: string) => `Verified by the${domain ? ` ${domain}` : ""} team`,
    it: (domain?: string) => `Verificato dal team${domain ? ` ${domain}` : ""}`,
    id: (domain?: string) => `Diverifikasi oleh tim${domain ? ` ${domain}` : ""}`,
    fr: (domain?: string) => `Vérifié par l'équipe${domain ? ` ${domain}` : ""}`,
    ru: (domain?: string) => `Проверено командой${domain ? ` ${domain}` : ""}`,
  },
};

interface TeamVerificationBadgeProps {
  status: "consulting" | "verified" | "not_needed";
  domainLabel?: string;
  onToggleCitations?: () => void;
  isExpanded?: boolean;
}

export const TeamVerificationBadge: React.FC<TeamVerificationBadgeProps> = ({
  status,
  domainLabel,
  onToggleCitations,
  isExpanded = false,
}) => {
  const locale = useChatLocale();

  if (status === "not_needed") return null;

  if (status === "consulting") {
    const labelFn = LABELS.consulting[locale] ?? LABELS.consulting.en;
    return (
      <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium text-zinc-400 mt-3 select-none animate-pulse">
        <Users size={13} />
        <span>{labelFn(domainLabel)}</span>
      </div>
    );
  }

  const labelFn = LABELS.verified[locale] ?? LABELS.verified.en;
  const text = labelFn(domainLabel);

  return (
    <button
      type="button"
      onClick={onToggleCitations}
      aria-expanded={isExpanded}
      aria-label={text}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium text-amber-600 hover:text-amber-500 mt-3 select-none transition-colors cursor-pointer focus-ring"
    >
      <Users size={13} />
      <span>{text}</span>
      <ChevronDown
        size={11}
        className={`ml-0.5 opacity-60 transition-transform ${isExpanded ? "rotate-180" : ""}`}
      />
    </button>
  );
};
