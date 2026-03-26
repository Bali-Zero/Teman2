"use client";

import type { CellPulse } from "@/hooks/useCellStatus";

export function MetabolismBar({ pulse }: { pulse: CellPulse | null }) {
  if (!pulse) return null;
  const percent = (pulse.budget_spent / pulse.budget_limit) * 100;
  const barColor =
    percent > 90 ? "#ef4444" : percent > 60 ? "#f59e0b" : "#22c55e";
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
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 8,
          fontSize: 10,
          color: "#666",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        <span>Metabolism</span>
        <span style={{ fontFamily: "monospace", color: "#e5e5e5" }}>
          ${pulse.budget_spent.toFixed(2)} / ${pulse.budget_limit.toFixed(2)} (
          {percent.toFixed(1)}%)
        </span>
      </div>
      <div
        style={{
          height: 8,
          background: "#222",
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${Math.min(percent, 100)}%`,
            background: barColor,
            borderRadius: 4,
            transition: "width 0.5s, background 0.5s",
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          gap: 16,
          marginTop: 8,
          fontSize: 11,
          color: "#666",
        }}
      >
        <span>Routine: ${Math.min(pulse.budget_spent, 3).toFixed(2)}/$3</span>
        <span>Incident: $0.00/$5</span>
        <span style={{ color: "#444" }}>Reserve: $2 (locked)</span>
      </div>
    </div>
  );
}
