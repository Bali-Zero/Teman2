import type { CellPulse } from "@/hooks/useCellStatus";

const HEALTH_COLORS: Record<string, string> = {
  green: "#22c55e",
  yellow: "#f59e0b",
  red: "#ef4444",
};

const ORGANS = [
  { label: "SENSE", angle: 0, color: "#22c55e" },
  { label: "MEMORY", angle: 90, color: "#3b82f6" },
  { label: "HEAL", angle: 180, color: "#f59e0b" },
  { label: "THINK", angle: 270, color: "#8b5cf6" },
];

export function OrganismView({
  pulse,
  alive,
}: {
  pulse: CellPulse | null;
  alive: boolean;
}) {
  const color = alive
    ? HEALTH_COLORS[pulse?.health_status || "green"]
    : "#666";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        minHeight: 300,
        position: "relative",
      }}
    >
      <div
        style={{
          position: "absolute",
          width: 220,
          height: 220,
          border: `1px solid ${color}33`,
          borderRadius: "50%",
          transition: "border-color 0.5s",
        }}
      />
      <div
        style={{
          width: 100,
          height: 100,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${color} 0%, #0a0a0a 70%)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 36,
          animation: alive ? "organism-pulse 2s infinite" : "none",
          transition: "all 0.5s",
        }}
      >
        {alive ? "🧬" : "💀"}
      </div>
      {ORGANS.map((organ) => {
        const rad = (organ.angle * Math.PI) / 180;
        const x = Math.cos(rad) * 130;
        const y = Math.sin(rad) * 130;
        return (
          <div
            key={organ.label}
            style={{
              position: "absolute",
              left: `calc(50% + ${x}px)`,
              top: `calc(50% + ${y}px)`,
              transform: "translate(-50%, -50%)",
              fontSize: 11,
              fontWeight: 600,
              color: organ.color,
              letterSpacing: "0.05em",
              opacity: alive ? 0.9 : 0.3,
              transition: "opacity 0.5s",
            }}
          >
            {organ.label}
          </div>
        );
      })}
      {pulse && (
        <div
          style={{
            position: "absolute",
            bottom: 10,
            display: "flex",
            gap: 20,
            fontSize: 11,
            color: "#666",
          }}
        >
          <span>Pulse #{pulse.pulse_number}</span>
          <span>Health: {pulse.health_status.toUpperCase()}</span>
          <span>${pulse.budget_spent.toFixed(2)} spent</span>
        </div>
      )}
      <style jsx global>{`
        @keyframes organism-pulse {
          0%,
          100% {
            box-shadow: 0 0 30px ${color}30;
          }
          50% {
            box-shadow: 0 0 60px ${color}50;
          }
        }
      `}</style>
    </div>
  );
}
