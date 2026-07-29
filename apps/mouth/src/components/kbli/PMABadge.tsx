import { cn } from "@/lib/utils";
import { pmaCapShape } from "@/lib/kbli-pma-shape";

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
  } else if (status === "restricted") {
    // The SHAPE comes from the shared classifier; only the wording is this
    // badge's own. This branch used to carry a private copy of the rule,
    // `numeric !== null && numeric < 100`, which failed at both ends in
    // OPPOSITE ways:
    //   - cap 0 passed the bound (0 < 100), reached the formula and published
    //     "⚠️ Restricted · Max 0%" on /kbli/47111 — still live after #3186 and
    //     #3436 unified every other surface;
    //   - cap 100 was EXCLUDED by the bound, so the badge printed no suffix at
    //     all, leaving a bare "Restricted" whose qualifier the reader cannot
    //     recover. Not "right by accident" — silently unhelpful, which is why
    //     the corpus below calls it guilty too.
    // A ceiling of 0 is not a ceiling anyone can invest under; a ceiling of
    // 100 restricts nothing.
    //
    // KNOWN GAP, shared with `restrictedCapBadge` and NOT introduced here: the
    // `none` / `full` / `conditional` arms answer before `capVerified` is
    // consulted, so an UNVERIFIED cap at an extreme would be stated as fact.
    // Measured on all 1,559 rows: the only two `capVerified: false` records are
    // TERBUKA/100 and never reach this branch, and the single restricted cap-0
    // row is verified — so the cell is unreachable today. Curing it belongs in
    // the shared module, where all six presenters inherit it at once.
    switch (pmaCapShape({ maxForeign, capSpecial, capVerified })) {
      case "none":
        suffix = "· closed (0%)";
        break;
      case "full":
      case "conditional":
        suffix = "· conditions apply";
        break;
      default:
        suffix = capVerified
          ? `· Max ${numeric}%`
          : `· ≈${numeric}% unverified`;
    }
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
