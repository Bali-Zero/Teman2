"use client";

import { useState, type FormEvent } from "react";
import { ArrowRightCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import { toError } from "@/lib/types/common";
import { ApiError } from "@/lib/api/error-handler";
import { STAGE_LABELS } from "@/lib/api/secondhome/state-machine";
import type { E33Stage } from "@/lib/api/secondhome/secondhome.types";
import { useAdvanceSecondHomeCase } from "@/hooks/useSecondHome";

/**
 * Advance-stage control. `allowedNextStages` comes from the CaseDetail
 * response's own `allowed_next_stages` field — the SERVER list is
 * authoritative (already excludes itap_eval while the flag is off); this
 * component does not recompute it from the local state-machine mirror.
 */
export function TransitionControl({
  caseId,
  currentStage,
  allowedNextStages,
}: {
  caseId: string;
  currentStage: E33Stage;
  allowedNextStages: E33Stage[];
}) {
  const toast = useToast();
  const advance = useAdvanceSecondHomeCase(caseId);
  const [toStage, setToStage] = useState<string>("");
  const [note, setNote] = useState("");
  const [occurredOn, setOccurredOn] = useState("");

  // Defensive filter — the server list is authoritative and already
  // excludes itap_eval, but never render it even if it slipped through.
  const offeredStages = allowedNextStages.filter((s) => s !== "itap_eval");

  if (offeredStages.length === 0) {
    return (
      <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)] p-4">
        <h3 className="text-sm font-semibold text-[var(--bz-text-1)] mb-1">
          Advance Stage
        </h3>
        <p className="text-xs text-[var(--bz-text-2)]">
          {STAGE_LABELS[currentStage]} is a terminal stage — no further
          transitions.
        </p>
      </div>
    );
  }

  const handleAdvance = async (e: FormEvent) => {
    e.preventDefault();
    if (!toStage) return;
    try {
      await advance.mutateAsync({
        to_stage: toStage as E33Stage,
        note: note || undefined,
        occurred_on: occurredOn || undefined,
      });
      toast.success(
        "Stage Advanced",
        `Case moved to ${STAGE_LABELS[toStage as E33Stage]}.`,
      );
      setToStage("");
      setNote("");
      setOccurredOn("");
    } catch (error) {
      logger.error(
        "Failed to advance second-home case",
        { component: "TransitionControl", action: "advance", itemId: caseId },
        toError(error),
      );
      // Surface the 409/422 detail verbatim — it names the allowed set or
      // the itap_eval gate reason.
      const message =
        error instanceof ApiError
          ? error.detail || error.message
          : "Failed to advance stage";
      toast.error("Error", message);
    }
  };

  const needsOccurredOn = toStage === "entry" || toStage === "itas_active";

  return (
    <form
      onSubmit={handleAdvance}
      className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)] p-4 space-y-3"
    >
      <h3 className="text-sm font-semibold text-[var(--bz-text-1)]">
        Advance Stage
      </h3>
      <div className="space-y-2">
        <select
          value={toStage}
          onChange={(e) => setToStage(e.target.value)}
          className="w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50"
        >
          <option value="">-- Select next stage --</option>
          {offeredStages.map((stage) => (
            <option key={stage} value={stage}>
              {STAGE_LABELS[stage]}
            </option>
          ))}
        </select>
        {needsOccurredOn && (
          <div>
            <label className="text-xs text-[var(--bz-text-2)] block mb-1">
              {toStage === "entry" ? "Entry date" : "ITAS activation date"}{" "}
              <span className="text-[var(--bz-text-2)]">
                (defaults to today if left blank — anchors the Day-90 gate)
              </span>
            </label>
            <input
              type="date"
              value={occurredOn}
              onChange={(e) => setOccurredOn(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50"
            />
          </div>
        )}
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional)"
          rows={2}
          className="w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-2)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50 resize-none"
        />
      </div>
      <Button
        type="submit"
        disabled={!toStage || advance.isPending}
        className="w-full gap-2 bg-[var(--bz-accent)] text-[var(--accent-foreground)] hover:bg-[var(--bz-accent)]/90"
      >
        {advance.isPending ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <ArrowRightCircle className="w-4 h-4" />
        )}
        Advance
      </Button>
    </form>
  );
}
