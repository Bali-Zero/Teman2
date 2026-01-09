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
import { logger } from "@/lib/logger";
import { intelligenceApi, SystemMetrics } from "@/lib/api/intelligence.api";
import { useToast } from "@/components/ui/toast";

export default function SystemPulsePage() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  useEffect(() => {
    logger.componentMount('SystemPulsePage');
    loadMetrics();

    return () => {
      logger.componentUnmount('SystemPulsePage');
    };
  }, []);

  const loadMetrics = async () => {
    logger.info('Loading system metrics', { component: 'SystemPulsePage', action: 'load_metrics' });
    setLoading(true);

    try {
      // Fetch real-time metrics from backend API
      const metricsData = await intelligenceApi.getMetrics();
      setMetrics(metricsData);

      logger.info('System metrics loaded successfully', {
        component: 'SystemPulsePage',
        action: 'load_metrics_success',
        metadata: {
          agent_status: metricsData.agent_status,
          qdrant_health: metricsData.qdrant_health,
          items_processed: metricsData.items_processed_today,
        },
      });
    } catch (error) {
      logger.error('Failed to load system metrics', {
        component: 'SystemPulsePage',
        action: 'load_metrics_error',
      }, error as Error);

      toast.error("Failed to load metrics", "Could not fetch system metrics. Please try again.");
      setMetrics(null);
    } finally {
      setLoading(false);
    }
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
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-[var(--foreground-muted)] text-lg">
          Metrics Unavailable
        </p>
        <Button onClick={loadMetrics} variant="secondary">
          Retry
        </Button>
      </div>
    );
  }

  const formatTime = (isoString: string | null) => {
    if (!isoString) return "N/A";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return "Invalid";
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-[var(--border)] pb-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
            System Pulse
          </h2>
          <p className="text-[var(--foreground-muted)] text-lg">
            Real-time health monitoring for IntelligentVisaAgent
          </p>
        </div>
        <Button onClick={loadMetrics} variant="secondary" size="sm" className="gap-2">
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Agent Status */}
        <Card className={cn(
          "border-t-4",
          metrics.agent_status === "active" ? "border-t-green-500" :
          metrics.agent_status === "idle" ? "border-t-amber-500" :
          "border-t-red-500"
        )}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Agent Status
            </CardTitle>
            <Activity className={cn(
              "h-5 w-5",
              metrics.agent_status === "active" ? "text-green-500" :
              metrics.agent_status === "idle" ? "text-amber-500" :
              "text-red-500"
            )} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className={cn(
                "inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold",
                metrics.agent_status === "active" ? "bg-green-100 text-green-600" :
                metrics.agent_status === "idle" ? "bg-amber-100 text-amber-600" :
                "bg-red-100 text-red-600"
              )}>
                {metrics.agent_status === "active" && (
                  <span className="h-2 w-2 rounded-full bg-green-600 animate-pulse"></span>
                )}
                {metrics.agent_status.toUpperCase()}
              </span>
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              Uptime: {metrics.uptime_percentage}%
            </p>
          </CardContent>
        </Card>

        {/* Last Scan */}
        <Card className="border-t-4 border-t-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Last Scan
            </CardTitle>
            <Clock className="h-5 w-5 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {metrics.last_run ? formatTime(metrics.last_run) : "Never"}
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              {metrics.last_run
                ? `${Math.round((Date.now() - new Date(metrics.last_run).getTime()) / 60000)} minutes ago`
                : "No runs recorded"}
            </p>
          </CardContent>
        </Card>

        {/* Items Processed Today */}
        <Card className="border-t-4 border-t-purple-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Items Processed Today
            </CardTitle>
            <TrendingUp className="h-5 w-5 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {metrics.items_processed_today}
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
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
            <Zap className="h-5 w-5 text-amber-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {(metrics.avg_response_time_ms / 1000).toFixed(2)}s
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              Per page analysis
            </p>
          </CardContent>
        </Card>

        {/* Qdrant Health */}
        <Card className={cn(
          "border-t-4",
          metrics.qdrant_health === "healthy" ? "border-t-green-500" :
          metrics.qdrant_health === "degraded" ? "border-t-amber-500" :
          "border-t-red-500"
        )}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Qdrant Health
            </CardTitle>
            <Database className={cn(
              "h-5 w-5",
              metrics.qdrant_health === "healthy" ? "text-green-500" :
              metrics.qdrant_health === "degraded" ? "text-amber-500" :
              "text-red-500"
            )} />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {metrics.qdrant_health === "healthy" ? (
                <CheckCircle className="h-5 w-5 text-green-600" />
              ) : metrics.qdrant_health === "degraded" ? (
                <AlertCircle className="h-5 w-5 text-amber-600" />
              ) : (
                <AlertCircle className="h-5 w-5 text-red-600" />
              )}
              <span className={cn(
                "text-2xl font-bold",
                metrics.qdrant_health === "healthy" ? "text-green-600" :
                metrics.qdrant_health === "degraded" ? "text-amber-600" :
                "text-red-600"
              )}>
                {metrics.qdrant_health.charAt(0).toUpperCase() + metrics.qdrant_health.slice(1)}
              </span>
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              {metrics.qdrant_health === "healthy" ? "All collections operational" :
               metrics.qdrant_health === "degraded" ? "Some collections degraded" :
               "Collections unavailable"}
            </p>
          </CardContent>
        </Card>

        {/* Next Scheduled Run */}
        <Card className="border-t-4 border-t-blue-500">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-[var(--foreground-muted)]">
              Next Scheduled Run
            </CardTitle>
            <Clock className="h-5 w-5 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-[var(--foreground)]">
              {metrics.next_scheduled_run ? formatTime(metrics.next_scheduled_run) : "N/A"}
            </div>
            <p className="mt-3 text-xs text-[var(--foreground-muted)]">
              {metrics.next_scheduled_run ? "Every 2 hours" : "Schedule pending"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Agent Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-bold text-[var(--foreground)]">
            Agent Configuration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-6">
            <div className="space-y-2">
              <p className="text-sm font-medium text-[var(--foreground-muted)]">
                LLM Provider
              </p>
              <p className="text-base font-semibold text-[var(--foreground)]">
                Gemini 2.0 Flash (Vision)
              </p>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-[var(--foreground-muted)]">
                Browser Engine
              </p>
              <p className="text-base font-semibold text-[var(--foreground)]">
                Playwright Webkit
              </p>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-[var(--foreground-muted)]">
                Target URL
              </p>
              <p className="text-base font-semibold text-[var(--foreground)]">
                imigrasi.go.id/wna/permohonan-visa
              </p>
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-[var(--foreground-muted)]">
                Change Detection
              </p>
              <p className="text-base font-semibold text-[var(--foreground)]">
                MD5 Hash + Vision Analysis
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
