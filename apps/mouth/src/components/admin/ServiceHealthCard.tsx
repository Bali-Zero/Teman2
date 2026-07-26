import {
  Activity,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { ServiceStatus } from "@/lib/api/admin/admin.types";

interface ServiceHealthCardProps {
  name: string;
  status: ServiceStatus;
  message: string;
  latency?: number;
  metadata?: Record<string, unknown>;
  icon?: React.ElementType;
}

export function ServiceHealthCard({
  name,
  status,
  message,
  latency,
  metadata,
  icon: Icon = Activity,
}: ServiceHealthCardProps) {
  const getStatusColor = (s: ServiceStatus) => {
    switch (s) {
      case "ok":
        return "text-[var(--state-success)] bg-[var(--state-success)]/10 border-[var(--state-success)]/30";
      case "warning":
        return "text-[var(--state-warning)] bg-[var(--state-warning)]/10 border-[var(--state-warning)]/30";
      case "error":
        return "text-[var(--state-danger)] bg-[var(--state-danger)]/10 border-[var(--state-danger)]/30";
      default:
        return "text-[var(--bz-text-2)] bg-[var(--bz-glass-rim)] border-[var(--bz-border)]";
    }
  };

  const getStatusIcon = (s: ServiceStatus) => {
    switch (s) {
      case "ok":
        return CheckCircle;
      case "warning":
        return AlertTriangle;
      case "error":
        return XCircle;
      default:
        return Activity;
    }
  };

  const StatusIcon = getStatusIcon(status);
  const colorClass = getStatusColor(status);

  return (
    <Card className={cn("border transition-all duration-200", colorClass)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
        <CardTitle className="text-sm font-medium capitalize flex items-center gap-2">
          <Icon className="w-4 h-4" />
          {name}
        </CardTitle>
        <StatusIcon className="w-4 h-4" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold uppercase tracking-wider text-xs mb-2">
          {status}
        </div>
        <p
          className="text-xs text-muted-foreground mb-4 font-mono truncate"
          title={message}
        >
          {message}
        </p>

        <div className="space-y-2">
          {latency !== undefined && (
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground flex items-center gap-1">
                <Clock className="w-3 h-3" /> Latency
              </span>
              <span
                className={cn(
                  "font-mono",
                  latency > 1000
                    ? "text-[var(--state-warning)]"
                    : "text-[var(--state-success)]",
                )}
              >
                {latency.toFixed(1)}ms
              </span>
            </div>
          )}

          {metadata &&
            Object.entries(metadata).map(([key, value]) => (
              <div
                key={key}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-muted-foreground capitalize">
                  {key.replace(/_/g, " ")}
                </span>
                <span className="font-mono text-foreground/80">
                  {String(value)}
                </span>
              </div>
            ))}
        </div>
      </CardContent>
    </Card>
  );
}
