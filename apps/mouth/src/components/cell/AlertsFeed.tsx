import type { CellAlert } from "@/hooks/useCellStatus";

const LEVEL_COLOR: Record<string, string> = {
  info: "#3b82f6",
  warn: "#f59e0b",
  critical: "#ef4444",
};

const ACTION_ICON: Record<string, string> = {
  alert_silent: "🔕",
  alert_human: "🚨",
  read_logs: "📋",
  restart_service: "🔄",
  scale_up: "⬆️",
  scale_down: "⬇️",
};

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("it-IT", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function AlertsFeed({ alerts }: { alerts: CellAlert[] }) {
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
          marginBottom: 12,
        }}
      >
        Alerts Feed
      </div>

      {alerts.length === 0 ? (
        <div style={{ fontSize: 12, color: "#444", fontFamily: "monospace" }}>
          No alerts recorded yet
        </div>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 6,
            maxHeight: 280,
            overflowY: "auto",
          }}
        >
          {alerts.map((a) => (
            <div
              key={a.id}
              style={{
                display: "flex",
                gap: 8,
                fontSize: 11,
                fontFamily: "monospace",
                borderLeft: `2px solid ${LEVEL_COLOR[a.level] ?? "#666"}`,
                paddingLeft: 8,
              }}
            >
              <span style={{ color: "#444", flexShrink: 0 }}>
                {fmt(a.created_at)}
              </span>
              <span style={{ flexShrink: 0 }}>
                {ACTION_ICON[a.action] ?? "•"}
              </span>
              <span
                style={{
                  color: LEVEL_COLOR[a.level] ?? "#ccc",
                  flexShrink: 0,
                  minWidth: 72,
                }}
              >
                {a.action}
              </span>
              <span
                style={{
                  color: "#aaa",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
                title={a.message}
              >
                {a.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
