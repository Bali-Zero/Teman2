"use client";

import { glassCard } from "./editorial-tokens";

interface TimelineEntry {
  year: string;
  month?: string;
  typeLabel: string;
  title: string;
  body: string;
  refText: string;
  refColor: string;
  accentYear?: boolean;
}

interface LegalTimelineProps {
  aktaPendirianNo?: string;
  aktaPendirianDate?: string;
  aktaPerubahanNo?: string;
  aktaPerubahanDate?: string;
  skNo?: string;
  skDate?: string;
  nib?: string;
  npwp?: string;
  companyName: string;
  companyType: string;
  capital: string | null;
  formatDate: (d: string) => string;
}

export function LegalTimeline({
  aktaPendirianNo,
  aktaPendirianDate,
  aktaPerubahanNo,
  aktaPerubahanDate,
  skNo,
  skDate,
  nib,
  npwp,
  companyName,
  companyType,
  capital,
  formatDate,
}: LegalTimelineProps) {
  const entries: TimelineEntry[] = [];

  const getMonth = (d: string) =>
    new Date(d).toLocaleDateString("en-US", { month: "long" });
  const getYear = (d: string) => new Date(d).getFullYear().toString();

  // Amendment (most recent first)
  if (aktaPerubahanNo && aktaPerubahanDate) {
    entries.push({
      year: getYear(aktaPerubahanDate),
      month: getMonth(aktaPerubahanDate),
      typeLabel: "Amendment \u00B7 Capital Restructuring",
      title: `Akta Notaris #${aktaPerubahanNo}${capital ? ` \u2014 Capital ${capital}` : ""}`,
      body: capital
        ? `Capital restructuring formalized. Authorized capital updated to ${capital}.`
        : `Corporate amendment recorded under Akta #${aktaPerubahanNo}.`,
      refText: `Akta #${aktaPerubahanNo} \u00B7 ${formatDate(aktaPerubahanDate)}`,
      refColor: "var(--kbli-amber)",
      accentYear: true,
    });
  }

  // NIB / OSS registration
  if (nib) {
    const nibYear = skDate
      ? parseInt(getYear(skDate)) + 1
      : aktaPendirianDate
        ? parseInt(getYear(aktaPendirianDate)) + 1
        : null;
    entries.push({
      year: nibYear?.toString() || "—",
      typeLabel: "Regulatory \u00B7 OSS Compliance",
      title: "NIB Issued & OSS Platform Verified",
      body: `Registered on the Online Single Submission (OSS) platform. NIB ${nib} issued.${npwp ? ` NPWP tax registration ${npwp} completed.` : ""}`,
      refText: `NIB ${nib}${npwp ? ` \u00B7 NPWP ${npwp}` : ""}`,
      refColor: "var(--kbli-pma-open)",
    });
  }

  // Incorporation
  if (aktaPendirianNo && aktaPendirianDate) {
    entries.push({
      year: getYear(aktaPendirianDate),
      month: getMonth(aktaPendirianDate),
      typeLabel: "Incorporation \u00B7 Company Formation",
      title: `${companyName} Established`,
      body: `Company incorporated as a Perseroan Terbatas${companyType === "PT PMA" || companyType === "PMA" ? " under the PMA regime (foreign direct investment)" : ""}.${skNo ? " Approval granted by the Ministry of Law and Human Rights." : ""}`,
      refText: skNo
        ? `${skNo} \u00B7 ${formatDate(aktaPendirianDate)}`
        : formatDate(aktaPendirianDate),
      refColor: "var(--kbli-accent)",
    });
  } else if (skNo && skDate) {
    // Fallback: use SK as founding event
    entries.push({
      year: getYear(skDate),
      month: getMonth(skDate),
      typeLabel: "Incorporation \u00B7 Company Formation",
      title: `${companyName} Established`,
      body: `Company incorporated and approved by Kemenkumham.`,
      refText: `${skNo} \u00B7 ${formatDate(skDate)}`,
      refColor: "var(--kbli-accent)",
    });
  }

  if (entries.length === 0) return null;

  return (
    <div className="flex flex-col">
      {entries.map((entry, i) => (
        <div
          key={i}
          className={`grid grid-cols-[80px_1fr] md:grid-cols-[100px_1fr] gap-5 md:gap-8 py-7 items-start ${
            i === 0 ? "pt-0" : ""
          } ${i < entries.length - 1 ? "border-b border-[var(--kbli-border)]" : ""}`}
        >
          {/* Date column */}
          <div className="text-right pt-1">
            <div
              className="text-[20px] font-[800] leading-none tracking-[-0.02em] tabular-nums"
              style={{
                color: entry.accentYear
                  ? "var(--kbli-accent)"
                  : "var(--kbli-text-muted)",
                opacity: entry.accentYear ? 1 : undefined,
              }}
            >
              {entry.year}
            </div>
            {entry.month && (
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--kbli-text-muted)] opacity-60 mt-0.5">
                {entry.month}
              </div>
            )}
          </div>

          {/* Content */}
          <div>
            <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-[var(--kbli-text-muted)] mb-1.5">
              {entry.typeLabel}
            </div>
            <div className="text-base font-bold text-[var(--kbli-text-primary)] mb-2 leading-[1.3]">
              {entry.title}
            </div>
            <div className="text-[13px] text-[var(--kbli-text-secondary)] leading-relaxed">
              {entry.body}
            </div>
            {/* Reference pill */}
            <div
              className="inline-flex items-center gap-1.5 mt-2.5 text-[11px] text-[var(--kbli-text-muted)] tabular-nums px-2.5 py-1 rounded-[var(--kbli-radius-sm)]"
              style={{
                ...glassCard,
                borderRadius: "var(--kbli-radius-sm)",
                padding: "4px 10px",
              }}
            >
              <span
                className="w-[5px] h-[5px] rounded-full shrink-0"
                style={{ background: entry.refColor }}
              />
              {entry.refText}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
