import React from "react";
import { BadgeCheck } from "lucide-react";
import { useChatLocale } from "@/hooks/useChatLocale";

export type VerificationStatus = "verified" | "consulting" | "not_needed";

interface TeamVerificationBadgeProps {
  status?: VerificationStatus;
  domainLabel?: string;
}

const LABELS: Record<string, (domain: string) => string> = {
  en: (d) => `Our ${d} specialists are verifying`,
  it: (d) => `Verificato dal team ${d}`,
  id: (d) => `Diverifikasi oleh tim ${d}`,
  fr: (d) => `Vérifié par l'équipe ${d}`,
  ru: (d) => `Подтверждено командой ${d}`,
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
}) => {
  const locale = useChatLocale();

  if (status === "not_needed") return null;

  const labelFn = status === "verified" ? VERIFIED_LABELS[locale] || VERIFIED_LABELS.en : LABELS[locale] || LABELS.en;

  const label = labelFn(domainLabel);

  return (
    <div className="flex items-center gap-1 text-[10px] text-accent/80 font-medium">
      <BadgeCheck size={12} className="shrink-0" aria-hidden="true" />
      <span aria-label={label}>{label}</span>
    </div>
  );
};
