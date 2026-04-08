"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Send, Calendar, ChevronLeft, ChevronRight } from "lucide-react";
import * as hrApi from "@/lib/api/hr/hr";
import type { LeaveTypeOption } from "@/lib/api/hr/hr";

// ─── Mini Calendar Component ───────────────────────────────────────────────
const DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function MiniCalendar({
  value,
  onChange,
  minDate,
}: {
  value: string;
  onChange: (date: string) => void;
  minDate?: string;
}) {
  const today = new Date();
  const selected = value ? new Date(value + "T00:00:00") : null;
  const [viewMonth, setViewMonth] = useState(
    selected ? selected.getMonth() : today.getMonth(),
  );
  const [viewYear, setViewYear] = useState(
    selected ? selected.getFullYear() : today.getFullYear(),
  );

  const firstDay = new Date(viewYear, viewMonth, 1);
  // Monday = 0, Sunday = 6
  const startOffset = (firstDay.getDay() + 6) % 7;
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

  const minD = minDate ? new Date(minDate + "T00:00:00") : null;

  const cells: (number | null)[] = [];
  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(d);

  const prevMonth = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear(viewYear - 1);
    } else {
      setViewMonth(viewMonth - 1);
    }
  };

  const nextMonth = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear(viewYear + 1);
    } else {
      setViewMonth(viewMonth + 1);
    }
  };

  const handleClick = (day: number) => {
    const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    if (minD) {
      const clicked = new Date(dateStr + "T00:00:00");
      if (clicked < minD) return;
    }
    onChange(dateStr);
  };

  const isSelected = (day: number) => {
    if (!selected) return false;
    return (
      selected.getFullYear() === viewYear &&
      selected.getMonth() === viewMonth &&
      selected.getDate() === day
    );
  };

  const isToday = (day: number) =>
    today.getFullYear() === viewYear &&
    today.getMonth() === viewMonth &&
    today.getDate() === day;

  const isDisabled = (day: number) => {
    if (!minD) return false;
    const d = new Date(viewYear, viewMonth, day);
    return d < minD;
  };

  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-3 w-[280px] shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <button
          type="button"
          onClick={prevMonth}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="text-sm font-medium text-zinc-200">
          {MONTHS[viewMonth]} {viewYear}
        </span>
        <button
          type="button"
          onClick={nextMonth}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 mb-1">
        {DAYS.map((d) => (
          <div
            key={d}
            className="text-[10px] text-zinc-500 text-center font-medium py-1"
          >
            {d}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <div className="grid grid-cols-7">
        {cells.map((day, i) => {
          if (day === null) {
            return <div key={`empty-${i}`} className="h-8" />;
          }
          const disabled = isDisabled(day);
          const sel = isSelected(day);
          const tod = isToday(day);
          return (
            <button
              key={day}
              type="button"
              disabled={disabled}
              onClick={() => handleClick(day)}
              className={`h-8 w-8 mx-auto rounded-full text-xs font-medium transition-colors ${
                sel
                  ? "bg-[var(--bz-accent)] text-zinc-950"
                  : tod
                    ? "bg-zinc-800 text-[var(--bz-accent)]"
                    : disabled
                      ? "text-zinc-700 cursor-not-allowed"
                      : "text-zinc-300 hover:bg-zinc-800"
              }`}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Date Input with Calendar Dropdown ──────────────────────────────────────
function DateInput({
  label,
  value,
  onChange,
  minDate,
}: {
  label: string;
  value: string;
  onChange: (date: string) => void;
  minDate?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const formatDisplay = (dateStr: string) => {
    if (!dateStr) return "";
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  };

  return (
    <div ref={ref} className="relative">
      <label className="block text-sm text-zinc-400 mb-1">{label}</label>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-left text-zinc-200 flex items-center justify-between hover:border-zinc-500 transition-colors"
      >
        <span className={value ? "text-zinc-200" : "text-zinc-500"}>
          {value ? formatDisplay(value) : "Select date"}
        </span>
        <Calendar size={16} className="text-zinc-500" />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 left-0">
          <MiniCalendar
            value={value}
            minDate={minDate}
            onChange={(date) => {
              onChange(date);
              setOpen(false);
            }}
          />
        </div>
      )}
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────────────────────────────
export default function LeaveRequestPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    leave_type_id: 0,
    start_date: "",
    end_date: "",
    total_days: 1,
    reason: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [leaveTypes, setLeaveTypes] = useState<LeaveTypeOption[]>([]);
  const [loadingTypes, setLoadingTypes] = useState(true);

  useEffect(() => {
    hrApi
      .getLeaveTypes()
      .then((res) => {
        const types = res.leave_types ?? [];
        setLeaveTypes(types);
        if (types.length > 0) {
          setForm((prev) => ({ ...prev, leave_type_id: types[0].id }));
        }
      })
      .catch((err) =>
        setError(
          err instanceof Error ? err.message : "Failed to load leave types",
        ),
      )
      .finally(() => setLoadingTypes(false));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.leave_type_id) {
      setError("Please select a leave type");
      return;
    }
    if (!form.start_date || !form.end_date) {
      setError("Please select start and end dates");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await hrApi.requestLeave(form);
      router.push("/hr/leave");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit");
    } finally {
      setSubmitting(false);
    }
  };

  const updateDays = useCallback((start: string, end: string) => {
    if (start && end) {
      const diff =
        Math.ceil(
          (new Date(end + "T00:00:00").getTime() -
            new Date(start + "T00:00:00").getTime()) /
            (1000 * 60 * 60 * 24),
        ) + 1;
      return Math.max(1, diff);
    }
    return 1;
  }, []);

  const setStartDate = (date: string) => {
    const endDate = form.end_date && form.end_date < date ? date : form.end_date;
    setForm((prev) => ({
      ...prev,
      start_date: date,
      end_date: endDate,
      total_days: updateDays(date, endDate),
    }));
  };

  const setEndDate = (date: string) => {
    setForm((prev) => ({
      ...prev,
      end_date: date,
      total_days: updateDays(prev.start_date, date),
    }));
  };

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-zinc-100 mb-6">Request Leave</h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm text-zinc-400 mb-1">Leave Type</label>
          <select
            value={form.leave_type_id}
            onChange={(e) =>
              setForm((prev) => ({
                ...prev,
                leave_type_id: Number(e.target.value),
              }))
            }
            disabled={loadingTypes || leaveTypes.length === 0}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-200 disabled:opacity-50"
          >
            {loadingTypes ? (
              <option value={0}>Loading...</option>
            ) : leaveTypes.length === 0 ? (
              <option value={0}>No leave types available</option>
            ) : (
              leaveTypes.map((lt) => (
                <option key={lt.id} value={lt.id}>
                  {lt.name}
                  {lt.default_days > 0 ? ` (${lt.default_days}d/yr)` : ""}
                </option>
              ))
            )}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <DateInput
            label="Start Date"
            value={form.start_date}
            onChange={setStartDate}
          />
          <DateInput
            label="End Date"
            value={form.end_date}
            onChange={setEndDate}
            minDate={form.start_date || undefined}
          />
        </div>

        <div>
          <label className="block text-sm text-zinc-400 mb-1">
            Total Days:{" "}
            <span className="text-zinc-200 font-medium">{form.total_days}</span>
          </label>
        </div>

        <div>
          <label className="block text-sm text-zinc-400 mb-1">
            Reason (optional)
          </label>
          <textarea
            value={form.reason}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, reason: e.target.value }))
            }
            rows={3}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-200"
            placeholder="Why do you need this leave?"
          />
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting || leaveTypes.length === 0}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bz-accent)] text-zinc-950 hover:opacity-90 text-sm font-medium transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Send size={16} />
          {submitting ? "Submitting..." : "Submit Request"}
        </button>
      </form>
    </div>
  );
}
