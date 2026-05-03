import React from "react";

interface DataPoint {
  label: string;
  value: number;
  color?: string;
}

interface MiniBarChartProps {
  data: DataPoint[];
  height?: number;
  showLabels?: boolean;
  className?: string;
}

export const MiniBarChart = React.memo(function MiniBarChart({
  data,
  height = 80,
  showLabels = true,
  className = "",
}: MiniBarChartProps) {
  const maxValue = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className={`flex items-end gap-1 ${className}`} style={{ height }}>
      {data.map((point, i) => {
        const barHeight = (point.value / maxValue) * 100;
        return (
          <div
            key={point.label}
            className="flex-1 flex flex-col items-center justify-end gap-1 group relative"
          >
            {/* Tooltip */}
            <div className="absolute bottom-full mb-1 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
              <div className="bg-black/90 text-white text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap">
                {point.value}
              </div>
            </div>
            {/* Bar */}
            <div
              className="w-full rounded-t transition-all duration-500 ease-out min-h-[2px]"
              style={{
                height: `${barHeight}%`,
                backgroundColor:
                  point.color || "var(--accent, hsl(210, 100%, 60%))",
                opacity: 0.7 + (i / data.length) * 0.3,
              }}
            />
            {showLabels && (
              <span className="text-[9px] text-[var(--foreground-muted)] truncate w-full text-center leading-none">
                {point.label}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
});
