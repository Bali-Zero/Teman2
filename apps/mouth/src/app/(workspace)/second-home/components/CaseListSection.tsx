"use client";

import { useRouter } from "next/navigation";
import { ChevronRight, ShieldCheck } from "lucide-react";
import {
  STAGE_GROUP_LABELS,
  STAGE_LABELS,
  type StageGroup,
} from "@/lib/api/secondhome/state-machine";
import type { CaseSummary } from "@/lib/api/secondhome/secondhome.types";

function daysUntil(dateIso: string): number {
  return Math.ceil((new Date(dateIso).getTime() - Date.now()) / 86400000);
}

function deadlineColor(days: number): string {
  if (days < 0) return "var(--state-danger)";
  if (days <= 7) return "var(--state-danger)";
  if (days <= 30) return "var(--state-warning)";
  return "var(--bz-text-2)";
}

function CaseRow({ item }: { item: CaseSummary }) {
  const router = useRouter();
  const deadlineDays = item.guarantee_proof_deadline
    ? daysUntil(item.guarantee_proof_deadline)
    : null;

  return (
    <button
      type="button"
      onClick={() =>
        router.push(`/second-home/${encodeURIComponent(item.case_id)}`)
      }
      className="w-full text-left p-3 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-card)] hover:bg-[var(--bz-card-hover)] transition-colors flex items-center justify-between gap-3"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-[var(--bz-text-1)] truncate">
            {item.client_name || "Unknown client"}
          </span>
          <span className="text-[10px] font-mono text-[var(--bz-text-2)]">
            {item.case_id}
          </span>
          {item.dependent_code && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium uppercase bg-[var(--bz-accent)]/10 text-[var(--bz-accent)]">
              {item.dependent_code} dependent
            </span>
          )}
          {item.stayguard_eligible && (
            <span
              className="text-[9px] px-1.5 py-0.5 rounded-full font-medium uppercase flex items-center gap-0.5"
              style={{
                background:
                  "color-mix(in srgb, var(--state-success) 15%, transparent)",
                color: "var(--state-success)",
              }}
              title="Guarantee evidence complete on an active permit — StayGuard-eligible"
            >
              <ShieldCheck className="w-2.5 h-2.5" />
              StayGuard
            </span>
          )}
        </div>
        <p className="text-xs text-[var(--bz-text-2)] mt-0.5">
          {STAGE_LABELS[item.stage]} ·{" "}
          {item.basis === "deposit" ? "Deposit route" : "Property route"}
          {item.owner_email ? ` · ${item.owner_email.split("@")[0]}` : ""}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {deadlineDays !== null && (
          <span
            className="text-[10px] font-medium"
            style={{ color: deadlineColor(deadlineDays) }}
            title={`Guarantee proof deadline: ${item.guarantee_proof_deadline}`}
          >
            {deadlineDays < 0
              ? `${Math.abs(deadlineDays)}d overdue`
              : `${deadlineDays}d to deadline`}
          </span>
        )}
        <ChevronRight className="w-4 h-4 text-[var(--bz-text-2)]" />
      </div>
    </button>
  );
}

export function CaseGroupSection({
  group,
  items,
}: {
  group: StageGroup;
  items: CaseSummary[];
}) {
  return (
    <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)]/40 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-[var(--bz-text-2)]">
          {STAGE_GROUP_LABELS[group]}
        </h3>
        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--surface-raised)] text-[var(--bz-text-2)]">
          {items.length}
        </span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-[var(--bz-text-2)] py-4 text-center">
          No cases in this group
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <CaseRow key={item.case_id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
