import React from "react";
import { BadgeCheck, ChevronDown } from "lucide-react";
import { useChatLocale } from "@/hooks/useChatLocale";

export type VerificationStatus = "verified" | "consulting" | "not_needed";

interface TeamVerificationBadgeProps {
  status?: VerificationStatus;
  domainLabel?: string;
  isExpanded?: boolean;
  onToggleCitations?: () => void;
}

const LABELS: Record<string, (domain: string) => string> = {
  en: (d) => `Our ${d} specialists are verifying`,
  it: (d) => `I nostri specialisti ${d} stanno verificando`,
  id: (d) => `Spesialis ${d} kami sedang memverifikasi`,
  fr: (d) => `Nos spécialistes ${d} vérifient`,
  ru: (d) => `Наши специалисты по ${d} проверяют`,
};

const VERIFIED_LABELS: Record<string, (domain: string) => string> = {
  en: (d) => `Verified by ${d} team`,
  it: (d) => `Verificato dal team ${d}`,
  id: (d) => `Diverifikasi oleh tim ${d}`,
  fr: (d) => `Vérifié par l'équipe ${d}`,
  ru: (d) => `Подтверждено командой ${d}`,
};

export const TeamVerificationBadge: React.FC<TeamVerificationBadgeProps> = ({
  status = "verified",
  domainLabel = "Legal",
  isExpanded = false,
  onToggleCitations,
}) => {
  const locale = useChatLocale();

  if (status === "not_needed") return null;

  const labelFn =
    status === "verified"
      ? VERIFIED_LABELS[locale] || VERIFIED_LABELS.en
      : LABELS[locale] || LABELS.en;

  const label = labelFn(domainLabel);

  const baseClassName =
    "flex items-center gap-1 text-[10px] text-accent/80 font-medium";

  if (onToggleCitations) {
    return (
      <button
        type="button"
        onClick={onToggleCitations}
        className={`${baseClassName} hover:text-accent transition-colors cursor-pointer focus-ring rounded px-1 -ml-1`}
        aria-expanded={isExpanded}
      >
        <BadgeCheck size={12} className="shrink-0" aria-hidden="true" />
        <span>{label}</span>
        <ChevronDown
          size={10}
          className={`shrink-0 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
          aria-hidden="true"
        />
      </button>
    );
  }

  return (
    <div className={baseClassName}>
      <BadgeCheck size={12} className="shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
};
