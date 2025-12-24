'use client';

import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { SystemHealthReport } from '@/lib/api/admin/admin.types';
import { ServiceHealthCard } from '@/components/admin/ServiceHealthCard';
import { DbExplorer } from '@/components/admin/DbExplorer';
import { VectorExplorer } from '@/components/admin/VectorExplorer';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function SystemDashboardPage() {
  const [report, setReport] = useState<SystemHealthReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      setError(null);
      const data = await api.getSystemHealth();
      setReport(data);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to fetch system health:', err);
      setError('System unreachable');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [fetchHealth]);

  if (isLoading && !report) {
    return (
      <div className="flex h-screen items-center justify-center bg-black text-green-500 font-mono">
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
    if (lower.includes('database') || lower.includes('postgres')) return Database;
    if (lower.includes('redis')) return Zap;
    if (lower.includes('qdrant') || lower.includes('vector')) return Layers;
    if (lower.includes('api')) return Server;
    if (lower.includes('auth') || lower.includes('guard')) return Shield;
    return Activity;
  };

  return (
    <div className="min-h-screen bg-black text-white p-6 font-mono">
      {/* Header */}
      <div className="flex items-center justify-between mb-8 border-b border-green-900/50 pb-4">
        <div>
            <h1 className="text-2xl font-bold tracking-widest text-green-500 flex items-center gap-2">
                <Activity className="w-6 h-6" />
                SYSTEM CONTROL ROOM
            </h1>
            <p className="text-xs text-green-500/60 mt-1">
                LIVE REMOTE TELEMETRY // FLY.IO
            </p>
        </div>
        <div className="flex items-center gap-4">
            <div className="text-right">
                <p className="text-xs text-green-500/60">LAST UPDATE</p>
                <p className="text-sm font-bold text-green-500">
                    {lastUpdated.toLocaleTimeString()}
                </p>
            </div>
            <Button 
                variant="outline" 
                size="icon" 
                onClick={fetchHealth}
                className="border-green-500/50 text-green-500 hover:bg-green-500/10 hover:text-green-400"
            >
                <RefreshCw className="w-4 h-4" />
            </Button>
        </div>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-500/50 text-red-500 p-4 rounded-lg mb-8 text-center animate-pulse">
            ⚠️ CONNECTION LOST: {error}
        </div>
      )}

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList className="bg-black border border-white/10 p-1">
            <TabsTrigger value="overview" className="data-[state=active]:bg-green-500/20 data-[state=active]:text-green-500 border-none rounded text-muted-foreground">Overview</TabsTrigger>
            <TabsTrigger value="database" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-500 border-none rounded text-muted-foreground">Database</TabsTrigger>
            <TabsTrigger value="vectors" className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-500 border-none rounded text-muted-foreground">Knowledge Vectors</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
             {/* System Metrics Bar */}
            {metrics && (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <Card className="bg-black border-green-900/50">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-green-500/60 flex items-center gap-2">
                                <Cpu className="w-4 h-4" /> CPU LOAD
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-400">{metrics.cpu_usage.toFixed(1)}%</div>
                            <Progress value={metrics.cpu_usage} className="h-1 mt-2 bg-green-900/30" indicatorClassName="bg-green-500" />
                        </CardContent>
                    </Card>
                    
                    <Card className="bg-black border-green-900/50">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-green-500/60 flex items-center gap-2">
                                <Layers className="w-4 h-4" /> MEMORY
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-400">{metrics.memory_usage.toFixed(1)}%</div>
                            <Progress value={metrics.memory_usage} className="h-1 mt-2 bg-green-900/30" indicatorClassName="bg-green-500" />
                        </CardContent>
                    </Card>

                    <Card className="bg-black border-green-900/50">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-green-500/60 flex items-center gap-2">
                                <HardDrive className="w-4 h-4" /> DISK
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-400">{metrics.disk_usage.toFixed(1)}%</div>
                            <Progress value={metrics.disk_usage} className="h-1 mt-2 bg-green-900/30" indicatorClassName="bg-green-500" />
                        </CardContent>
                    </Card>

                    <Card className="bg-black border-green-900/50">
                        <CardHeader className="pb-2">
                            <CardTitle className="text-xs font-medium text-green-500/60 flex items-center gap-2">
                                <Clock className="w-4 h-4" /> UPTIME
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-400">
                                {(metrics.uptime / 3600).toFixed(1)}h
                            </div>
                            <p className="text-xs text-green-500/40 mt-1">running smooth</p>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* Services Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {report?.checks && Object.entries(report.checks).map(([name, check]) => (
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
             <Card className="bg-black/40 border-green-900/30">
                <CardHeader>
                    <CardTitle className="text-sm font-medium text-green-500/80 flex items-center gap-2">
                         <Code2 className="w-4 h-4" /> ACTIVE SYSTEM STACK
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono text-zinc-400">
                        <div className="flex items-center gap-2 p-2 bg-white/5 rounded">
                            <Database className="w-4 h-4 text-blue-400" />
                            <span>PostgreSQL 15</span>
                        </div>
                        <div className="flex items-center gap-2 p-2 bg-white/5 rounded">
                             <Layers className="w-4 h-4 text-red-500" />
                            <span>Qdrant (Vectors)</span>
                        </div>
                         <div className="flex items-center gap-2 p-2 bg-white/5 rounded">
                            <Zap className="w-4 h-4 text-orange-500" />
                            <span>Redis (Cache)</span>
                        </div>
                         <div className="flex items-center gap-2 p-2 bg-white/5 rounded">
                            <Server className="w-4 h-4 text-green-400" />
                            <span>FastAPI + Next.js</span>
                        </div>
                         <div className="flex items-center gap-2 p-2 bg-white/5 rounded">
                            <Terminal className="w-4 h-4 text-purple-400" />
                            <span>Fly.io (Compute)</span>
                        </div>
                    </div>
                </CardContent>
             </Card>
        </TabsContent>

        <TabsContent value="database" className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
            <Card className="bg-black border-blue-900/30 border">
                <CardHeader>
                    <CardTitle className="text-blue-500 text-lg flex items-center gap-2">
                        <Database className="w-5 h-5" /> POSTGRES EXPLORER
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <DbExplorer />
                </CardContent>
            </Card>
        </TabsContent>

        <TabsContent value="vectors" className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
             <Card className="bg-black border-purple-900/30 border">
                <CardHeader>
                    <CardTitle className="text-purple-500 text-lg flex items-center gap-2">
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
