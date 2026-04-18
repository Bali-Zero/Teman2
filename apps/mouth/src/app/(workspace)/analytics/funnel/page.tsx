"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  analyticsApi,
  type FunnelViewResponse,
} from "@/lib/api/workspace/analytics.api";

const FunnelChart = dynamic(
  () => import("@/components/analytics/FunnelChart"),
  {
    ssr: false,
    loading: () => (
      <div
        style={{ height: 300 }}
        className="animate-pulse rounded bg-white/5"
        aria-hidden="true"
      />
    ),
  },
);

export default function FunnelAnalyticsPage() {
  const [data, setData] = useState<FunnelViewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    analyticsApi
      .funnelView()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const merged = useMemo(() => {
    if (!data) return [];
    const sessionMap = new Map(data.sessions.map((s) => [s.funnel, s.count]));
    const conversionMap = new Map(
      data.conversions.map((c) => [c.funnel, c.count]),
    );
    const funnels = new Set<string>([
      ...sessionMap.keys(),
      ...conversionMap.keys(),
    ]);
    return Array.from(funnels).map((funnel) => ({
      funnel,
      sessions: sessionMap.get(funnel) ?? 0,
      conversions: conversionMap.get(funnel) ?? 0,
    }));
  }, [data]);

  const totals = useMemo(() => {
    if (!data) return { sessions: 0, conversions: 0, rate: 0 };
    const sessions = data.sessions.reduce((a, b) => a + b.count, 0);
    const conversions = data.conversions.reduce((a, b) => a + b.count, 0);
    const rate = sessions > 0 ? (conversions / sessions) * 100 : 0;
    return { sessions, conversions, rate };
  }, [data]);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <header>
        <h1 style={{ margin: 0, fontSize: 24 }}>Funnel Analytics</h1>
        <p
          style={{
            margin: "4px 0 0",
            color: "var(--color-text-secondary, #9ca3af)",
          }}
        >
          Sessions and first-touch conversion attribution across funnels.
        </p>
      </header>

      {loading ? (
        <p>Caricamento…</p>
      ) : error ? (
        <p role="alert" style={{ color: "var(--color-danger, #dc2626)" }}>
          Errore: {error}
        </p>
      ) : (
        <>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
              gap: 16,
            }}
          >
            <Kpi
              label="Sessioni totali"
              value={totals.sessions.toLocaleString()}
            />
            <Kpi
              label="Conversioni"
              value={totals.conversions.toLocaleString()}
            />
            <Kpi
              label="Tasso conversione"
              value={`${totals.rate.toFixed(2)}%`}
            />
          </div>

          <div
            style={{
              background: "rgba(26,26,30,0.5)",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 12,
              padding: 16,
              minHeight: 360,
            }}
          >
            <h2 style={{ margin: "0 0 12px", fontSize: 16 }}>
              Sessioni vs conversioni per funnel
            </h2>
            {merged.length === 0 ? (
              <p style={{ color: "var(--color-text-secondary, #9ca3af)" }}>
                Nessun dato disponibile.
              </p>
            ) : (
              <FunnelChart data={merged} />
            )}
          </div>
        </>
      )}
    </section>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: "rgba(26,26,30,0.5)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 12,
        padding: 16,
      }}
    >
      <div
        style={{ fontSize: 12, color: "var(--color-text-secondary, #9ca3af)" }}
      >
        {label}
      </div>
      <div style={{ fontSize: 28, fontWeight: 600, marginTop: 4 }}>{value}</div>
    </div>
  );
}
