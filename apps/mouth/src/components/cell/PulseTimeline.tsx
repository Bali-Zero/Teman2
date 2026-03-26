"use client";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

interface PulsePoint {
  pulse_number: number;
  health_status: string;
  response_time_ms: number;
  created_at: string;
}

export function PulseTimeline({ pulses }: { pulses: PulsePoint[] }) {
  const sorted = [...pulses].reverse();
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
          marginBottom: 8,
        }}
      >
        Pulse Timeline (last {pulses.length})
      </div>
      <div style={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
        {sorted.map((p, i) => (
          <div
            key={i}
            title={`#${p.pulse_number} — ${p.health_status.toUpperCase()} — ${p.response_time_ms}ms — ${new Date(p.created_at).toLocaleTimeString()}`}
            style={{
              width: 12,
              height: 20,
              borderRadius: 2,
              background: HEALTH_COLORS[p.health_status] || "#444",
              opacity: 0.8,
              cursor: "pointer",
              transition: "opacity 0.2s",
            }}
            onMouseEnter={(e) => {
              (e.target as HTMLElement).style.opacity = "1";
            }}
            onMouseLeave={(e) => {
              (e.target as HTMLElement).style.opacity = "0.8";
            }}
          />
        ))}
      </div>
    </div>
  );
}
