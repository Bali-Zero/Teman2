'use client';

import { PYLON_COLORS } from '@/lib/geo';

interface DataPylonProps {
  type: string;
  name: string;
  officialCount: number;
  hasAnomaly: boolean;
  x: number;
  y: number;
  onClick: () => void;
  delay?: number;
}

export function DataPylon({ type, name, officialCount, hasAnomaly, x, y, onClick, delay = 0 }: DataPylonProps) {
  const colors = PYLON_COLORS[type] ?? PYLON_COLORS.kanim;
  const beamColor = hasAnomaly ? 'var(--sg-copper)' : colors.beam;
  const pulseClass = hasAnomaly ? 'pylon-pulse-fast' : 'pylon-pulse';

  return (
    <div
      className="absolute cursor-pointer group"
      style={{ left: x, top: y, zIndex: 25, transform: 'translate(-50%, -100%)' }}
      onClick={onClick}
    >
      <div
        className="relative mx-auto"
        style={{
          width: 4,
          height: 120,
          background: `linear-gradient(to top, ${beamColor}, transparent)`,
          boxShadow: `0 0 20px ${beamColor}`,
          animation: `pylon-emerge 500ms ease-out both`,
          animationDelay: `${delay}ms`,
        }}
      >
        {hasAnomaly && (
          <>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="absolute w-1 h-1 rounded-full left-1/2 -translate-x-1/2"
                style={{
                  background: 'var(--sg-copper)',
                  bottom: `${i * 20}%`,
                  animation: `particle-ascend 1.5s ease-out infinite`,
                  animationDelay: `${i * 500}ms`,
                }}
              />
            ))}
          </>
        )}
      </div>

      <div
        className="w-10 h-10 rounded-full border mx-auto -mt-1 flex items-center justify-center"
        style={{
          borderColor: beamColor,
          background: colors.ring,
          animation: `${pulseClass} 2s ease-in-out infinite`,
        }}
      >
        <span className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-primary)]">
          {officialCount}
        </span>
      </div>

      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
        <div className="obsidian-glass rounded px-3 py-2">
          <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-primary)]">{name}</div>
          <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)]">{officialCount} officials</div>
        </div>
      </div>
    </div>
  );
}
