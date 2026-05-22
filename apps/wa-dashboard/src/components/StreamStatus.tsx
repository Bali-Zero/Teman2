"use client";

import { useInboxStore } from "@/lib/store";
import { Circle, AlertCircle, Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

const STATUS_COLOR: Record<string, string> = {
  idle: "text-neutral-500",
  connecting: "text-yellow-400",
  open: "text-emerald-400",
  error: "text-red-400",
  closed: "text-neutral-600",
};

export function StreamStatus() {
  const { status, lastEventId, errorCount } = useInboxStore((s) => s.stream);
  const color = STATUS_COLOR[status] ?? "text-neutral-500";
  const Icon =
    status === "connecting"
      ? Loader2
      : status === "error"
        ? AlertCircle
        : Circle;
  return (
    <div className="flex items-center gap-2 text-xs">
      <Icon
        className={cn(
          "h-3 w-3",
          color,
          status === "connecting" && "animate-spin",
        )}
        fill={status === "open" ? "currentColor" : "none"}
      />
      <span className={color}>SSE {status}</span>
      <span className="text-neutral-500">| last_event_id={lastEventId}</span>
      {errorCount > 0 && (
        <span className="text-red-400">| errors={errorCount}</span>
      )}
    </div>
  );
}
