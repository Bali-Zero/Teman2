'use client';

interface ConnectionLineProps {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  type: string;
  highlighted: boolean;
  delay?: number;
}

export function ConnectionLine({ x1, y1, x2, y2, type, highlighted, delay = 0 }: ConnectionLineProps) {
  const color = type === 'SUPERVISES' ? 'var(--sg-copper)' : 'var(--sg-periwinkle)';
  const width = type === 'SUPERVISES' ? 1.5 : 1;
  const dash = type !== 'SUPERVISES' ? '4 4' : 'none';

  const offset = (x2 - x1) * 0.15;
  const path = `M ${x1} ${y1} C ${x1 + offset} ${y1}, ${x2 - offset} ${y2}, ${x2} ${y2}`;

  return (
    <path
      d={path}
      fill="none"
      stroke={color}
      strokeWidth={width}
      strokeDasharray={dash}
      opacity={highlighted ? 0.8 : 0.3}
      style={{
        strokeDashoffset: 1000,
        animation: `draw-line 800ms ease-out ${delay}ms both`,
      }}
    />
  );
}
