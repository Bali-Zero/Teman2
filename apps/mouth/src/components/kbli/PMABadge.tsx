import { cn } from "@/lib/utils";
import { pmaCapShape } from "@/lib/kbli-pma-shape";

interface PMABadgeProps {
  status: "open" | "restricted" | "closed" | "unknown";
  maxForeign: number | "special" | null;
  /** Whole-code verdict has a canonical official locator + source vintage. */
  verdictVerified?: boolean;
  /** true => special-distribution condition (47221-class): "· special conditions", not "Closed 0%" */
  capSpecial?: boolean;
  /** false => withhold numeric/special cap claims and render "· cap not verified" */
  capVerified?: boolean;
  /**
   * true => the code is nationally open but BLOCKED for a PT PMA in Bali
   * (l4_bali.blocked — moratorium / reserved UMKM). National openness != Bali
   * registrability: a bare green "Open · 100% Foreign" next to a "closed in Bali"
   * verdict is the nazionale-vs-Bali contradiction. Qualify the suffix instead.
   */
  baliBlocked?: boolean;
  /**
   * true => nationally open, and NOT on Bali's 2026 applied-closure list (18
   * business fields) — but the low/medium-low risk tier the OLD blanket
   * reading relied on was only ever named in the Governor's own request
   * letter, never enacted for this code. Must NEVER render as a plain green
   * "✅ Open": a bare green pill next to this fact is the same
   * nazionale-vs-Bali contradiction `baliBlocked` exists to prevent, just
   * with a "verify" outcome instead of a "blocked" one. Added 2026-09-15
   * (W-J B1, Codex sol MAJOR finding 2 on PR #6578).
   */
  baliAttentionFascia?: boolean;
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
  verdictVerified = false,
  capSpecial = false,
  capVerified = false,
  baliBlocked = false,
  baliAttentionFascia = false,
  size = "md",
}: PMABadgeProps) {
  const numeric =
    typeof maxForeign === "number" && Number.isFinite(maxForeign)
      ? maxForeign
      : null;
  const markedSpecial = capSpecial === true && maxForeign === "special";
  const capPublishable =
    verdictVerified === true &&
    capVerified === true &&
    (numeric !== null || markedSpecial);
  const zeroCapClosure = capPublishable && !markedSpecial && numeric === 0;
  const effectiveStatus = zeroCapClosure ? "closed" : status;
  // A verified zero cap (genuinely closed) outranks the attention-fascia warn:
  // that is a different, stronger fact than "verify the risk tier in Bali".
  // `baliBlocked` also outranks it — not a real data shape (a code is never
  // both `l4_bali.blocked === true` and ATTENZIONE_FASCIA_BALI at once), but
  // if a caller ever passes both, the stronger "blocked" fact must win on
  // BOTH the icon/label and the suffix, never split across the two.
  const attentionFasciaOpen =
    baliAttentionFascia === true &&
    baliBlocked !== true &&
    verdictVerified === true &&
    effectiveStatus === "open";
  const c =
    verdictVerified === true
      ? attentionFasciaOpen
        ? { ...config.restricted, label: "Open" }
        : config[effectiveStatus] || config.unknown
      : {
          ...config.unknown,
          label: "PMA unverified",
        };
  // Qualifying suffix, aligned with the native app:
  //  - verified special-distribution → "· special conditions" (never a %)
  //  - unverified numeric/special cap → "· cap not verified"
  //  - restricted & verified % → "· Max N%"
  //  - open 100% → "· 100% Foreign"
  //  - open but Bali-blocked → "· 100% nat'l · blocked in Bali" (no false green promise)
  //  - open but off Bali's closure list → "· 100% nat'l · verify in Bali" (same reasoning)
  let suffix: string | null = null;
  if (verdictVerified !== true) {
    suffix = null;
  } else if (!capPublishable) {
    suffix =
      status === "open" && baliBlocked
        ? "· cap not verified · blocked in Bali"
        : status === "open" && attentionFasciaOpen
          ? "· cap not verified · verify in Bali"
          : "· cap not verified";
  } else if (zeroCapClosure) {
    suffix = "· 0% foreign ownership";
  } else if (status === "open" && baliBlocked) {
    suffix = markedSpecial
      ? "· special conditions nat'l · blocked in Bali"
      : `· ${numeric}% nat'l · blocked in Bali`;
  } else if (status === "open" && attentionFasciaOpen) {
    suffix = markedSpecial
      ? "· special conditions nat'l · verify in Bali"
      : `· ${numeric}% nat'l · verify in Bali`;
  } else if (markedSpecial) {
    suffix = "· special conditions";
  } else if (status === "open" && numeric !== null) {
    suffix = `· ${numeric}% Foreign`;
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
    // Verification is checked before classifying the extremes: an unverified
    // 0 or 100 remains explicitly unverified instead of becoming a closure or
    // a no-cap condition by assertion.
    if (numeric !== null) {
      switch (pmaCapShape({ maxForeign, capSpecial, capVerified })) {
        case "none":
          suffix = "· closed (0%)";
          break;
        case "full":
        case "conditional":
          suffix = "· conditions apply";
          break;
        default:
          suffix = `· Max ${numeric}%`;
      }
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
