interface ConfidenceBadgeProps {
  confidence: "ABSTAIN" | "CAUTIOUS" | "NORMAL";
}

export function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  if (confidence === "NORMAL") return null;

  if (confidence === "CAUTIOUS") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
        style={{
          backgroundColor: "rgba(234, 179, 8, 0.15)",
          color: "#eab308",
          border: "1px solid rgba(234, 179, 8, 0.3)",
        }}
      >
        <span>⚠</span>
        May vary by case
      </span>
    );
  }

  // ABSTAIN
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
      style={{
        backgroundColor: "rgba(239, 68, 68, 0.15)",
        color: "#ef4444",
        border: "1px solid rgba(239, 68, 68, 0.3)",
      }}
    >
      <span>⚑</span>
      Expert review needed
    </span>
  );
}
