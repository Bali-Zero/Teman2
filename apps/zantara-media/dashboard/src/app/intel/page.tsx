"use client";

import React, { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Search,
  Filter,
  Zap,
  ExternalLink,
  FileText,
  Check,
  X,
  Clock,
  AlertCircle,
  TrendingUp,
  RefreshCw,
} from "lucide-react";
import { formatRelativeTime, truncate } from "@/lib/utils";
import type { IntelSignal, ContentCategory } from "@/types";

// Mock data
const mockSignals: IntelSignal[] = [
  {
    id: "1",
    title: "New visa regulation: E33G Remote Worker KITAS processing time reduced to 3 days",
    source_name: "Imigrasi Indonesia",
    source_url: "https://imigrasi.go.id/news/123",
    category: "immigration",
    priority: "high",
    summary: "The Directorate General of Immigration announced that E33G Remote Worker KITAS applications will now be processed within 3 working days, down from the previous 5-7 days.",
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    processed: false,
  },
  {
    id: "2",
    title: "Tax deadline reminder: SPT Tahunan due March 31, 2025",
    source_name: "DJP Online",
    source_url: "https://djponline.pajak.go.id/",
    category: "tax",
    priority: "high",
    summary: "Annual tax return (SPT Tahunan) deadline approaching. PT PMA companies must file by March 31, 2025. Late filing incurs IDR 1,000,000 penalty.",
    detected_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
    processed: false,
  },
  {
    id: "3",
    title: "Bali tourism arrivals hit record high in December 2024",
    source_name: "BPS Statistics",
    source_url: "https://bps.go.id/",
    category: "bali_news",
    priority: "medium",
    summary: "Bali welcomed 1.2 million international visitors in December 2024, the highest monthly figure since 2019. Australian tourists led the arrivals.",
    detected_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    processed: true,
    content_id: "article-123",
  },
  {
    id: "4",
    title: "New KBLI codes added for tech sector businesses",
    source_name: "OSS Indonesia",
    source_url: "https://oss.go.id/",
    category: "business",
    priority: "medium",
    summary: "OSS system updated with 15 new KBLI codes specifically for technology and digital services sector. Includes AI development, cloud services, and fintech.",
    detected_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    processed: false,
  },
  {
    id: "5",
    title: "Property foreign ownership regulations under review",
    source_name: "Kementerian ATR/BPN",
    source_url: "https://atr.bpn.go.id/",
    category: "property",
    priority: "low",
    summary: "Ministry reviewing regulations on foreign property ownership. Discussions ongoing about extending HGB rights for foreigners from 80 to 100 years.",
    detected_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    processed: false,
  },
  {
    id: "6",
    title: "BPJS Kesehatan premium rates unchanged for 2025",
    source_name: "BPJS Kesehatan",
    source_url: "https://bpjs-kesehatan.go.id/",
    category: "legal",
    priority: "low",
    summary: "BPJS confirms health insurance premium rates will remain the same for 2025. No changes to coverage or contribution amounts.",
    detected_at: new Date(Date.now() - 36 * 60 * 60 * 1000).toISOString(),
    processed: true,
  },
];

const categoryFilters: { value: ContentCategory | "all"; label: string }[] = [
  { value: "all", label: "All Categories" },
  { value: "immigration", label: "Immigration" },
  { value: "tax", label: "Tax" },
  { value: "business", label: "Business" },
  { value: "property", label: "Property" },
  { value: "legal", label: "Legal" },
  { value: "bali_news", label: "Bali News" },
];

function getPriorityIcon(priority: string) {
  switch (priority) {
    case "high":
      return <AlertCircle className="w-5 h-5 text-[var(--error)]" />;
    case "medium":
      return <TrendingUp className="w-5 h-5 text-[var(--warning)]" />;
    default:
      return <Clock className="w-5 h-5 text-[var(--foreground-muted)]" />;
  }
}

function getPriorityBadge(priority: string) {
  switch (priority) {
    case "high":
      return <Badge variant="error">HIGH</Badge>;
    case "medium":
      return <Badge variant="warning">MEDIUM</Badge>;
    default:
      return <Badge variant="secondary">LOW</Badge>;
  }
}

export default function IntelPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<ContentCategory | "all">("all");
  const [showProcessed, setShowProcessed] = useState(false);

  const filteredSignals = mockSignals.filter((signal) => {
    const matchesSearch =
      searchQuery === "" ||
      signal.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      signal.source_name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = categoryFilter === "all" || signal.category === categoryFilter;
    const matchesProcessed = showProcessed || !signal.processed;
    return matchesSearch && matchesCategory && matchesProcessed;
  });

  const unprocessedCount = mockSignals.filter((s) => !s.processed).length;

  return (
    <DashboardLayout title="Intel Signals">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center">
              <Zap className="w-5 h-5 text-[var(--accent)]" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">{unprocessedCount}</p>
              <p className="text-sm text-[var(--foreground-muted)]">Pending</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[var(--error)]/10 flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-[var(--error)]" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">
                {mockSignals.filter((s) => s.priority === "high" && !s.processed).length}
              </p>
              <p className="text-sm text-[var(--foreground-muted)]">High Priority</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[var(--success)]/10 flex items-center justify-center">
              <Check className="w-5 h-5 text-[var(--success)]" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">
                {mockSignals.filter((s) => s.processed).length}
              </p>
              <p className="text-sm text-[var(--foreground-muted)]">Processed</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-[var(--background-elevated)] flex items-center justify-center">
              <RefreshCw className="w-5 h-5 text-[var(--foreground-secondary)]" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">630+</p>
              <p className="text-sm text-[var(--foreground-muted)]">Sources</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <Input
            placeholder="Search signals..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value as ContentCategory | "all")}
            className="h-10 px-3 rounded-md border border-[var(--border)] bg-[var(--background-input)] text-sm text-[var(--foreground)]"
          >
            {categoryFilters.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>
          <Button
            variant={showProcessed ? "secondary" : "outline"}
            size="sm"
            onClick={() => setShowProcessed(!showProcessed)}
          >
            {showProcessed ? "Hide" : "Show"} Processed
          </Button>
          <Button variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Signals List */}
      <div className="space-y-4">
        {filteredSignals.map((signal) => (
          <Card
            key={signal.id}
            className={signal.processed ? "opacity-60" : ""}
          >
            <CardContent className="p-4">
              <div className="flex items-start gap-4">
                {getPriorityIcon(signal.priority)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <h3 className="text-sm font-medium text-[var(--foreground)] mb-1">
                        {signal.title}
                      </h3>
                      <p className="text-sm text-[var(--foreground-muted)] mb-2">
                        {truncate(signal.summary, 200)}
                      </p>
                      <div className="flex items-center gap-3 flex-wrap">
                        <Badge variant="outline">{signal.category}</Badge>
                        {getPriorityBadge(signal.priority)}
                        <span className="text-xs text-[var(--foreground-muted)]">
                          {signal.source_name}
                        </span>
                        <span className="text-xs text-[var(--foreground-muted)]">
                          {formatRelativeTime(signal.detected_at)}
                        </span>
                        {signal.processed && (
                          <Badge variant="success" className="gap-1">
                            <Check className="w-3 h-3" />
                            Processed
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <Button variant="ghost" size="icon" asChild>
                        <a href={signal.source_url} target="_blank" rel="noopener noreferrer">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </Button>
                      {!signal.processed && (
                        <>
                          <Button variant="outline" size="sm" className="gap-1">
                            <FileText className="w-4 h-4" />
                            Create Content
                          </Button>
                          <Button variant="ghost" size="icon">
                            <X className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {filteredSignals.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <Zap className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-4" />
              <p className="text-[var(--foreground-secondary)]">No signals found</p>
              <p className="text-sm text-[var(--foreground-muted)]">
                Try adjusting your filters or check back later
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
