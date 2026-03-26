"use client";

import type { CellPulse } from "@/hooks/useCellStatus";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

function VitalCard({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: string;
  subtitle?: string;
  color?: string;
}) {
  return (
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
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 24,
          fontWeight: 700,
          color: color || "#e5e5e5",
          fontFamily: "monospace",
        }}
      >
        {value}
      </div>
      {subtitle && (
        <div style={{ fontSize: 11, color: "#666", marginTop: 2 }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

export function VitalSigns({
  pulse,
  alive,
}: {
  pulse: CellPulse | null;
  alive: boolean;
}) {
  if (!pulse) return null;
  const healthColor = alive ? HEALTH_COLORS[pulse.health_status] : "#666";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      <VitalCard
        label="Heartbeat"
        value="60s"
        subtitle={`Pulse #${pulse.pulse_number}`}
      />
      <VitalCard
        label="DNA"
        value={pulse.dna_intact ? "INTACT" : "TAMPERED"}
        color={pulse.dna_intact ? "#22c55e" : "#ef4444"}
      />
      <VitalCard
        label="Health"
        value={pulse.health_status.toUpperCase()}
        color={healthColor}
      />
      <VitalCard
        label="Response"
        value={`${(pulse.response_time_ms / 1000).toFixed(2)}s`}
        subtitle={pulse.response_time_ms > 5000 ? "↑ slow" : "normal"}
      />
    </div>
  );
}
