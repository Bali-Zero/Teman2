import { cn } from '@/lib/utils';

interface PMABadgeProps {
  status: 'open' | 'restricted' | 'closed';
  maxForeign: number | 'special';
  /** true => special-distribution condition (47221-class): "Restricted · special conditions", not "Closed 0%" */
  capSpecial?: boolean;
  /** false => TERBATAS cap % is not source-backed: render "≈N% (unverified)" */
  capVerified?: boolean;
  size?: 'sm' | 'md';
}

const config = {
  open: {
    label: 'Open',
    icon: '✅',
    className:
      'bg-[var(--kbli-pma-open-bg)] text-[var(--kbli-pma-open)] border-[var(--kbli-pma-open)]/20',
  },
  restricted: {
    label: 'Restricted',
    icon: '⚠️',
    className:
      'bg-[var(--kbli-pma-restricted-bg)] text-[var(--kbli-pma-restricted)] border-[var(--kbli-pma-restricted)]/20',
  },
  closed: {
    label: 'Closed',
    icon: '🚫',
    className:
      'bg-[var(--kbli-pma-closed-bg)] text-[var(--kbli-pma-closed)] border-[var(--kbli-pma-closed)]/20',
  },
};

export function PMABadge({
  status,
  maxForeign,
  capSpecial = false,
  capVerified = true,
  size = 'md',
}: PMABadgeProps) {
  const c = config[status];
  const numeric = typeof maxForeign === 'number' ? maxForeign : null;

  // Suffix that qualifies the badge, aligned with the native app:
  //  - special-distribution: "· special conditions" (never a %)
  //  - restricted & unverified %: "· ≈N% unverified"
  //  - restricted & verified %: "· Max N%"
  //  - open 100%: "· 100% Foreign"
  let suffix: string | null = null;
  if (capSpecial) {
    suffix = '· special conditions';
  } else if (status === 'open' && numeric === 100) {
    suffix = '· 100% Foreign';
  } else if (status === 'restricted' && numeric !== null && numeric < 100) {
    suffix = capVerified ? `· Max ${numeric}%` : `· ≈${numeric}% unverified`;
  }

  const ariaLabel = capSpecial
    ? 'PMA status: Restricted, open with special distribution conditions'
    : status === 'open' && numeric === 100
      ? 'PMA status: Open for foreign investment, 100% foreign ownership allowed'
      : status === 'restricted' && numeric !== null && numeric < 100
        ? `PMA status: Restricted, maximum ${numeric}% foreign ownership${capVerified ? '' : ' (unverified cap)'}`
        : `PMA status: ${c.label}`;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
        c.className
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
