import { cn } from '@/lib/utils';

interface RiskBadgeProps {
  category?: string;
  riskCategory?: string;
  size?: 'sm' | 'md';
}

function parseRisk(category: string): { label: string; color: string } {
  if (!category) return { label: 'Unknown', color: 'var(--foreground-muted)' };
  const lower = category.toLowerCase();
  if (lower === 'tinggi') return { label: 'High', color: 'var(--kbli-risk-high)' };
  if (lower.includes('menengah') && lower.includes('tinggi'))
    return { label: 'Medium-High', color: 'var(--kbli-risk-medium-high)' };
  if (lower.includes('menengah') && lower.includes('rendah'))
    return { label: 'Medium-Low', color: 'var(--kbli-risk-medium-low)' };
  if (lower === 'rendah') return { label: 'Low', color: 'var(--kbli-risk-low)' };
  return { label: category, color: 'var(--foreground-muted)' };
}

export function RiskBadge({ category, riskCategory, size = 'md' }: RiskBadgeProps) {
  const { label, color } = parseRisk(category ?? riskCategory ?? '');
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm'
      )}
      style={{
        color,
        borderColor: `color-mix(in srgb, ${color} 20%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${color} 8%, transparent)`,
      }}
      aria-label={`${label} Risk level`}
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden="true"
      />
      {label} Risk
    </span>
  );
}
