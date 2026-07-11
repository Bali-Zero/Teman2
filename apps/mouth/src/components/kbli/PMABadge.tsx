import { cn } from "@/lib/utils";

interface PMABadgeProps {
  status: "open" | "restricted" | "closed" | "unknown";
  maxForeign: number | "special";
  /** true => special-distribution condition (47221-class): "· special conditions", not "Closed 0%" */
  capSpecial?: boolean;
  /** false => TERBATAS cap % not source-backed: render "· ≈N% unverified" */
  capVerified?: boolean;
  /**
   * true => the code is nationally open but BLOCKED for a PT PMA in Bali
   * (l4_bali.blocked — moratorium / reserved UMKM). National openness != Bali
   * registrability: a bare green "Open · 100% Foreign" next to a "closed in Bali"
   * verdict is the nazionale-vs-Bali contradiction. Qualify the suffix instead.
   */
  baliBlocked?: boolean;
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
    label: "Unknown",
    icon: "❓",
    className: "bg-slate-50 text-slate-500 border-slate-200",
  },
};

export function PMABadge({
  status,
  maxForeign,
  capSpecial = false,
  capVerified = true,
  baliBlocked = false,
  size = "md",
}: PMABadgeProps) {
  const c = config[status] || config.open;
  const numeric = typeof maxForeign === "number" ? maxForeign : null;

  // Qualifying suffix, aligned with the native app:
  //  - special-distribution → "· special conditions" (never a %)
  //  - restricted & unverified % → "· ≈N% unverified"
  //  - restricted & verified % → "· Max N%"
  //  - open 100% → "· 100% Foreign"
  //  - open but Bali-blocked → "· 100% nat'l · blocked in Bali" (no false green promise)
  let suffix: string | null = null;
  if (capSpecial) {
    suffix = "· special conditions";
  } else if (status === "open" && baliBlocked) {
    suffix = "· 100% nat'l · blocked in Bali";
  } else if (status === "open" && numeric === 100) {
    suffix = "· 100% Foreign";
  } else if (status === "restricted" && numeric !== null && numeric < 100) {
    suffix = capVerified ? `· Max ${numeric}%` : `· ≈${numeric}% unverified`;
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
        c.className,
      )}
    >
      <span>{c.icon}</span>
      <span>{c.label}</span>
      {suffix && <span className="opacity-70">{suffix}</span>}
    </span>
  );
}
