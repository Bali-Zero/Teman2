import React from "react";
import Link from "next/link";
import { ChevronRight, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

export interface CasePreview {
  id: number;
  title: string;
  client: string;
  status: "inquiry" | "quotation" | "in_progress" | "documents" | "completed";
  daysRemaining?: number;
  completedAt?: string;
}

interface CasesPreviewProps {
  cases: CasePreview[];
  isLoading?: boolean;
}

const statusConfig = {
  inquiry: {
    label: "Inquiry",
    color: "text-[var(--foreground-muted)]",
    bg: "bg-[var(--foreground-muted)]/10",
    dot: "bg-[var(--foreground-muted)]",
  },
  quotation: {
    label: "Quotation",
    color: "text-[var(--warning)]",
    bg: "bg-[var(--warning)]/10",
    dot: "bg-[var(--warning)]",
  },
  in_progress: {
    label: "In Progress",
    color: "text-[var(--accent)]",
    bg: "bg-[var(--accent)]/10",
    dot: "bg-[var(--accent)]",
  },
  documents: {
    label: "Documents",
    color: "text-[var(--warning)]",
    bg: "bg-[var(--warning)]/10",
    dot: "bg-[var(--warning)]",
  },
  completed: {
    label: "Completed",
    color: "text-[var(--success)]",
    bg: "bg-[var(--success)]/10",
    dot: "bg-[var(--success)]",
  },
};

export function CasesPreview({ cases, isLoading }: CasesPreviewProps) {
  if (isLoading) {
    return (
      <div className="glass-card-warm p-5 rounded-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="h-5 w-32 bg-[var(--background-elevated)] rounded animate-pulse" />
          <div className="h-4 w-20 bg-[var(--background-elevated)] rounded animate-pulse" />
        </div>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 bg-[var(--background-elevated)]/50 rounded-lg animate-pulse"
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card-warm p-5 rounded-xl">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-[var(--foreground)]">
          My Process
        </h2>
        <Link
          href="/process"
          className="text-sm text-[var(--accent)] hover:text-[var(--accent-hover)] transition-colors flex items-center gap-1"
        >
          All
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="space-y-2">
        {cases.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--foreground-muted)]">
              No process assigned
            </p>
          </div>
        ) : (
          cases.map((caseItem) => {
            const config = statusConfig[caseItem.status];
            return (
              <Link
                key={caseItem.id}
                href={`/process/${caseItem.id}`}
                className="block p-3 rounded-lg border border-[var(--border)] hover:border-[var(--border-hover)] hover:bg-[var(--background-elevated)]/30 transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--foreground)] truncate">
                      {caseItem.title}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)] truncate">
                      {caseItem.client}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <span
                      className={cn(
                        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium",
                        config.bg,
                        config.color,
                      )}
                    >
                      <span
                        className={cn("w-1.5 h-1.5 rounded-full", config.dot)}
                      />
                      {config.label}
                    </span>
                    {caseItem.status !== "completed" &&
                      caseItem.daysRemaining !== undefined && (
                        <span
                          className={cn(
                            "text-xs flex items-center gap-1",
                            caseItem.daysRemaining <= 0
                              ? "text-[var(--error)]"
                              : caseItem.daysRemaining <= 3
                                ? "text-[var(--error)]"
                                : caseItem.daysRemaining <= 7
                                  ? "text-[var(--warning)]"
                                  : "text-[var(--foreground-muted)]",
                          )}
                        >
                          <Clock className="w-3 h-3" />
                          {caseItem.daysRemaining <= 0
                            ? "Expired"
                            : `${caseItem.daysRemaining}d`}
                        </span>
                      )}
                    {caseItem.status === "completed" && caseItem.completedAt && (
                      <span className="text-xs text-[var(--foreground-muted)]">
                        {caseItem.completedAt}
                      </span>
                    )}
                  </div>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}
