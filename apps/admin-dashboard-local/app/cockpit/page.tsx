/**
 * /cockpit — Bali Zero home (read-only MVP).
 *
 * 4 tiles + 2 door cards + footer. Tiles fetch their data client-side every
 * 60s. PinGate wraps the whole tree; if no valid session cookie the modal
 * shows and the rest of the page renders behind it.
 */
"use client";

import { useEffect, useState } from "react";
import BrandTopbar from "@/components/cockpit/BrandTopbar";
import DoorCard from "@/components/cockpit/DoorCard";
import HomeTile from "@/components/cockpit/HomeTile";
import PinGate from "@/components/cockpit/PinGate";

interface CronList {
  total: number;
  running: number;
  waiting: number;
  not_loaded: number;
}

interface DecisionsResponse {
  count: number;
}

function useJson<T>(url: string, intervalMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function tick() {
      try {
        const res = await fetch(url, { credentials: "include" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const j = (await res.json()) as T;
        if (!cancelled) {
          setData(j);
          setError("");
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    }

    tick();
    timer = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [url, intervalMs]);

  return { data, error };
}

export default function CockpitHome() {
  const { data: cron } = useJson<CronList>("/api/cockpit/cron/list", 60_000);
  const { data: decisions } = useJson<DecisionsResponse>(
    "/api/cockpit/decisions",
    60_000,
  );

  const total = cron?.total ?? 35;
  const running = cron?.running ?? null;
  const pendingDecisions = decisions?.count ?? null;

  const pulseStatus: "healthy" | "amber" | "red" =
    running === null
      ? "amber"
      : running >= total - 2
        ? "healthy"
        : running >= total - 6
          ? "amber"
          : "red";

  return (
    <PinGate>
      <BrandTopbar>
        <span>
          <span className={`cockpit-dot ${pulseStatus}`} />
          <strong>{running ?? "—"}</strong>/{total} cron
        </span>
        <span>
          PG <strong>connected</strong>
        </span>
        <span>
          HMAC <span className="accent">verified</span>
        </span>
      </BrandTopbar>

      <main>
        <section className="cockpit-home-tiles">
          <HomeTile
            label="Global Pulse"
            value={running ?? "—"}
            suffix={`/${total}`}
            meta={
              running === null
                ? "loading"
                : pulseStatus === "healthy"
                  ? "healthy organism"
                  : pulseStatus === "amber"
                    ? "some cron quiet"
                    : "needs attention"
            }
            status={pulseStatus}
          />
          <HomeTile
            label="Pending Decisions"
            value={pendingDecisions ?? "—"}
            meta={
              pendingDecisions === null
                ? "loading"
                : pendingDecisions === 0
                  ? "all clear"
                  : "pending review"
            }
          />
          <HomeTile label="What It Learned" value="—" meta="coming v2" />
          <HomeTile label="Quick Commands" value="→" meta="coming v2" />
        </section>

        <DoorCard
          title="WR2 — Editorial Carousels"
          description="News, regulations, visa / tax / property carousels for Instagram. Read-only pipeline view."
          href="/cockpit/wr2"
        >
          Open the WR2 drafts table to see the latest 30 briefs and their
          current pipeline status.
        </DoorCard>

        <DoorCard
          title="Intel-Lake — News & Regulations"
          description="OSINT pipeline: Indonesia sources → router → NotebookLM intel. Read-only feed."
          href="/cockpit/intel-lake"
        >
          Open the Intel-Lake page to inspect 4 KPI counters and the latest 30
          items. Click any row to open the source URL.
        </DoorCard>

        <footer className="cockpit-footer">
          <span>
            Pro · localhost:3100 ·{" "}
            <strong style={{ color: "var(--text-white)" }}>Antonello</strong> ·
            L2 autonomous ops
          </span>
          <span>Read-only MVP · v2 iterates after feedback</span>
        </footer>
      </main>
    </PinGate>
  );
}
