"use client";
import { useEffect, useState } from "react";
import { WidgetFrame } from "./WidgetFrame";

interface Decision {
  type: string;
  title: string;
  url?: string;
  age_minutes?: number;
}
interface Resp {
  decisions: Decision[];
  total: number;
}

export function DecisionsAttesa() {
  const [data, setData] = useState<Resp | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    async function fetchD() {
      try {
        const r = await fetch("/api/cockpit/decisions");
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
    const i = setInterval(fetchD, 30_000);
    return () => {
      cancel = true;
      clearInterval(i);
    };
  }, []);

  if (err) {
    return (
      <WidgetFrame title="Decisions Attesa" status="red">
        error: {err}
      </WidgetFrame>
    );
  }
  if (!data) {
    return (
      <WidgetFrame title="Decisions Attesa" status="amber">
        loading...
      </WidgetFrame>
    );
  }

  const status: "green" | "amber" | "red" =
    data.total === 0 ? "green" : data.total > 5 ? "red" : "amber";
  return (
    <WidgetFrame title="Decisions Attesa" status={status}>
      <div style={{ fontSize: 24, marginBottom: 8 }}>{data.total}</div>
      <div style={{ fontSize: 11, maxHeight: 140, overflow: "auto" }}>
        {data.decisions.length === 0 ? (
          <div style={{ color: "var(--fg-dim)" }}>nothing pending</div>
        ) : (
          data.decisions.map((d, i) => (
            <div key={i} style={{ marginBottom: 4 }}>
              <a
                href={d.url ?? "#"}
                target="_blank"
                rel="noreferrer"
                style={{ color: "var(--fg-active)", textDecoration: "none" }}
              >
                {d.title.slice(0, 50)}
              </a>
              {typeof d.age_minutes === "number" && (
                <span style={{ color: "var(--fg-dim)", marginLeft: 4 }}>
                  ({d.age_minutes}m)
                </span>
              )}
            </div>
          ))
        )}
      </div>
    </WidgetFrame>
  );
}
