import { CheckCircle2, Circle } from "lucide-react";
import { STAGE_LABELS } from "@/lib/api/secondhome/state-machine";
import type {
  E33Stage,
  StageTransitionView,
} from "@/lib/api/secondhome/secondhome.types";

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function StageTimeline({
  history,
  currentStage,
}: {
  history: StageTransitionView[];
  currentStage: E33Stage;
}) {
  return (
    <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)] p-4 space-y-3">
      <h3 className="text-sm font-semibold text-[var(--bz-text-1)]">
        Lifecycle
      </h3>
      <div className="space-y-0">
        {history.length === 0 ? (
          <p className="text-xs text-[var(--bz-text-2)] py-2">
            No stage transitions recorded yet.
          </p>
        ) : (
          history.map((entry, idx) => (
            <div key={idx} className="flex gap-3 pb-4 last:pb-0">
              <div className="flex flex-col items-center">
                <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0" />
                {idx < history.length - 1 && (
                  <div className="w-px flex-1 bg-[var(--bz-border)] mt-1" />
                )}
              </div>
              <div className="pb-1">
                <p className="text-sm text-[var(--bz-text-1)]">
                  {entry.from_stage ? (
                    <>
                      {STAGE_LABELS[entry.from_stage]} →{" "}
                      <strong>{STAGE_LABELS[entry.to_stage]}</strong>
                    </>
                  ) : (
                    <>
                      Opened at <strong>{STAGE_LABELS[entry.to_stage]}</strong>
                    </>
                  )}
                </p>
                <p className="text-[10px] text-[var(--bz-text-2)]">
                  {formatDateTime(entry.at)}
                  {entry.actor ? ` · ${entry.actor}` : ""}
                </p>
                {entry.note && (
                  <p className="text-xs text-[var(--bz-text-2)] mt-0.5 italic">
                    “{entry.note}”
                  </p>
                )}
              </div>
            </div>
          ))
        )}
        <div className="flex gap-3">
          <Circle className="w-4 h-4 text-[var(--bz-accent)] fill-current shrink-0" />
          <p className="text-sm font-semibold text-[var(--bz-accent)]">
            Current: {STAGE_LABELS[currentStage]}
          </p>
        </div>
      </div>
    </div>
  );
}
