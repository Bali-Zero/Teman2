"use client";

import React from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  FileText,
  Send,
  Clock,
  Zap,
  TrendingUp,
  Eye,
  Users,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";

// Mock data - will be replaced with API calls
const stats = {
  published_today: 8,
  scheduled: 12,
  in_review: 3,
  intel_signals: 12,
};

const recentContent = [
  {
    id: "1",
    title: "New KITAS Regulations 2025: What Expats Need to Know",
    status: "published",
    category: "immigration",
    published_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    engagements: 1240,
  },
  {
    id: "2",
    title: "Tax Filing Deadline Reminder for PT PMA Companies",
    status: "scheduled",
    category: "tax",
    scheduled_at: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: "3",
    title: "Bali Property Market Q1 2025 Analysis",
    status: "review",
    category: "property",
    updated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
  },
];

const intelSignals = [
  {
    id: "1",
    title: "New visa regulation detected - Imigrasi.go.id",
    priority: "high",
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    source: "Imigrasi",
  },
  {
    id: "2",
    title: "Tax deadline reminder trending on Twitter",
    priority: "medium",
    detected_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    source: "Twitter",
  },
  {
    id: "3",
    title: "Bali tourism stats released by BPS",
    priority: "low",
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    source: "BPS",
  },
];

const upcomingSchedule = [
  { time: "10:00", title: "Newsletter send", platform: "Email" },
  { time: "14:00", title: "TikTok video post", platform: "TikTok" },
  { time: "16:00", title: "Twitter thread", platform: "Twitter" },
  { time: "18:00", title: "LinkedIn article", platform: "LinkedIn" },
];

function StatCard({
  title,
  value,
  icon: Icon,
  trend,
}: {
  title: string;
  value: number | string;
  icon: React.ElementType;
  trend?: string;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-[var(--foreground-muted)]">{title}</p>
            <p className="text-2xl font-bold text-[var(--foreground)] mt-1">
              {value}
            </p>
            {trend && (
              <p className="text-xs text-[var(--success)] mt-1 flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />
                {trend}
              </p>
            )}
          </div>
          <div className="w-12 h-12 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center">
            <Icon className="w-6 h-6 text-[var(--accent)]" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function getStatusBadge(status: string) {
  switch (status) {
    case "published":
      return <Badge variant="success">Published</Badge>;
    case "scheduled":
      return <Badge variant="warning">Scheduled</Badge>;
    case "review":
      return <Badge variant="default">In Review</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function getPriorityBadge(priority: string) {
  switch (priority) {
    case "high":
      return <Badge variant="error">HIGH</Badge>;
    case "medium":
      return <Badge variant="warning">MED</Badge>;
    case "low":
      return <Badge variant="secondary">LOW</Badge>;
    default:
      return <Badge variant="secondary">{priority}</Badge>;
  }
}

export default function DashboardPage() {
  return (
    <DashboardLayout title="Dashboard">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          title="Published Today"
          value={stats.published_today}
          icon={FileText}
          trend="+12% vs yesterday"
        />
        <StatCard
          title="Scheduled"
          value={stats.scheduled}
          icon={Clock}
        />
        <StatCard
          title="In Review"
          value={stats.in_review}
          icon={Eye}
        />
        <StatCard
          title="Intel Signals"
          value={stats.intel_signals}
          icon={Zap}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Content Pipeline - Takes 2 columns */}
        <div className="lg:col-span-2 space-y-6">
          {/* Recent Content */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base font-semibold">
                Recent Content
              </CardTitle>
              <Button variant="ghost" size="sm" className="text-[var(--accent)]">
                View All
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {recentContent.map((content) => (
                  <div
                    key={content.id}
                    className="flex items-start justify-between p-3 rounded-lg hover:bg-[var(--background)] transition-colors cursor-pointer"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--foreground)] truncate">
                        {content.title}
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">
                          {content.category}
                        </Badge>
                        {content.engagements && (
                          <span className="text-xs text-[var(--foreground-muted)] flex items-center gap-1">
                            <Users className="w-3 h-3" />
                            {content.engagements.toLocaleString()}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 ml-4">
                      {getStatusBadge(content.status)}
                      <span className="text-xs text-[var(--foreground-muted)]">
                        {formatRelativeTime(
                          content.published_at ||
                            content.scheduled_at ||
                            content.updated_at ||
                            ""
                        )}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Intel Signals */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base font-semibold">
                  Intel Signals
                </CardTitle>
                <span className="flex items-center justify-center w-5 h-5 rounded-full bg-[var(--accent)] text-white text-xs">
                  {intelSignals.length}
                </span>
              </div>
              <Button variant="ghost" size="sm" className="text-[var(--accent)]">
                View All
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {intelSignals.map((signal) => (
                  <div
                    key={signal.id}
                    className="flex items-center gap-3 p-3 rounded-lg border border-[var(--border)] hover:border-[var(--border-hover)] transition-colors cursor-pointer"
                  >
                    <AlertCircle
                      className={`w-5 h-5 flex-shrink-0 ${
                        signal.priority === "high"
                          ? "text-[var(--error)]"
                          : signal.priority === "medium"
                          ? "text-[var(--warning)]"
                          : "text-[var(--foreground-muted)]"
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[var(--foreground)] truncate">
                        {signal.title}
                      </p>
                      <p className="text-xs text-[var(--foreground-muted)]">
                        {signal.source} · {formatRelativeTime(signal.detected_at)}
                      </p>
                    </div>
                    {getPriorityBadge(signal.priority)}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Sidebar */}
        <div className="space-y-6">
          {/* Today's Schedule */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">
                Today&apos;s Schedule
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {upcomingSchedule.map((item, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 text-sm"
                  >
                    <span className="text-[var(--foreground-muted)] w-12 flex-shrink-0">
                      {item.time}
                    </span>
                    <div className="flex-1">
                      <p className="text-[var(--foreground)]">{item.title}</p>
                      <p className="text-xs text-[var(--foreground-muted)]">
                        {item.platform}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">
                Quick Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button variant="outline" className="w-full justify-start gap-2">
                <FileText className="w-4 h-4" />
                Create Article
              </Button>
              <Button variant="outline" className="w-full justify-start gap-2">
                <Send className="w-4 h-4" />
                Schedule Post
              </Button>
              <Button variant="outline" className="w-full justify-start gap-2">
                <Zap className="w-4 h-4" />
                Process Intel
              </Button>
            </CardContent>
          </Card>

          {/* Platform Status */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-semibold">
                Platform Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  { name: "Twitter", status: "connected", followers: "12.4K" },
                  { name: "LinkedIn", status: "connected", followers: "8.2K" },
                  { name: "Instagram", status: "connected", followers: "15.1K" },
                  { name: "TikTok", status: "connected", followers: "5.8K" },
                  { name: "Telegram", status: "connected", followers: "3.2K" },
                ].map((platform) => (
                  <div
                    key={platform.name}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${
                          platform.status === "connected"
                            ? "bg-[var(--success)]"
                            : "bg-[var(--error)]"
                        }`}
                      />
                      <span className="text-[var(--foreground)]">
                        {platform.name}
                      </span>
                    </div>
                    <span className="text-[var(--foreground-muted)]">
                      {platform.followers}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
