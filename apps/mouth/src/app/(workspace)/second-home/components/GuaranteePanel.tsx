import { AlertCircle, CalendarClock } from "lucide-react";
import type { GuaranteeInfo } from "@/lib/api/secondhome/secondhome.types";
import { severityColorVar, severityLabel } from "./severity";

export function GuaranteePanel({
  guarantee,
  hasEntryOrItasDate,
}: {
  guarantee: GuaranteeInfo | null;
  hasEntryOrItasDate: boolean;
}) {
  return (
    <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)] p-4 space-y-3">
      <h3 className="text-sm font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
        <CalendarClock className="w-4 h-4" />
        Day-90 Guarantee Gate
      </h3>

      {guarantee ? (
        <>
          <div className="flex items-baseline gap-2">
            <span
              className="text-lg font-bold"
              style={{
                color:
                  guarantee.days_remaining < 0
                    ? "var(--state-danger)"
                    : "var(--bz-text-1)",
              }}
            >
              {guarantee.days_remaining < 0
                ? `${Math.abs(guarantee.days_remaining)}d overdue`
                : `${guarantee.days_remaining}d remaining`}
            </span>
            <span className="text-xs text-[var(--bz-text-2)]">
              deadline {guarantee.deadline}
            </span>
          </div>
          {guarantee.alert_schedule.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-[var(--bz-text-2)] uppercase tracking-wide">
                Alert schedule
              </p>
              {guarantee.alert_schedule.map((milestone, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-[var(--bz-text-2)]">
                    {milestone.date}
                  </span>
                  <span
                    className="font-medium px-1.5 py-0.5 rounded-full"
                    style={{
                      color: severityColorVar(milestone.severity),
                      background: `color-mix(in srgb, ${severityColorVar(milestone.severity)} 12%, transparent)`,
                    }}
                  >
                    {severityLabel(milestone.severity)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <div className="flex gap-2 text-xs text-[var(--bz-text-2)]">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <p>
            {hasEntryOrItasDate
              ? "Guarantee deadline not yet computed."
              : "The Day-90 gate opens once the entry date or ITAS activation date is recorded — advance the case to Entry or ITAS Active to anchor it."}
          </p>
        </div>
      )}
    </div>
  );
}
