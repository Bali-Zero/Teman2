"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/error-handler";
import type { components } from "@/lib/api/schema";
import { cn } from "@/lib/utils";
import {
  EmptyState,
  FOCUS,
  Masthead,
  Notice,
  StatePill,
} from "@/components/workspace/r19";

type Obligations = components["schemas"]["MemberObligationsOut"];
type Duty = components["schemas"]["MemberObligation"];
type Scope = "mine" | "team";
const LIMIT = 50;
const BUTTON = cn(
  "rounded border border-[var(--bz-border)] px-3 py-2 text-sm text-[var(--bz-text-1)] disabled:opacity-50",
  FOCUS,
);

function passportTiming(days: number): string {
  if (days < 0) return `Expired ${Math.abs(days)} days ago`;
  if (days === 0) return "Expires today";
  return `Expires in ${days} days`;
}

function dutyDescription(duty: Duty): string {
  if (duty.kind === "process") {
    return `Open for ${duty.age_days} days · ${duty.practice_type_name ?? "Process"}`;
  }
  const expiry = new Date(
    `${duty.passport_expiry}T00:00:00`,
  ).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  return `${passportTiming(duty.days_left ?? 0)} · ${expiry}`;
}

export default function MemberObligationsPage() {
  const [scope, setScope] = useState<Scope>("mine");
  const [owner, setOwner] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<Obligations | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    const query = new URLSearchParams({
      scope,
      limit: String(LIMIT),
      offset: String(offset),
    });
    if (owner) query.set("assigned_to", owner);
    try {
      const result = await api.get<Obligations>(
        `/api/crm/member-obligations?${query}`,
      );
      if (id !== requestId.current) return;
      if (offset > 0 && result.items.length === 0 && result.total <= offset) {
        setOffset(0);
        return;
      }
      setData(result);
    } catch (failure) {
      if (id !== requestId.current) return;
      setData(null);
      setError(
        failure instanceof ApiError && failure.statusCode === 403
          ? "You do not have access to this overview."
          : "Could not load obligations. Please try again.",
      );
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [scope, owner, offset]);

  useEffect(() => {
    void load();
    const onFocus = () => {
      if (document.visibilityState === "visible") void load();
    };
    window.addEventListener("focus", onFocus);
    return () => {
      requestId.current += 1;
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);

  function changeScope(next: Scope) {
    if (next === scope) return;
    setLoading(true);
    setOwner("");
    setOffset(0);
    setScope(next);
  }

  return (
    <div className="space-y-5 p-4 md:p-6">
      <Masthead
        eyebrow="Operations"
        title="Obligations"
        sub="Follow up on passports and review open processes. Update the original record to clear an item."
        actions={
          <button
            className={BUTTON}
            onClick={() => void load()}
            disabled={loading}
          >
            Refresh
          </button>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        <div
          role="group"
          aria-label="Obligation scope"
          className="flex flex-wrap gap-2"
        >
          <StatePill
            tone="you"
            label="My obligations"
            pressed={scope === "mine"}
            onClick={() => changeScope("mine")}
          />
          {(data?.can_view_team || scope === "team") && (
            <StatePill
              tone="ink"
              label="Team overview"
              pressed={scope === "team"}
              onClick={() => changeScope("team")}
            />
          )}
        </div>
        {scope === "team" && data && (
          <select
            aria-label="Team member"
            className={BUTTON}
            value={owner}
            onChange={(event) => {
              setLoading(true);
              setOwner(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All team members</option>
            {owner &&
              !data.owners.some(
                (member) => (member.email ?? "__unassigned__") === owner,
              ) && (
                <option value={owner}>
                  {owner === "__unassigned__" ? "Unassigned" : owner} (0)
                </option>
              )}
            {data.owners.map((member) => (
              <option
                key={member.email ?? "__unassigned__"}
                value={member.email ?? "__unassigned__"}
              >
                {member.name} ({member.total})
              </option>
            ))}
          </select>
        )}
        {data?.can_view_register && (
          <Link
            className={cn(
              "text-sm underline text-[var(--bz-text-2)] md:ml-auto",
              FOCUS,
            )}
            href="/obligations/register"
          >
            Compliance register
          </Link>
        )}
      </div>

      {error ? (
        <Notice role="alert">{error}</Notice>
      ) : loading ? (
        <p role="status" className="text-sm text-[var(--bz-text-2)]">
          Loading obligations…
        </p>
      ) : (
        data && (
          <>
            <div className="grid grid-cols-3 gap-3 border-y border-[var(--bz-border)] py-4">
              {[
                ["To review", data.total],
                ["Passports", data.passport_count],
                ["Processes", data.process_count],
              ].map(([label, count]) => (
                <div key={label}>
                  <p className="text-xs text-[var(--bz-text-2)]">{label}</p>
                  <p
                    aria-label={`${label}: ${count}`}
                    className="text-2xl tabular-nums text-[var(--bz-text-1)]"
                  >
                    {count}
                  </p>
                </div>
              ))}
            </div>
            {data.items.length === 0 ? (
              <EmptyState>
                {scope === "mine"
                  ? "No obligations need your attention."
                  : "No obligations need attention for this selection."}
              </EmptyState>
            ) : (
              <ul
                aria-label="Obligations to review"
                className="divide-y divide-[var(--bz-border)]"
              >
                {data.items.map((duty) => {
                  const member = data.owners.find(
                    (entry) => entry.email === duty.assigned_to,
                  );
                  const canOpen =
                    duty.kind === "passport" || duty.can_open_process;
                  const href =
                    duty.kind === "passport"
                      ? `/clients/${duty.client_id}?tab=overview`
                      : `/process/${duty.practice_id}`;
                  return (
                    <li
                      key={`${duty.kind}:${duty.practice_id ?? duty.client_id}`}
                      className="flex flex-col gap-3 py-5 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <StatePill
                            tone="wait"
                            label={
                              duty.kind === "passport"
                                ? "Passport"
                                : "Process review"
                            }
                          />
                          <span className="text-xs text-[var(--bz-text-2)]">
                            {dutyDescription(duty)}
                          </span>
                        </div>
                        <p className="break-words font-medium text-[var(--bz-text-1)]">
                          {duty.client_name}
                        </p>
                        <p className="text-sm text-[var(--bz-text-2)]">
                          {duty.kind === "passport"
                            ? "Contact the client or update their passport."
                            : "Review in Process: complete it if finished, or cancel it if it will not proceed."}
                        </p>
                        {scope === "team" && (
                          <p className="text-xs text-[var(--bz-text-2)]">
                            Responsible:{" "}
                            {member?.name ?? duty.assigned_to ?? "Unassigned"}
                          </p>
                        )}
                      </div>
                      {canOpen ? (
                        <Link
                          href={href}
                          className={cn(
                            BUTTON,
                            "shrink-0 self-start sm:self-center",
                          )}
                        >
                          {duty.kind === "passport"
                            ? "Open client"
                            : "Open process"}
                        </Link>
                      ) : (
                        <span className="text-xs text-[var(--bz-text-2)]">
                          Review with the responsible team member
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {data.total > LIMIT && (
              <nav
                aria-label="Obligation pages"
                className="flex items-center justify-between gap-3"
              >
                <button
                  className={BUTTON}
                  disabled={offset === 0}
                  onClick={() => {
                    setLoading(true);
                    setOffset(Math.max(0, offset - LIMIT));
                  }}
                >
                  Previous
                </button>
                <span className="text-sm text-[var(--bz-text-2)]">
                  {offset + 1}–{Math.min(offset + LIMIT, data.total)} of{" "}
                  {data.total}
                </span>
                <button
                  className={BUTTON}
                  disabled={offset + LIMIT >= data.total}
                  onClick={() => {
                    setLoading(true);
                    setOffset(offset + LIMIT);
                  }}
                >
                  Next
                </button>
              </nav>
            )}
          </>
        )
      )}
    </div>
  );
}
