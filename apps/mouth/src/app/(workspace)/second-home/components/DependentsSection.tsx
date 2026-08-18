import Link from "next/link";
import { Users } from "lucide-react";
import type { DependentLinkView } from "@/lib/api/secondhome/secondhome.types";

export function DependentsSection({
  dependents,
  principalCaseId,
  dependentCode,
}: {
  dependents: DependentLinkView[];
  principalCaseId?: string | null;
  dependentCode?: string | null;
}) {
  return (
    <div className="rounded-xl border border-[var(--bz-border)] bg-[var(--bz-card)] p-4 space-y-3">
      <h3 className="text-sm font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
        <Users className="w-4 h-4" />
        Dependents
      </h3>

      {principalCaseId && dependentCode && (
        <p className="text-xs text-[var(--bz-text-2)]">
          This case is a{" "}
          <span className="font-medium text-[var(--bz-text-1)]">
            {dependentCode}
          </span>{" "}
          dependent of{" "}
          <Link
            href={`/second-home/${encodeURIComponent(principalCaseId)}`}
            className="text-[var(--bz-accent)] hover:underline font-mono"
          >
            {principalCaseId}
          </Link>
          .
        </p>
      )}

      {dependents.length === 0 ? (
        <p className="text-xs text-[var(--bz-text-2)]">
          No dependents linked to this case.
        </p>
      ) : (
        <div className="space-y-1.5">
          {dependents.map((dep, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between text-xs p-2 rounded-lg bg-[var(--bz-base)]/40"
            >
              <span className="text-[var(--bz-text-1)]">
                {dep.client_name || `Client #${dep.client_id}`}{" "}
                <span className="text-[var(--bz-text-2)]">
                  ({dep.relationship})
                </span>
              </span>
              <span className="font-mono text-[10px] text-[var(--bz-accent)]">
                {dep.code}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
