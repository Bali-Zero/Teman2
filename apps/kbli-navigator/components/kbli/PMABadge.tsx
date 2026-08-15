import { cn } from "@/lib/utils";

interface PMABadgeProps {
  status: "open" | "restricted" | "closed" | "unknown";
  maxForeign: number | "special" | null;
  /** Whole-code verdict carries the compiler-owned located tuple. */
  verdictVerified?: boolean;
  /** true => special-distribution condition (47221-class): "Restricted · special conditions", not "Closed 0%" */
  capSpecial?: boolean;
  /** false => withhold numeric/special cap claims and render "cap not verified" */
  capVerified?: boolean;
  size?: "sm" | "md";
}

const config = {
  open: {
    label: "Open",
    icon: "✅",
    className:
      "bg-[var(--kbli-pma-open-bg)] text-[var(--kbli-pma-open)] border-[var(--kbli-pma-open)]/20",
  },
  restricted: {
    label: "Restricted",
    icon: "⚠️",
    className:
      "bg-[var(--kbli-pma-restricted-bg)] text-[var(--kbli-pma-restricted)] border-[var(--kbli-pma-restricted)]/20",
  },
  closed: {
    label: "Closed",
    icon: "🚫",
    className:
      "bg-[var(--kbli-pma-closed-bg)] text-[var(--kbli-pma-closed)] border-[var(--kbli-pma-closed)]/20",
  },
  unknown: {
    label: "PMA unverified",
    icon: "❓",
    className: "bg-white/5 text-[var(--foreground-muted)] border-white/10",
  },
};

export function PMABadge({
  status,
  maxForeign,
  verdictVerified = false,
  capSpecial = false,
  capVerified = false,
  size = "md",
}: PMABadgeProps) {
  const numeric =
    typeof maxForeign === "number" && Number.isFinite(maxForeign)
      ? maxForeign
      : null;
  const markedSpecial = capSpecial === true && maxForeign === "special";
  const effectiveStatus =
    verdictVerified !== true
      ? "unknown"
      : status === "open" &&
          capVerified === true &&
          numeric === 0 &&
          !markedSpecial
        ? "closed"
        : status;
  const c =
    effectiveStatus === "unknown" && verdictVerified !== true
      ? { ...config.unknown, label: "PMA unverified" }
      : config[effectiveStatus];

  // Suffix that qualifies the badge, aligned with the native app:
  //  - verified special-distribution: "· special conditions" (never a %)
  //  - unverified numeric/special cap: "· cap not verified"
  //  - restricted & verified %: "· Max N%"
  //  - open verified cap: "· N% Foreign"; no cap is inferred from TERBUKA
  let suffix: string | null = null;
  if (verdictVerified !== true || status === "unknown") {
    suffix = null;
  } else if (markedSpecial && capVerified === true) {
    suffix = "· special conditions";
  } else if (status === "open") {
    suffix =
      capVerified !== true || numeric === null
        ? "· cap not verified"
        : `· ${numeric}% Foreign`;
  } else if (status === "restricted") {
    suffix =
      capVerified !== true || numeric === null
        ? "· cap not verified"
        : numeric <= 0
          ? "· closed (0%)"
          : numeric >= 100
            ? "· conditions apply"
            : `· Max ${numeric}%`;
  }

  const ariaLabel = `PMA status: ${c.label}${suffix ? ` ${suffix.replace(/^·\s*/, "")}` : ""}`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        c.className,
      )}
      aria-label={ariaLabel}
    >
      <span aria-hidden="true">{c.icon}</span>
      <span>{c.label}</span>
      {suffix && (
        <span className="opacity-70" aria-hidden="true">
          {suffix}
        </span>
      )}
    </span>
  );
}
