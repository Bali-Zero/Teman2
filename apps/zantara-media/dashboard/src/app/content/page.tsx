"use client";

import React, { useState } from "react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Search,
  Plus,
  Filter,
  MoreHorizontal,
  FileText,
  Edit,
  Eye,
  Trash2,
  Clock,
  Send,
} from "lucide-react";
import { formatRelativeTime, truncate } from "@/lib/utils";
import type { Content, ContentStatus } from "@/types";

// Mock data
const mockContent: Content[] = [
  {
    id: "1",
    title: "New KITAS Regulations 2025: What Expats Need to Know",
    slug: "kitas-regulations-2025",
    type: "article",
    status: "published",
    category: "immigration",
    priority: "high",
    body: "Lorem ipsum...",
    summary: "Complete guide to the new KITAS regulations effective January 2025",
    author_id: "1",
    author_name: "Zero",
    created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    published_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    metadata: {
      word_count: 1250,
      reading_time_minutes: 5,
      ai_generated: false,
      language: "en",
    },
    distributions: [],
    tags: ["kitas", "visa", "2025", "regulations"],
  },
  {
    id: "2",
    title: "Tax Filing Deadline Reminder for PT PMA Companies",
    slug: "tax-filing-deadline-pt-pma",
    type: "article",
    status: "scheduled",
    category: "tax",
    priority: "high",
    body: "Lorem ipsum...",
    author_id: "1",
    author_name: "AI Writer",
    created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    scheduled_at: new Date(Date.now() + 4 * 60 * 60 * 1000).toISOString(),
    metadata: {
      word_count: 800,
      reading_time_minutes: 3,
      ai_generated: true,
      ai_model: "llama-4-scout",
      language: "en",
    },
    distributions: [],
    tags: ["tax", "pt pma", "deadline", "spt"],
  },
  {
    id: "3",
    title: "Bali Property Market Q1 2025 Analysis",
    slug: "bali-property-q1-2025",
    type: "article",
    status: "review",
    category: "property",
    priority: "normal",
    body: "Lorem ipsum...",
    author_id: "2",
    author_name: "Nina",
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    metadata: {
      word_count: 2100,
      reading_time_minutes: 8,
      ai_generated: false,
      language: "en",
    },
    distributions: [],
    tags: ["property", "bali", "market analysis", "q1 2025"],
  },
  {
    id: "4",
    title: "Quick Guide: Remote Worker Visa in 60 Seconds",
    slug: "remote-worker-visa-guide",
    type: "social_post",
    status: "draft",
    category: "immigration",
    priority: "normal",
    body: "Lorem ipsum...",
    author_id: "1",
    author_name: "AI Writer",
    created_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    metadata: {
      word_count: 150,
      reading_time_minutes: 1,
      ai_generated: true,
      ai_model: "gemini-flash",
      language: "en",
    },
    distributions: [],
    tags: ["remote worker", "visa", "digital nomad"],
  },
  {
    id: "5",
    title: "Weekly Newsletter: Indonesia Business Updates",
    slug: "weekly-newsletter-jan-w2",
    type: "newsletter",
    status: "intake",
    category: "general",
    priority: "normal",
    body: "",
    author_id: "1",
    author_name: "System",
    created_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(),
    metadata: {
      word_count: 0,
      reading_time_minutes: 0,
      ai_generated: false,
      language: "en",
    },
    distributions: [],
    tags: ["newsletter", "weekly"],
  },
];

const statusTabs: { value: ContentStatus | "all"; label: string; count: number }[] = [
  { value: "all", label: "All", count: mockContent.length },
  { value: "intake", label: "Intake", count: mockContent.filter((c) => c.status === "intake").length },
  { value: "draft", label: "Draft", count: mockContent.filter((c) => c.status === "draft").length },
  { value: "review", label: "Review", count: mockContent.filter((c) => c.status === "review").length },
  { value: "scheduled", label: "Scheduled", count: mockContent.filter((c) => c.status === "scheduled").length },
  { value: "published", label: "Published", count: mockContent.filter((c) => c.status === "published").length },
];

function getStatusBadge(status: ContentStatus) {
  const variants: Record<ContentStatus, "success" | "warning" | "default" | "secondary" | "error"> = {
    published: "success",
    scheduled: "warning",
    review: "default",
    approved: "success",
    draft: "secondary",
    intake: "secondary",
    archived: "secondary",
  };
  return <Badge variant={variants[status]}>{status}</Badge>;
}

function getTypeBadge(type: string) {
  const icons: Record<string, React.ReactNode> = {
    article: <FileText className="w-3 h-3" />,
    social_post: <Send className="w-3 h-3" />,
    newsletter: <FileText className="w-3 h-3" />,
  };
  return (
    <Badge variant="outline" className="gap-1">
      {icons[type]}
      {type.replace("_", " ")}
    </Badge>
  );
}

export default function ContentPage() {
  const [activeTab, setActiveTab] = useState<ContentStatus | "all">("all");
  const [searchQuery, setSearchQuery] = useState("");

  const filteredContent = mockContent.filter((content) => {
    const matchesTab = activeTab === "all" || content.status === activeTab;
    const matchesSearch =
      searchQuery === "" ||
      content.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      content.tags.some((tag) => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesTab && matchesSearch;
  });

  return (
    <DashboardLayout title="Content">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <Input
            placeholder="Search content..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <Filter className="w-4 h-4 mr-2" />
            Filter
          </Button>
          <Button size="sm">
            <Plus className="w-4 h-4 mr-2" />
            New Content
          </Button>
        </div>
      </div>

      {/* Status Tabs */}
      <Tabs defaultValue="all" onValueChange={(v) => setActiveTab(v as ContentStatus | "all")}>
        <TabsList className="mb-4 flex-wrap h-auto gap-1">
          {statusTabs.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} className="gap-2">
              {tab.label}
              <span className="text-xs bg-[var(--background)] px-1.5 py-0.5 rounded">
                {tab.count}
              </span>
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Content List */}
        <TabsContent value={activeTab} className="mt-0">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[var(--border)]">
                      <th className="text-left p-4 text-sm font-medium text-[var(--foreground-secondary)]">
                        Title
                      </th>
                      <th className="text-left p-4 text-sm font-medium text-[var(--foreground-secondary)] hidden md:table-cell">
                        Type
                      </th>
                      <th className="text-left p-4 text-sm font-medium text-[var(--foreground-secondary)]">
                        Status
                      </th>
                      <th className="text-left p-4 text-sm font-medium text-[var(--foreground-secondary)] hidden lg:table-cell">
                        Author
                      </th>
                      <th className="text-left p-4 text-sm font-medium text-[var(--foreground-secondary)] hidden md:table-cell">
                        Updated
                      </th>
                      <th className="text-right p-4 text-sm font-medium text-[var(--foreground-secondary)]">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredContent.map((content) => (
                      <tr
                        key={content.id}
                        className="border-b border-[var(--border)] hover:bg-[var(--background)] transition-colors cursor-pointer"
                      >
                        <td className="p-4">
                          <div>
                            <p className="text-sm font-medium text-[var(--foreground)]">
                              {truncate(content.title, 50)}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline" className="text-xs">
                                {content.category}
                              </Badge>
                              {content.metadata.ai_generated && (
                                <Badge variant="secondary" className="text-xs">
                                  AI
                                </Badge>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="p-4 hidden md:table-cell">
                          {getTypeBadge(content.type)}
                        </td>
                        <td className="p-4">{getStatusBadge(content.status)}</td>
                        <td className="p-4 hidden lg:table-cell">
                          <span className="text-sm text-[var(--foreground-secondary)]">
                            {content.author_name}
                          </span>
                        </td>
                        <td className="p-4 hidden md:table-cell">
                          <div className="flex items-center gap-1 text-sm text-[var(--foreground-muted)]">
                            <Clock className="w-3 h-3" />
                            {formatRelativeTime(content.updated_at)}
                          </div>
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <Edit className="w-4 h-4" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {filteredContent.length === 0 && (
                <div className="text-center py-12">
                  <FileText className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-4" />
                  <p className="text-[var(--foreground-secondary)]">No content found</p>
                  <p className="text-sm text-[var(--foreground-muted)]">
                    Try adjusting your search or filters
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </DashboardLayout>
  );
}
