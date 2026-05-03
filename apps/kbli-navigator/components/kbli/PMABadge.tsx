import { cn } from '@/lib/utils';

interface PMABadgeProps {
  status: 'open' | 'restricted' | 'closed';
  maxForeign: number;
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

export function PMABadge({ status, maxForeign, size = 'md' }: PMABadgeProps) {
  const c = config[status];

  const ariaLabel =
    status === 'open' && maxForeign === 100
      ? 'PMA status: Open for foreign investment, 100% foreign ownership allowed'
      : status === 'restricted' && maxForeign < 100
        ? `PMA status: Restricted, maximum ${maxForeign}% foreign ownership`
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
      {status === 'open' && maxForeign === 100 && (
        <span className="opacity-70" aria-hidden="true">
          · 100% Foreign
        </span>
      )}
      {status === 'restricted' && maxForeign < 100 && (
        <span className="opacity-70" aria-hidden="true">
          · Max {maxForeign}%
        </span>
      )}
    </span>
  );
}
