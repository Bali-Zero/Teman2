"use client";

import { Edit2 } from "lucide-react";
import { StatusChip } from "./StatusChip";
import {
  formatCapital,
  companyTypeSubtitles,
} from "./editorial-tokens";

interface EditorialHeroProps {
  companyName: string;
  companyType: string;
  companyStatus?: string;
  nib?: string;
  kbliDescription?: string;
  city?: string;
  province?: string;
  addressStr?: string;
  capital: string | null;
  shareholderCount: number;
  foundingYear: number | null;
  companyId?: number;
  onEdit: () => void;
}

export function EditorialHero({
  companyName,
  companyType,
  companyStatus,
  nib,
  kbliDescription,
  city,
  province,
  addressStr,
  capital,
  shareholderCount,
  foundingYear,
  companyId,
  onEdit,
}: EditorialHeroProps) {
  // Split company name for italic styling on last word(s)
  const words = companyName.split(" ");
  let mainPart = companyName;
  let italicPart = "";
  if (words.length >= 3) {
    // If company name has a recognizable type suffix, italicize it
    const lastTwo = words.slice(-2).join(" ");
    const suffixes = ["Consulting", "Indonesia", "International", "Services", "Group", "Trading"];
    if (suffixes.some((s) => lastTwo.includes(s))) {
      mainPart = words.slice(0, -1).join(" ");
      italicPart = words[words.length - 1];
    }
  }

  // Build editorial prose dynamically
  const location = city || province;
  const typeLabel = companyTypeSubtitles[companyType] || companyType;
  const isPMA = companyType === "PT PMA" || companyType === "PMA";
  const typeStr = isPMA ? "PT PMA (foreign-owned)" : typeLabel || companyType;

  // Line 1: type + location + year
  const line1Parts: string[] = [];
  if (companyType) line1Parts.push(typeStr);
  if (foundingYear && location) line1Parts.push(`founded in ${location}, ${foundingYear}`);
  else if (foundingYear) line1Parts.push(`founded ${foundingYear}`);
  else if (location) line1Parts.push(`based in ${location}`);

  // Line 2: business activity (KBLI)
  const line2 = kbliDescription
    ? kbliDescription.split(";")[0].trim() // Take first activity only
    : null;

  // Line 3: structure summary
  const line3Parts: string[] = [];
  if (shareholderCount > 0)
    line3Parts.push(`${shareholderCount} shareholder${shareholderCount > 1 ? "s" : ""}`);
  if (capital) line3Parts.push(`authorized capital ${capital}`);

  const prose = [
    line1Parts.join(", "),
    line2,
    line3Parts.length > 0 ? line3Parts.join(" · ") : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const status = companyStatus || "active";

  return (
    <div className="pt-14 pb-10">
      {/* Eyebrow */}
      <div className="flex items-center gap-2.5 mb-5">
        <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--kbli-accent)]">
          Company Profile
        </span>
        <span className="w-8 h-px bg-[var(--kbli-accent)] opacity-50" />
        {companyId && (
          <button
            onClick={onEdit}
            className="ml-auto p-1.5 rounded-lg hover:bg-white/10 text-[var(--kbli-text-muted)] transition-colors"
            title="Edit company"
            aria-label="Edit company"
          >
            <Edit2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* H1 */}
      <h1 className="text-[36px] md:text-[48px] font-[800] tracking-[-0.035em] leading-[1.05] text-[var(--kbli-text-primary)] mb-6">
        {italicPart ? (
          <>
            {mainPart}{" "}
            <em className="font-light italic text-[var(--kbli-text-secondary)]">
              {italicPart}
            </em>
          </>
        ) : (
          companyName
        )}
      </h1>

      {/* Status chips */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {status === "active" && (
          <StatusChip
            label="Active"
            variant="green"
            icon={
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--kbli-pma-open)] shadow-[0_0_6px_var(--kbli-pma-open)]" />
            }
          />
        )}
        {status === "in_setup" && <StatusChip label="In Setup" variant="amber" />}
        {status === "dormant" && <StatusChip label="Dormant" variant="cool" />}
        {companyType && <StatusChip label={companyType} variant="accent" />}
        {nib && <StatusChip label="OSS \u2713" variant="cool" />}
      </div>

      {/* Prose */}
      {prose && (
        <p className="text-base leading-[1.75] text-[var(--kbli-text-secondary)] max-w-[680px] font-normal">
          {prose}
        </p>
      )}
    </div>
  );
}
