"use client";
import { useEffect, useState } from "react";
import { WidgetFrame } from "./WidgetFrame";
import { StatusDot } from "./StatusDot";

interface Resp {
  statuses: any[];
  counts: {
    running: number;
    waiting: number;
    not_loaded: number;
    failed: number;
  };
}

export function GlobalPulse() {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    async function fetchD() {
      try {
        const r = await fetch("/api/cockpit/cron/list");
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = await r.json();
        if (!cancel) {
          setData(j);
          setErr(null);
        }
      } catch (e: any) {
        if (!cancel) setErr(e.message);
      }
    }
    fetchD();
    const i = setInterval(fetchD, 10_000);
    return () => {
      cancel = true;
      clearInterval(i);
    };
  }, []);

  if (err) {
    return (
      <WidgetFrame title="Global Pulse" status="red">
        error: {err}
      </WidgetFrame>
    );
  }
  if (!data) {
    return (
      <WidgetFrame title="Global Pulse" status="amber">
        loading...
      </WidgetFrame>
    );
  }

  const dominant: "green" | "amber" | "red" =
    data.counts.failed > 0
      ? "red"
      : data.counts.not_loaded > 0
        ? "amber"
        : "green";
  return (
    <WidgetFrame title="Global Pulse" status={dominant}>
      <div style={{ fontSize: 24, marginBottom: 8 }}>
        {data.counts.running}/{data.statuses.length}
      </div>
      <div style={{ fontSize: 11, color: "var(--fg-dim)" }}>
        <div>
          <StatusDot status="green" /> running: {data.counts.running}
        </div>
        <div>
          <StatusDot status="amber" /> waiting: {data.counts.waiting}
        </div>
        <div style={{ color: "var(--fg-red)" }}>
          <StatusDot status="red" /> failed (24h): {data.counts.failed}
        </div>
      </div>
    </WidgetFrame>
  );
}
