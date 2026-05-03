'use client';

import { formatRupiah } from '@/lib/format';
import type { OfficialData } from '@/lib/types';

interface OfficialNodeProps {
  official: OfficialData;
  x: number;
  y: number;
  selected: boolean;
  onClick: () => void;
  delay?: number;
}

export function OfficialNode({ official, x, y, selected, onClick, delay = 0 }: OfficialNodeProps) {
  const initials = official.name
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase();

  const borderColor = official.has_lhkpn ? 'var(--sg-copper)' : 'var(--sg-periwinkle)';
  const glowColor = official.anomaly ? 'var(--sg-copper-glow)' : official.has_lhkpn ? 'var(--sg-copper-dim)' : 'none';

  return (
    <div
      className="absolute cursor-pointer group"
      style={{
        left: x,
        top: y,
        transform: 'translate(-50%, -50%)',
        zIndex: selected ? 35 : 30,
        animation: `node-appear 400ms ease-out both`,
        animationDelay: `${delay}ms`,
      }}
      onClick={onClick}
    >
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center mx-auto transition-all relative"
        style={{
          border: `2px solid ${borderColor}`,
          background: 'var(--sg-base-deep)',
          boxShadow: selected
            ? `0 0 20px var(--sg-copper-glow), 0 0 40px var(--sg-copper-dim)`
            : official.anomaly
              ? `0 0 12px ${glowColor}`
              : 'none',
          animation: official.anomaly ? 'pylon-pulse 1.5s ease-in-out infinite' : undefined,
        }}
      >
        <span className="font-[family-name:var(--font-display)] text-[14px] font-semibold text-[var(--sg-text-primary)]">
          {initials}
        </span>

        {official.anomaly && (
          <div
            className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full"
            style={{ background: 'var(--sg-anomaly)' }}
          />
        )}
      </div>

      <div className="text-center mt-1.5 max-w-[120px]">
        <div className="font-[family-name:var(--font-display)] text-[11px] font-semibold text-[var(--sg-text-primary)] truncate">
          {official.name}
        </div>
        <div className="font-[family-name:var(--font-mono)] text-[9px] text-[var(--sg-text-ghost)] truncate">
          {official.jabatan}
        </div>
        {official.has_lhkpn && (
          <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-copper)] mt-0.5">
            {formatRupiah(official.total_assets)}
          </div>
        )}
      </div>
    </div>
  );
}
