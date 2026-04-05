interface QuestionCounterProps {
  remaining: number;
}

export function QuestionCounter({ remaining }: QuestionCounterProps) {
  if (remaining <= 0) return null;

  const MAX = 3;

  return (
    <div className="flex items-center gap-2" style={{ color: 'var(--tx-secondary)' }}>
      {/* Dots */}
      <div className="flex items-center gap-1">
        {Array.from({ length: MAX }).map((_, i) => (
          <span
            key={i}
            className="w-2 h-2 rounded-full inline-block"
            style={{
              backgroundColor: i < remaining ? 'var(--bz-accent)' : 'rgba(255,255,255,0.15)',
              transition: 'background-color 0.2s ease',
            }}
          />
        ))}
      </div>

      {/* Label */}
      <span className="text-xs">
        {remaining} question{remaining !== 1 ? 's' : ''} remaining
      </span>
    </div>
  );
}
