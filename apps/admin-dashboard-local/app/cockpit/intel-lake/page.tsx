/**
 * /cockpit/intel-lake — READ-ONLY Intel-Lake KPI + items table.
 *
 * 4 KPI mini-cards from /api/cockpit/intel-lake/kpi.
 * Latest 30 intel_items from /api/cockpit/intel-lake/items.
 * Click a row → open canonical_url in a new tab (Antonello reads source).
 *
 * NO action buttons, NO drawer, NO intent emission. Polling 60s.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import BrandTopbar from "@/components/cockpit/BrandTopbar";
import HomeTile from "@/components/cockpit/HomeTile";
import PinGate from "@/components/cockpit/PinGate";
import WidgetFrame from "@/components/cockpit/WidgetFrame";

interface KpiResponse {
  items_today: number;
  outbox_pending: number;
  stuck: number;
  nb_pushes_7d: number;
  errors?: Record<string, string>;
}

interface ItemRow {
  id: string;
  canonical_url: string | null;
  title: string | null;
  source_domain: string | null;
  routing_status: string | null;
  first_seen_at: string | null;
}

interface ItemsResponse {
  count: number;
  items: ItemRow[];
  error?: string;
}

function formatDate(s: string | null): string {
  if (!s) return "—";
  return s.replace(/\.\d+/, "").replace("T", " ").slice(0, 19);
}

function pillClass(status: string | null): string {
  if (!status) return "cockpit-pill";
  if (status === "needs_review") return "cockpit-pill red";
  if (status === "unrouted") return "cockpit-pill amber";
  if (status === "skip") return "cockpit-pill";
  return "cockpit-pill yellow";
}

export default function CockpitIntelLakePage() {
  const [kpi, setKpi] = useState<KpiResponse | null>(null);
  const [items, setItems] = useState<ItemsResponse | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function tick() {
      try {
        const [kRes, iRes] = await Promise.all([
          fetch("/api/cockpit/intel-lake/kpi", { credentials: "include" }),
          fetch("/api/cockpit/intel-lake/items", { credentials: "include" }),
        ]);
        if (!kRes.ok) throw new Error(`KPI HTTP ${kRes.status}`);
        if (!iRes.ok) throw new Error(`items HTTP ${iRes.status}`);
        const kJson = (await kRes.json()) as KpiResponse;
        const iJson = (await iRes.json()) as ItemsResponse;
        if (!cancelled) {
          setKpi(kJson);
          setItems(iJson);
          setError(iJson.error ?? "");
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    tick();
    timer = setInterval(tick, 60_000);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  const k = (v: number | undefined): string => {
    if (v === undefined || v === null) return "—";
    if (v < 0) return "?";
    return String(v);
  };

  return (
    <PinGate>
      <BrandTopbar tagline="— Intel-Lake read-only">
        <span>
          <strong>{items?.count ?? 0}</strong> shown
        </span>
        <span>refresh every 60s</span>
      </BrandTopbar>

      <main>
        <div className="cockpit-breadcrumb">
          <Link href="/cockpit">Cockpit</Link> · Intel-Lake
        </div>
        <h1 className="cockpit-page-heading">
          Intel-Lake — News & Regulations
        </h1>
        <p style={{ color: "var(--text-muted)", marginBottom: 24 }}>
          OSINT pipeline read-only feed. Click any row to open the source.
        </p>

        <section className="cockpit-kpi-grid">
          <HomeTile
            label="Items today"
            value={k(kpi?.items_today)}
            meta="first_seen_at = today"
          />
          <HomeTile
            label="Outbox pending"
            value={k(kpi?.outbox_pending)}
            meta="intel_lake_event unconsumed"
            status={kpi && kpi.outbox_pending > 50 ? "amber" : undefined}
          />
          <HomeTile
            label="Stuck"
            value={k(kpi?.stuck)}
            meta="routing_status = needs_review"
            status={
              kpi && kpi.stuck > 0
                ? kpi.stuck > 5
                  ? "red"
                  : "amber"
                : undefined
            }
          />
          <HomeTile
            label="NB pushes 7d"
            value={k(kpi?.nb_pushes_7d)}
            meta="intel_item_nb_pushes"
          />
        </section>

        <WidgetFrame title="Recent items">
          {error ? (
            <p style={{ color: "var(--status-red)", marginBottom: 12 }}>
              error: {error}
            </p>
          ) : null}

          {!items || items.items.length === 0 ? (
            <p style={{ color: "var(--text-muted)", padding: "12px 4px" }}>
              {items === null ? "Loading..." : "No intel items found."}
            </p>
          ) : (
            <table className="cockpit-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>First seen</th>
                </tr>
              </thead>
              <tbody>
                {items.items.map((r) => (
                  <tr
                    key={r.id}
                    className={r.canonical_url ? "is-clickable" : undefined}
                    onClick={() => {
                      if (r.canonical_url) {
                        window.open(
                          r.canonical_url,
                          "_blank",
                          "noopener,noreferrer",
                        );
                      }
                    }}
                  >
                    <td>
                      {r.title ?? <span className="muted">(no title)</span>}
                    </td>
                    <td className="muted">{r.source_domain ?? "—"}</td>
                    <td>
                      <span className={pillClass(r.routing_status)}>
                        {r.routing_status ?? "—"}
                      </span>
                    </td>
                    <td className="muted">{formatDate(r.first_seen_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </WidgetFrame>

        <footer className="cockpit-footer">
          <span>Read-only · clicking a row opens the source in a new tab</span>
          <span>
            <Link href="/cockpit">← Back to home</Link>
          </span>
        </footer>
      </main>
    </PinGate>
  );
}
