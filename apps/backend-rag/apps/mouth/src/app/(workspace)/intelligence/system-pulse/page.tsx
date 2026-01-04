"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Activity,
  Loader2,
  CheckCircle,
  AlertCircle,
  Clock,
  Database,
  RefreshCw,
  TrendingUp,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface SystemMetrics {
  agent_status: "active" | "idle" | "error";
  last_run: string;
  items_processed_today: number;
  avg_response_time_ms: number;
  qdrant_health: "healthy" | "degraded" | "down";
  next_scheduled_run: string;
  uptime_percentage: number;
}

export default function SystemPulsePage() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
  }, []);

  const loadMetrics = async () => {
    setLoading(true);
    // TODO: Replace with real API call when backend endpoint is ready
    setTimeout(() => {
      setMetrics({
        agent_status: "active",
        last_run: new Date(Date.now() - 1000 * 60 * 15).toISOString(), // 15 min ago
        items_processed_today: 29,
        avg_response_time_ms: 1250,
        qdrant_health: "healthy",
        next_scheduled_run: new Date(Date.now() + 1000 * 60 * 45).toISOString(), // 45 min from now
        uptime_percentage: 99.8,
      });
      setLoading(false);
    }, 800);
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-[var(--accent)]" />
        <p className="text-[var(--foreground-muted)] animate-pulse text-lg">
          Loading System Metrics...
        </p>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex flex-col items-center justify-center py-32">
        <AlertCircle className="h-16 w-16 text-red-500 mb-4" />
        <h3 className="text-xl font-semibold text-[var(--foreground)] mb-2">
          Metrics Unavailable
        </h3>
        <p className="text-[var(--foreground-muted)] mb-6">
          Unable to load system health metrics
        </p>
        <Button onClick={loadMetrics} variant="outline" className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Retry
        </Button>
      </div>
    );
  }

  const statusColor = {
    active: "text-green-600",
    idle: "text-amber-600",
    error: "text-red-600",
  }[metrics.agent_status];

  const statusBgColor = {
    active: "bg-green-100 border-green-200",
    idle: "bg-amber-100 border-amber-200",
    error: "bg-red-100 border-red-200",
  }[metrics.agent_status];

  const qdrantColor = {
    healthy: "text-green-600",
    degraded: "text-amber-600",
    down: "text-red-600",
  }[metrics.qdrant_health];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-center pb-4 border-b border-[var(--border)]">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
            System Pulse
          </h2>
          <p className="text-[var(--foreground-muted)] text-lg">
            Real-time health monitoring for IntelligentVisaAgent
          </p>
        </div>
        <Button onClick={loadMetrics} variant="secondary" size="sm" className="gap-2">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Primary Metrics Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Agent Status */}
        <Card className="border-t-4 border-t-green-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Agent Status
            </CardTitle>
            <Activity className={cn("h-5 w-5", statusColor)} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-bold border shadow-sm",
                  statusBgColor,
                  statusColor
                )}
              >
                <div className="w-2 h-2 rounded-full bg-current animate-pulse" />
                {metrics.agent_status.toUpperCase()}
              </span>
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-3">
              Uptime: {metrics.uptime_percentage}%
            </p>
          </CardContent>
        </Card>

        {/* Last Run */}
        <Card className="border-t-4 border-t-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Last Scan
            </CardTitle>
            <Clock className="h-5 w-5 text-blue-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {new Date(metrics.last_run).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              {new Date(metrics.last_run).toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
              })}
            </p>
          </CardContent>
        </Card>

        {/* Items Processed */}
        <Card className="border-t-4 border-t-purple-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Items Processed Today
            </CardTitle>
            <TrendingUp className="h-5 w-5 text-purple-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {metrics.items_processed_today}
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Visa pages analyzed
            </p>
          </CardContent>
        </Card>

        {/* Avg Response Time */}
        <Card className="border-t-4 border-t-amber-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Avg Response Time
            </CardTitle>
            <Zap className="h-5 w-5 text-amber-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {(metrics.avg_response_time_ms / 1000).toFixed(2)}s
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Per page analysis
            </p>
          </CardContent>
        </Card>

        {/* Qdrant Health */}
        <Card className="border-t-4 border-t-green-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Qdrant Health
            </CardTitle>
            <Database className={cn("h-5 w-5", qdrantColor)} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {metrics.qdrant_health === "healthy" && (
                <CheckCircle className="h-5 w-5 text-green-600" />
              )}
              {metrics.qdrant_health === "degraded" && (
                <AlertCircle className="h-5 w-5 text-amber-600" />
              )}
              {metrics.qdrant_health === "down" && (
                <AlertCircle className="h-5 w-5 text-red-600" />
              )}
              <span className={cn("text-lg font-bold", qdrantColor)}>
                {metrics.qdrant_health.charAt(0).toUpperCase() +
                  metrics.qdrant_health.slice(1)}
              </span>
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Vector database status
            </p>
          </CardContent>
        </Card>

        {/* Next Scheduled Run */}
        <Card className="border-t-4 border-t-slate-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Next Scheduled Run
            </CardTitle>
            <Clock className="h-5 w-5 text-slate-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {new Date(metrics.next_scheduled_run).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
            <p className="text-xs text-[var(--foreground-muted)] mt-1">
              Every 2 hours
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Agent Configuration Info */}
      <Card className="bg-[var(--background-secondary)] border-[var(--border)]">
        <CardHeader>
          <CardTitle className="text-lg text-[var(--foreground)]">
            Agent Configuration
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Model</p>
              <p className="text-[var(--foreground)]">Gemini 2.0 Flash (Vision)</p>
            </div>
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Browser</p>
              <p className="text-[var(--foreground)]">Playwright Webkit</p>
            </div>
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Target URL</p>
              <p className="text-[var(--foreground)] text-xs font-mono">
                imigrasi.go.id/wna/permohonan-visa
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-[var(--foreground-muted)] font-medium">Detection Mode</p>
              <p className="text-[var(--foreground)]">MD5 Hash + Vision Analysis</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
