/**
 * /cockpit/wr2 — READ-ONLY WR2 drafts table.
 *
 * Latest 30 war_room_drafts with status filter dropdown. NO approve/reject,
 * NO subprocess spawn, NO intent emission. Polling 30s.
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import BrandTopbar from "@/components/cockpit/BrandTopbar";
import PinGate from "@/components/cockpit/PinGate";
import WidgetFrame from "@/components/cockpit/WidgetFrame";

interface DraftRow {
  id: string;
  topic: string | null;
  status: string | null;
  register: string | null;
  updated_at: string | null;
  lease_owner: string | null;
}

interface DraftsResponse {
  count: number;
  items: DraftRow[];
  error?: string;
}

const ALL = "__all__";

function formatDate(s: string | null): string {
  if (!s) return "—";
  // PG returns "2026-05-18 02:30:00+00" — display short ISO-ish.
  return s.replace(/\.\d+/, "").replace("T", " ").slice(0, 19);
}

export default function CockpitWR2Page() {
  const [data, setData] = useState<DraftsResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>(ALL);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function tick() {
      try {
        const res = await fetch("/api/cockpit/wr2/drafts", {
          credentials: "include",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const j = (await res.json()) as DraftsResponse;
        if (!cancelled) {
          setData(j);
          setError(j.error ?? "");
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    tick();
    timer = setInterval(tick, 30_000);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  const allStatuses = useMemo(() => {
    const s = new Set<string>();
    for (const r of data?.items ?? []) {
      if (r.status) s.add(r.status);
    }
    return Array.from(s).sort();
  }, [data]);

  const visible = useMemo(() => {
    const items = data?.items ?? [];
    if (statusFilter === ALL) return items;
    return items.filter((r) => r.status === statusFilter);
  }, [data, statusFilter]);

  return (
    <PinGate>
      <BrandTopbar tagline="— WR2 read-only">
        <span>
          <strong>{visible.length}</strong>/{data?.count ?? 0} shown
        </span>
        <span>refresh every 30s</span>
      </BrandTopbar>

      <main>
        <div className="cockpit-breadcrumb">
          <Link href="/cockpit">Cockpit</Link> · WR2
        </div>
        <h1 className="cockpit-page-heading">WR2 — Editorial Drafts</h1>
        <p style={{ color: "var(--text-muted)", marginBottom: 24 }}>
          Latest 30 war_room_drafts. Read-only view. Filter by status below.
        </p>

        <WidgetFrame title="Drafts">
          <div className="cockpit-toolbar">
            <label
              htmlFor="status-filter"
              style={{ color: "var(--text-muted)", fontSize: 12 }}
            >
              Status
            </label>
            <select
              id="status-filter"
              className="cockpit-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value={ALL}>All</option>
              {allStatuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <span className="spacer" />
            {error ? (
              <span style={{ color: "var(--status-red)", fontSize: 12 }}>
                error: {error}
              </span>
            ) : null}
          </div>

          {visible.length === 0 ? (
            <p style={{ color: "var(--text-muted)", padding: "12px 4px" }}>
              {data === null ? "Loading..." : "No drafts match this filter."}
            </p>
          ) : (
            <table className="cockpit-table">
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Status</th>
                  <th>Register</th>
                  <th>Updated</th>
                  <th>Lease owner</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={r.id}>
                    <td>
                      {r.topic ?? <span className="muted">(no topic)</span>}
                    </td>
                    <td>
                      <span className="cockpit-pill">{r.status ?? "—"}</span>
                    </td>
                    <td className="muted">{r.register ?? "—"}</td>
                    <td className="muted">{formatDate(r.updated_at)}</td>
                    <td className="muted">{r.lease_owner ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </WidgetFrame>

        <footer className="cockpit-footer">
          <span>
            Read-only · v2 will add Approve / Reject after MVP feedback
          </span>
          <span>
            <Link href="/cockpit">← Back to home</Link>
          </span>
        </footer>
      </main>
    </PinGate>
  );
}
