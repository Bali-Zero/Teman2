"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useSessionState } from "@/hooks/useSessionState";
import { logger } from "@/lib/logger";
import { SystemHealthReport } from "@/lib/api/admin/admin.types";
import { ServiceHealthCard } from "@/components/admin/ServiceHealthCard";
import { DbExplorer } from "@/components/admin/DbExplorer";
import { VectorExplorer } from "@/components/admin/VectorExplorer";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Activity,
  Database,
  Server,
  Cpu,
  HardDrive,
  RefreshCw,
  Clock,
  Shield,
  Layers,
  Zap,
  Code2,
  Terminal,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Dashboard panel recipe — mirrors the day/dark-aware Kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
};

export default function SystemDashboardPage() {
  const router = useRouter();
  const session = useSessionState();
  const [report, setReport] = useState<SystemHealthReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);
  const [isAuthorized, setIsAuthorized] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      setError(null);
      const data = await api.getSystemHealth();
      setReport(data);
      setLastUpdated(new Date());
    } catch (err) {
      logger.error("Failed to fetch system health", {}, err as Error);
      setError("System unreachable");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // admin-only surface: DbExplorer (Postgres browser) + VectorExplorer (Qdrant) —
    // backend admin/system routes aren't mounted yet, so this frontend gate is the only guard today
    if (session === "anonymous") {
      router.push("/login");
      return;
    }
    if (session !== "authenticated") return;
    if (!api.isAdmin()) {
      router.push("/chat");
      return;
    }
    setIsAuthorized(true);
  }, [session, router]);

  useEffect(() => {
    if (!isAuthorized) return;
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [isAuthorized, fetchHealth]);

  if (!isAuthorized) {
    return (
      <div className="flex h-screen items-center justify-center text-[var(--state-success)] font-mono">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-12 h-12 animate-spin" />
          <p>VERIFYING ACCESS...</p>
        </div>
      </div>
    );
  }

  if (isLoading && !report) {
    return (
      <div className="flex h-screen items-center justify-center text-[var(--state-success)] font-mono">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-12 h-12 animate-spin" />
          <p>INITIALIZING CONTROL ROOM...</p>
        </div>
      </div>
    );
  }

  const metrics = report?.system_metrics;

  // Helper to map check names to icons
  const getIconForCheck = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.includes("database") || lower.includes("postgres"))
      return Database;
    if (lower.includes("redis")) return Zap;
    if (lower.includes("qdrant") || lower.includes("vector")) return Layers;
    if (lower.includes("api")) return Server;
    if (lower.includes("auth") || lower.includes("guard")) return Shield;
    return Activity;
  };

  return (
    <div className="min-h-screen text-[var(--bz-text-1)] p-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 border-b border-[var(--bz-border)] pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-widest text-[var(--state-success)] flex items-center gap-2">
            <Activity className="w-6 h-6" />
            SYSTEM CONTROL ROOM
          </h1>
          <p className="text-xs text-[var(--bz-text-2)] mt-1">
            LIVE REMOTE TELEMETRY // FLY.IO
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <p className="text-xs text-[var(--bz-text-2)]">LAST UPDATE</p>
            <p className="text-sm font-bold text-[var(--state-success)]">
              {lastUpdated.toLocaleTimeString("en-US")}
            </p>
          </div>
          <Button
            variant="outline"
            size="icon"
            onClick={fetchHealth}
            className="border-[var(--state-success)]/50 text-[var(--state-success)] hover:bg-[var(--state-success)]/10"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {error && (
        <div className="bg-[var(--state-danger)]/10 border border-[var(--state-danger)]/30 text-[var(--state-danger)] p-4 rounded-lg mb-8 text-center animate-pulse">
          ⚠️ CONNECTION LOST: {error}
        </div>
      )}

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="border border-[var(--bz-border)] p-1">
          <TabsTrigger
            value="overview"
            className="data-[state=active]:bg-[var(--state-success)]/20 data-[state=active]:text-[var(--state-success)] border-none rounded text-muted-foreground"
          >
            Overview
          </TabsTrigger>
          <TabsTrigger
            value="database"
            className="data-[state=active]:bg-[var(--state-info)]/20 data-[state=active]:text-[var(--state-info)] border-none rounded text-muted-foreground"
          >
            Database
          </TabsTrigger>
          <TabsTrigger
            value="vectors"
            className="data-[state=active]:bg-[var(--bz-neon-purple)]/20 data-[state=active]:text-[var(--bz-neon-purple)] border-none rounded text-muted-foreground"
          >
            Knowledge Vectors
          </TabsTrigger>
        </TabsList>

        <TabsContent
          value="overview"
          className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500"
        >
          {/* System Metrics Bar */}
          {metrics && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="border" style={PANEL}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium text-[var(--bz-text-2)] flex items-center gap-2">
                    <Cpu className="w-4 h-4" /> CPU LOAD
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[var(--state-success)]">
                    {metrics.cpu_usage.toFixed(1)}%
                  </div>
                  <Progress
                    value={metrics.cpu_usage}
                    className="h-1 mt-2 bg-[var(--bz-glass-rim)]"
                    indicatorClassName="bg-[var(--state-success)]"
                  />
                </CardContent>
              </Card>

              <Card className="border" style={PANEL}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium text-[var(--bz-text-2)] flex items-center gap-2">
                    <Layers className="w-4 h-4" /> MEMORY
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[var(--state-success)]">
                    {metrics.memory_usage.toFixed(1)}%
                  </div>
                  <Progress
                    value={metrics.memory_usage}
                    className="h-1 mt-2 bg-[var(--bz-glass-rim)]"
                    indicatorClassName="bg-[var(--state-success)]"
                  />
                </CardContent>
              </Card>

              <Card className="border" style={PANEL}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium text-[var(--bz-text-2)] flex items-center gap-2">
                    <HardDrive className="w-4 h-4" /> DISK
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[var(--state-success)]">
                    {metrics.disk_usage.toFixed(1)}%
                  </div>
                  <Progress
                    value={metrics.disk_usage}
                    className="h-1 mt-2 bg-[var(--bz-glass-rim)]"
                    indicatorClassName="bg-[var(--state-success)]"
                  />
                </CardContent>
              </Card>

              <Card className="border" style={PANEL}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs font-medium text-[var(--bz-text-2)] flex items-center gap-2">
                    <Clock className="w-4 h-4" /> UPTIME
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-[var(--state-success)]">
                    {(metrics.uptime / 3600).toFixed(1)}h
                  </div>
                  <p className="text-xs text-[var(--bz-text-3)] mt-1">
                    running smooth
                  </p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Services Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {report?.checks &&
              Object.entries(report.checks).map(([name, check]) => (
                <ServiceHealthCard
                  key={name}
                  name={name}
                  status={check.status}
                  message={check.message}
                  latency={check.latency_ms}
                  metadata={check.metadata}
                  icon={getIconForCheck(name)}
                />
              ))}
          </div>

          {/* Tech Stack List - Addressing User Request */}
          <Card className="border" style={PANEL}>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-[var(--bz-text-1)] flex items-center gap-2">
                <Code2 className="w-4 h-4" /> ACTIVE SYSTEM STACK
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono text-[var(--bz-text-2)]">
                <div className="flex items-center gap-2 p-2 bg-[var(--bz-glass-rim)] rounded">
                  <Database className="w-4 h-4 text-[var(--state-info)]" />
                  <span>PostgreSQL 15</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-[var(--bz-glass-rim)] rounded">
                  <Layers className="w-4 h-4 text-[var(--state-danger)]" />
                  <span>Qdrant (Vectors)</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-[var(--bz-glass-rim)] rounded">
                  <Zap className="w-4 h-4 text-[var(--state-warning)]" />
                  <span>Redis (Cache)</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-[var(--bz-glass-rim)] rounded">
                  <Server className="w-4 h-4 text-[var(--state-success)]" />
                  <span>FastAPI + Next.js</span>
                </div>
                <div className="flex items-center gap-2 p-2 bg-[var(--bz-glass-rim)] rounded">
                  <Terminal className="w-4 h-4 text-[var(--bz-neon-purple)]" />
                  <span>Fly.io (Compute)</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent
          value="database"
          className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300"
        >
          <Card className="border" style={PANEL}>
            <CardHeader>
              <CardTitle className="text-[var(--state-info)] text-lg flex items-center gap-2">
                <Database className="w-5 h-5" /> POSTGRES EXPLORER
              </CardTitle>
            </CardHeader>
            <CardContent>
              <DbExplorer />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent
          value="vectors"
          className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300"
        >
          <Card className="border" style={PANEL}>
            <CardHeader>
              <CardTitle className="text-[var(--bz-neon-purple)] text-lg flex items-center gap-2">
                <Layers className="w-5 h-5" /> QDRANT INSPECTOR
              </CardTitle>
            </CardHeader>
            <CardContent>
              <VectorExplorer />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
