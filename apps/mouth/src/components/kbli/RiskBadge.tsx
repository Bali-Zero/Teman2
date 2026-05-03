import { cn } from "@/lib/utils";

interface RiskBadgeProps {
  category?: string;
  riskCategory?: string;
  size?: "sm" | "md";
}

function parseRisk(category: string): { label: string; color: string } {
  if (!category) return { label: "Unknown", color: "var(--foreground-muted)" };
  const lower = category.toLowerCase();
  if (
    lower === "tinggi" ||
    (lower.includes("tinggi") &&
      !lower.includes("rendah") &&
      !lower.includes("menengah"))
  )
    return { label: "High", color: "var(--kbli-risk-high, #ef4444)" };
  if (lower.includes("menengah") && lower.includes("tinggi"))
    return {
      label: "Medium-High",
      color: "var(--kbli-risk-medium-high, #f59e0b)",
    };
  if (lower.includes("menengah") && lower.includes("rendah"))
    return {
      label: "Medium-Low",
      color: "var(--kbli-risk-medium-low, #3b82f6)",
    };
  if (lower.includes("rendah"))
    return { label: "Low", color: "var(--kbli-risk-low, #22c55e)" };
  return { label: category, color: "var(--foreground-muted, #666)" };
}

export function RiskBadge({
  category,
  riskCategory,
  size = "md",
}: RiskBadgeProps) {
  const { label, color } = parseRisk(category ?? riskCategory ?? "");
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm",
      )}
      style={{
        color,
        borderColor: `${color}33`,
        backgroundColor: `${color}15`,
      }}
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label} Risk
    </span>
  );
}
