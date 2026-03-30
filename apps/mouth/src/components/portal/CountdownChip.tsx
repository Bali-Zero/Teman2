import React from 'react';

interface CountdownChipProps {
  /** ISO date string to count down to (future) or since (past) */
  date: string;
  /** 'countdown' = future deadline, 'age' = time since event */
  mode?: 'countdown' | 'age';
  className?: string;
}

export function CountdownChip({ date, mode = 'countdown', className }: CountdownChipProps) {
  const now = Date.now();
  const target = new Date(date).getTime();
  const diffDays = Math.round((target - now) / 86400000);

  if (mode === 'age') {
    const ageDays = Math.abs(diffDays);
    if (ageDays < 7) return null;
    const label =
      ageDays >= 365 ? `${Math.floor(ageDays / 365)}y ago` :
      ageDays >= 30 ? `${Math.floor(ageDays / 30)}mo ago` :
      `${ageDays}d ago`;
    return (
      <span
        suppressHydrationWarning
        className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${className ?? ''}`}
        style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--bz-text-3)' }}
      >
        {label}
      </span>
    );
  }

  // Countdown mode
  const isOverdue = diffDays < 0;
  const absDays = Math.abs(diffDays);

  const chipColor =
    isOverdue ? 'bg-red-500/15 text-red-400' :
    diffDays === 0 ? 'bg-red-500/10 text-red-400' :
    diffDays <= 7 ? 'bg-red-500/10 text-red-400' :
    diffDays <= 30 ? 'bg-amber-500/10 text-amber-400' :
    diffDays <= 90 ? 'bg-amber-500/10 text-amber-400' :
    'bg-emerald-500/10 text-emerald-400';

  const label =
    isOverdue ? `${absDays}d overdue` :
    diffDays === 0 ? 'today' :
    diffDays === 1 ? 'tomorrow' :
    diffDays <= 365 ? `⏰ ${diffDays}d left` :
    `${Math.floor(diffDays / 30)}mo left`;

  return (
    <span
      suppressHydrationWarning
      className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${chipColor} ${className ?? ''}`}
      title={new Date(date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
    >
      {label}
    </span>
  );
}
