"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo } from "react";

const MONTH_LABELS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

interface MonthPillTabsProps {
  selectedMonth: string;
  onMonthChange: (month: string) => void;
}

function parseMonth(month: string): { year: number; month: number } {
  const [y, m] = month.split("-").map(Number);
  return { year: y, month: m };
}

function formatMonth(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function addMonths(month: string, delta: number): string {
  const { year, month: m } = parseMonth(month);
  const total = year * 12 + (m - 1) + delta;
  const newYear = Math.floor(total / 12);
  const newMonth = (total % 12) + 1;
  return formatMonth(newYear, newMonth);
}

export function MonthPillTabs({
  selectedMonth,
  onMonthChange,
}: MonthPillTabsProps) {
  const now = new Date();
  const currentMonth = formatMonth(now.getFullYear(), now.getMonth() + 1);

  const visibleMonths = useMemo(() => {
    const totalSelected =
      parseMonth(selectedMonth).year * 12 +
      (parseMonth(selectedMonth).month - 1);
    const totalCurrent = now.getFullYear() * 12 + now.getMonth();

    let startTotal = totalSelected - 2;
    const endTotal = startTotal + 4;

    if (endTotal > totalCurrent + 2) {
      startTotal = totalCurrent + 2 - 4;
    }

    const months: string[] = [];
    for (let i = 0; i < 5; i++) {
      const t = startTotal + i;
      const y = Math.floor(t / 12);
      const m = (t % 12) + 1;
      months.push(formatMonth(y, m));
    }
    return months;
  }, [selectedMonth]);

  const isFuture = (m: string) => m > currentMonth;

  return (
    <div className="flex items-center gap-1 p-1 bg-[rgba(32,32,36,0.5)] backdrop-blur-md border border-[rgba(255,255,255,0.05)] rounded-xl w-fit shadow-xl">
      <button
        onClick={() => onMonthChange(addMonths(selectedMonth, -1))}
        className="p-1.5 text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors rounded-lg hover:bg-[rgba(255,255,255,0.05)]"
        aria-label="Previous month"
      >
        <ChevronLeft className="w-3.5 h-3.5" />
      </button>

      {visibleMonths.map((m) => {
        const { month: mNum } = parseMonth(m);
        const isSelected = m === selectedMonth;
        const future = isFuture(m);

        return (
          <button
            key={m}
            onClick={() => !future && onMonthChange(m)}
            disabled={future}
            className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
              isSelected
                ? "bg-gradient-to-br from-[var(--bz-accent-warm)] to-[rgba(212,132,90,0.8)] text-white shadow-lg shadow-[rgba(212,132,90,0.3)]"
                : future
                  ? "text-[var(--bz-text-2)]/30 cursor-not-allowed"
                  : "text-[var(--bz-text-2)] hover:bg-[rgba(255,255,255,0.05)] hover:text-[var(--bz-text-1)]"
            }`}
          >
            {MONTH_LABELS[mNum - 1]}
          </button>
        );
      })}

      <button
        onClick={() => {
          const next = addMonths(selectedMonth, 1);
          if (!isFuture(next)) onMonthChange(next);
        }}
        disabled={isFuture(addMonths(selectedMonth, 1))}
        className="p-1.5 text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors rounded-lg hover:bg-[rgba(255,255,255,0.05)] disabled:opacity-30 disabled:cursor-not-allowed"
        aria-label="Next month"
      >
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
