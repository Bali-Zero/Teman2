import type { KBLIMappingStatus } from '@/lib/kbli-types';

interface TransitionBadgeProps {
  status: KBLIMappingStatus;
}

const labels: Record<string, { text: string; icon: string; color: string }> = {
  MATCH_LANGSUNG: {
    text: 'Unchanged from 2020',
    icon: '',
    color: 'var(--kbli-map-unchanged)',
  },
  CODICE_RINUMERATO: {
    text: 'Renumbered in 2025',
    icon: '🔄 ',
    color: 'var(--kbli-map-renamed)',
  },
  MATCH_CON_AGGREGAZIONE: {
    text: 'Merged in 2025',
    icon: '🔀 ',
    color: 'var(--kbli-map-merged)',
  },
  BPS_ONLY: {
    text: 'New in 2025',
    icon: '🆕 ',
    color: 'var(--kbli-map-new)',
  },
};

export function TransitionBadge({ status }: TransitionBadgeProps) {
  const config = labels[status];
  if (!config) return null;

  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium"
      style={{
        color: config.color,
        borderColor: `color-mix(in srgb, ${config.color} 20%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${config.color} 8%, transparent)`,
      }}
      aria-label={`KBLI 2025 transition: ${config.text}`}
    >
      <span aria-hidden="true">{config.icon}</span>
      {config.text}
    </span>
  );
}
