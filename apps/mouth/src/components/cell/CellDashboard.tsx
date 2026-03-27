"use client";

import { useCellStatus } from "@/hooks/useCellStatus";
import { OrganismView } from "./OrganismView";
import { VitalSigns } from "./VitalSigns";
import { MetabolismBar } from "./MetabolismBar";
import { PulseTimeline } from "./PulseTimeline";
import { AlertsFeed } from "./AlertsFeed";

export function CellDashboard() {
  const { status, loading, error } = useCellStatus(10000);

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          color: "#666",
        }}
      >
        Connecting to CELL...
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "60vh",
          color: "#ef4444",
        }}
      >
        Cannot reach CELL: {error}
      </div>
    );
  }

  const pulse = status?.last_pulse || null;
  const alive = status?.alive || false;

  return (
    <div
      style={{
        background: "#0a0a0a",
        minHeight: "100vh",
        padding: 24,
        color: "#e5e5e5",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 24,
          paddingBottom: 16,
          borderBottom: "1px solid #222",
        }}
      >
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>
            🧬 CELL — Essere Perfetto
          </h1>
          <p style={{ fontSize: 12, color: "#666", margin: "4px 0 0" }}>
            Autonomous Digital Organism
          </p>
        </div>
        <span style={{ fontSize: 12, color: "#444" }}>v0.1.0</span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 16,
          marginBottom: 16,
        }}
      >
        <div
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 8,
          }}
        >
          <OrganismView pulse={pulse} alive={alive} />
        </div>
        <VitalSigns pulse={pulse} alive={alive} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <MetabolismBar pulse={pulse} />
      </div>
      <div style={{ marginBottom: 16 }}>
        <PulseTimeline pulses={status?.recent_pulses || []} />
      </div>

      <div style={{ marginBottom: 16 }}>
        <AlertsFeed alerts={status?.alerts || []} />
      </div>

      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}
      >
        <div
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "#666",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 12,
            }}
          >
            Memory
          </div>
          <div
            style={{
              fontSize: 13,
              lineHeight: 2,
              fontFamily: "monospace",
            }}
          >
            <div>
              STM: {pulse?.memory_stm_count || 0} observations (Redis)
            </div>
            <div>
              LTM: {pulse?.memory_ltm_count || 0} experiences (Qdrant)
            </div>
            <div>
              Procedures: {pulse?.procedures_count || 0} strategies
            </div>
          </div>
        </div>
        <div
          style={{
            background: "#111",
            border: "1px solid #222",
            borderRadius: 8,
            padding: 16,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: "#666",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 12,
            }}
          >
            Cells
          </div>
          <div style={{ fontSize: 13, fontFamily: "monospace" }}>
            <div style={{ marginBottom: 8 }}>
              {pulse?.cells_active || 1}/{pulse?.cells_total || 50} active
            </div>
            <div
              style={{
                fontSize: 12,
                color: "#888",
                display: "flex",
                alignItems: "center",
                gap: 6,
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#22c55e",
                  display: "inline-block",
                }}
              />
              pulse_cell: ACTIVE
            </div>
          </div>
        </div>
      </div>

      {status?.uptime_24h && status.uptime_24h.total_pulses > 0 && (
        <div
          style={{
            marginTop: 16,
            textAlign: "center",
            fontSize: 11,
            color: "#444",
          }}
        >
          24h uptime: {status.uptime_24h.green_percent}% green ·{" "}
          {status.uptime_24h.yellow_percent}% yellow ·{" "}
          {status.uptime_24h.red_percent}% red ·{" "}
          {status.uptime_24h.total_pulses} pulses
        </div>
      )}
    </div>
  );
}
