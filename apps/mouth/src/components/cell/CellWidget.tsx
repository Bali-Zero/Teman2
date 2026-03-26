"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCellStatus } from "@/hooks/useCellStatus";
import { api } from "@/lib/api";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

export function CellWidget() {
  const [expanded, setExpanded] = useState(false);
  const router = useRouter();
  const { status, loading } = useCellStatus(10000);

  if (!api.isAdmin()) return null;

  const color = status?.alive
    ? HEALTH_COLORS[status.last_pulse?.health_status || "green"]
    : "#666";
  const emoji = loading ? "⏳" : status?.alive ? "🧬" : "💀";
  const pulse = status?.last_pulse;

  return (
    <>
      <button
        onClick={() => setExpanded(!expanded)}
        title={
          pulse
            ? `CELL — Pulse #${pulse.pulse_number} — ${pulse.health_status.toUpperCase()}`
            : "CELL — Loading..."
        }
        style={{
          position: "fixed",
          bottom: 16,
          right: 16,
          width: 40,
          height: 40,
          borderRadius: "50%",
          background: "#111",
          border: `2px solid ${color}`,
          boxShadow: status?.alive
            ? `0 0 12px ${color}40, 0 0 24px ${color}20`
            : "none",
          cursor: "pointer",
          zIndex: 50,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 18,
          animation: status?.alive ? "cell-widget-pulse 2s infinite" : "none",
          transition: "all 0.3s ease",
        }}
      >
        {emoji}
      </button>

      {expanded && (
        <>
          <div
            onClick={() => setExpanded(false)}
            style={{ position: "fixed", inset: 0, zIndex: 49 }}
          />
          <div
            style={{
              position: "fixed",
              bottom: 64,
              right: 16,
              width: 280,
              background: "#111",
              border: "1px solid #333",
              borderRadius: 12,
              padding: 16,
              zIndex: 51,
              fontFamily: "system-ui, sans-serif",
              color: "#e5e5e5",
              fontSize: 13,
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 12,
              }}
            >
              <span style={{ fontSize: 20 }}>🧬</span>
              <span style={{ fontWeight: 600, fontSize: 15 }}>CELL</span>
              <span style={{ marginLeft: "auto", fontSize: 11, color: "#666" }}>
                v0.1.0
              </span>
            </div>

            {!status || !pulse ? (
              <div style={{ color: "#666" }}>Loading...</div>
            ) : (
              <>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 8,
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: color,
                      display: "inline-block",
                    }}
                  />
                  <span>
                    {status.alive ? pulse.health_status.toUpperCase() : "DEAD"}
                  </span>
                  <span style={{ color: "#666", marginLeft: "auto" }}>
                    Pulse #{pulse.pulse_number}
                  </span>
                </div>
                <div style={{ color: "#888", marginBottom: 4 }}>
                  Response: {pulse.response_time_ms}ms
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      color: "#666",
                      marginBottom: 2,
                    }}
                  >
                    <span>Budget</span>
                    <span>
                      ${pulse.budget_spent.toFixed(2)} /{" "}
                      ${pulse.budget_limit.toFixed(2)}
                    </span>
                  </div>
                  <div
                    style={{
                      height: 4,
                      background: "#222",
                      borderRadius: 2,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        height: "100%",
                        width: `${(pulse.budget_spent / pulse.budget_limit) * 100}%`,
                        background: color,
                        borderRadius: 2,
                        transition: "width 0.3s",
                      }}
                    />
                  </div>
                </div>
                <div style={{ color: "#888", fontSize: 12, marginBottom: 12 }}>
                  {pulse.action_taken || "Observing..."}
                </div>
                <button
                  onClick={() => {
                    setExpanded(false);
                    router.push("/admin/cell");
                  }}
                  style={{
                    width: "100%",
                    padding: "8px 0",
                    background: "#222",
                    border: "1px solid #333",
                    borderRadius: 6,
                    color: "#e5e5e5",
                    fontSize: 12,
                    cursor: "pointer",
                  }}
                >
                  Open CELL Dashboard →
                </button>
              </>
            )}
          </div>
        </>
      )}

      <style jsx global>{`
        @keyframes cell-widget-pulse {
          0%,
          100% {
            box-shadow: 0 0 12px ${color}40, 0 0 24px ${color}20;
          }
          50% {
            box-shadow: 0 0 20px ${color}60, 0 0 40px ${color}30;
          }
        }
      `}</style>
    </>
  );
}
