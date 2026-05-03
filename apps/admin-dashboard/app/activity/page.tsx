"use client";
import { useState, useEffect } from "react";
import { error as logError } from "@/lib/logger";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardTitle,
} from "@/components/ui/primitives";
import { Activity, RefreshCcw, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

export default function ActivityPage() {
  const [activities, setActivities] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchActivity = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/postgres/activity");
      const data = await res.json();
      if (data.activities) {
        setActivities(data.activities);
        setError(null);
      }
      if (data.warning) {
        setError(data.warning);
      }
      setLastUpdated(new Date());
    } catch (e) {
      logError(e as string);
      setError("Failed to fetch activity");
    } finally {
      setLoading(false);
    }
  };

  // Initial load & Auto-refresh
  useEffect(() => {
    fetchActivity();
    const interval = setInterval(fetchActivity, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <Activity className="h-8 w-8 text-primary" />
            Agent Activity Stream
          </h1>
          <p className="text-muted-foreground mt-2">
            Live monitoring of agent actions, decisions, and tool executions.
            Auto-refreshes every 5s.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-muted-foreground">
            Updated: {lastUpdated?.toLocaleTimeString() ?? "..."}
          </span>
          <Button variant="outline" size="sm" onClick={fetchActivity}>
            <RefreshCcw
              className={cn("h-4 w-4 mr-2", loading && "animate-spin")}
            />
            Refresh
          </Button>
        </div>
      </div>

      {error ? (
        <div className="p-12 border-2 border-dashed rounded-lg text-center">
          <Terminal className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium">No Activity Log Found</h3>
          <p className="text-muted-foreground mt-2">{error}</p>
          <p className="text-sm text-muted-foreground mt-1">
            Ensure the <code>activity_log</code> table exists in your PostgreSQL
            database.
          </p>
        </div>
      ) : (
        <div className="grid gap-4">
          {activities.length === 0 && !loading && (
            <div className="text-center py-12 text-muted-foreground">
              No recent activity recorded.
            </div>
          )}

          {activities.map((act, i) => (
            <Card
              key={act.id || i}
              className="overflow-hidden border-l-4 border-l-primary/50"
            >
              <CardContent className="p-4 flex items-start gap-4">
                <div className="min-w-[120px] text-sm text-muted-foreground">
                  {new Date(act.created_at).toLocaleTimeString()}
                </div>
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <h4 className="font-semibold text-sm flex items-center gap-2">
                      {act.agent_name || "System"}
                      <Badge
                        variant={
                          act.status === "ERROR" ? "destructive" : "secondary"
                        }
                      >
                        {act.action || "Unknown"}
                      </Badge>
                    </h4>
                    {act.duration_ms && (
                      <span className="text-xs font-mono">
                        {act.duration_ms}ms
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap font-mono bg-muted/30 p-2 rounded">
                    {typeof act.details === "object"
                      ? JSON.stringify(act.details)
                      : act.details}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
