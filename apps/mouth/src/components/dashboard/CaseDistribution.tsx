import React from "react";

interface Segment {
  label: string;
  value: number;
  color: string;
}

interface CaseDistributionProps {
  segments: Segment[];
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export const CaseDistribution = React.memo(function CaseDistribution({
  segments,
  size = 120,
  strokeWidth = 16,
  className = "",
}: CaseDistributionProps) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  if (total === 0) return null;

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const center = size / 2;

  let cumulativeOffset = 0;

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {segments.map((segment) => {
          const fraction = segment.value / total;
          const dashLength = fraction * circumference;
          const dashGap = circumference - dashLength;
          const offset = cumulativeOffset;
          cumulativeOffset += dashLength;

          return (
            <circle
              key={segment.label}
              cx={center}
              cy={center}
              r={radius}
              fill="none"
              stroke={segment.color}
              strokeWidth={strokeWidth}
              strokeDasharray={`${dashLength} ${dashGap}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
              transform={`rotate(-90 ${center} ${center})`}
              className="transition-all duration-700 ease-out"
            />
          );
        })}
        {/* Center text */}
        <text
          x={center}
          y={center - 4}
          textAnchor="middle"
          className="fill-[var(--foreground)] text-lg font-bold"
          fontSize="18"
        >
          {total}
        </text>
        <text
          x={center}
          y={center + 12}
          textAnchor="middle"
          className="fill-[var(--foreground-muted)] text-[10px]"
          fontSize="10"
        >
          total
        </text>
      </svg>

      {/* Legend */}
      <div className="flex flex-col gap-1.5">
        {segments
          .filter((s) => s.value > 0)
          .map((segment) => (
            <div key={segment.label} className="flex items-center gap-2">
              <div
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: segment.color }}
              />
              <span className="text-xs text-[var(--foreground-muted)] whitespace-nowrap">
                {segment.label}
              </span>
              <span className="text-xs font-medium text-[var(--foreground)] ml-auto">
                {segment.value}
              </span>
            </div>
          ))}
      </div>
    </div>
  );
});
