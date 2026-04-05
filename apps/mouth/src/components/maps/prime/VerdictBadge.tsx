'use client';

const VERDICT_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  GREEN: {
    bg: 'bg-emerald-500/20 border-emerald-500/40',
    text: 'text-emerald-300',
    label: 'Can Invest',
  },
  YELLOW: { bg: 'bg-amber-500/20 border-amber-500/40', text: 'text-amber-300', label: 'Caution' },
  RED: { bg: 'bg-red-500/20 border-red-500/40', text: 'text-red-300', label: 'Cannot Invest' },
};

interface Props {
  verdict: 'GREEN' | 'YELLOW' | 'RED';
  score: number;
  compact?: boolean;
}

export function VerdictBadge({ verdict, score, compact = false }: Props) {
  const style = VERDICT_STYLES[verdict] || VERDICT_STYLES.RED;

  if (compact) {
    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold border ${style.bg} ${style.text}`}
      >
        {score}
      </span>
    );
  }

  return (
    <div className={`flex items-center justify-between px-4 py-3 rounded-xl border ${style.bg}`}>
      <div>
        <div className={`text-sm font-bold ${style.text}`}>{style.label}</div>
        <div className="text-xs text-slate-500 mt-0.5">Investment Verdict</div>
      </div>
      <div className={`text-2xl font-black tabular-nums ${style.text}`}>
        {score}
        <span className="text-xs font-normal opacity-60">/100</span>
      </div>
    </div>
  );
}
