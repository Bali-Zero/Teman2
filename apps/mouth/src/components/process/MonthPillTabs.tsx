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
    <div className="flex w-fit items-center gap-1 rounded-[var(--bz-product-radius-sm)] border border-[var(--bz-border)] bg-[var(--bz-card)] p-1 shadow-[var(--bz-shadow-card)]">
      <button
        type="button"
        onClick={() => onMonthChange(addMonths(selectedMonth, -1))}
        className="rounded-lg p-1.5 text-[var(--bz-text-2)] transition-colors hover:bg-[var(--bz-surface)] hover:text-[var(--bz-text-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-focus-ring)]"
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
            type="button"
            key={m}
            onClick={() => !future && onMonthChange(m)}
            disabled={future}
            className={`rounded-lg px-3 py-1 text-xs font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-focus-ring)] ${
              isSelected
                ? "bg-[var(--bz-accent)] text-white shadow-sm"
                : future
                  ? "cursor-not-allowed text-[var(--bz-text-2)] opacity-40"
                  : "text-[var(--bz-text-2)] hover:bg-[var(--bz-surface)] hover:text-[var(--bz-text-1)]"
            }`}
          >
            {MONTH_LABELS[mNum - 1]}
          </button>
        );
      })}

      <button
        type="button"
        onClick={() => {
          const next = addMonths(selectedMonth, 1);
          if (!isFuture(next)) onMonthChange(next);
        }}
        disabled={isFuture(addMonths(selectedMonth, 1))}
        className="rounded-lg p-1.5 text-[var(--bz-text-2)] transition-colors hover:bg-[var(--bz-surface)] hover:text-[var(--bz-text-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-focus-ring)] disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Next month"
      >
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
