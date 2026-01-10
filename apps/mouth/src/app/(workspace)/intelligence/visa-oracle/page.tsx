"use client";

import { useEffect, useState, useMemo } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import {
  Loader2,
  Check,
  X,
  FileText,
  ExternalLink,
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Eye,
  Filter,
  ArrowUpDown,
  Search,
  CheckSquare,
  Square,
} from "lucide-react";
import { cn } from "@/lib/utils";

type FilterType = "all" | "NEW" | "UPDATED";
type SortType = "date-desc" | "date-asc" | "title-asc" | "title-desc";

export default function VisaOraclePage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string>("");
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [sortType, setSortType] = useState<SortType>("date-desc");
  const [searchQuery, setSearchQuery] = useState("");
  const toast = useToast();

  // Filtered and sorted items
  const filteredAndSortedItems = useMemo(() => {
    let filtered = items;

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (item) =>
          item.title.toLowerCase().includes(query) ||
          item.id.toLowerCase().includes(query) ||
          item.source.toLowerCase().includes(query)
      );
    }

    // Apply type filter
    if (filterType !== "all") {
      filtered = filtered.filter((item) => item.detection_type === filterType);
    }

    // Apply sorting
    const sorted = [...filtered].sort((a, b) => {
      switch (sortType) {
        case "date-desc":
          return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
        case "date-asc":
          return new Date(a.detected_at).getTime() - new Date(b.detected_at).getTime();
        case "title-asc":
          return a.title.localeCompare(b.title);
        case "title-desc":
          return b.title.localeCompare(a.title);
        default:
          return 0;
      }
    });

    return sorted;
  }, [items, filterType, sortType, searchQuery]);

  useEffect(() => {
    logger.componentMount('VisaOraclePage');
    loadItems();

    return () => {
      logger.componentUnmount('VisaOraclePage');
    };
  }, []);

  const loadItems = async () => {
    logger.info('Loading visa items', { component: 'VisaOraclePage', action: 'load_items' });
    setLoading(true);
    try {
      const res = await intelligenceApi.getPendingItems("visa");
      setItems(res.items);
      logger.info(`Loaded ${res.count} visa items`, {
        component: 'VisaOraclePage',
        action: 'load_items_success',
        metadata: { count: res.count },
      });
    } catch (error) {
      logger.error('Failed to load visa items', { component: 'VisaOraclePage', action: 'load_items_error' }, error as Error);
      toast.error("Failed to load items", "Could not fetch pending visa updates.");
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (id: string, type: "visa" | "news") => {
    if (previewId === id) {
      logger.userAction('close_preview', type, id, { component: 'VisaOraclePage' });
      setPreviewId(null);
      setPreviewContent("");
      return;
    }

    logger.userAction('open_preview', type, id, { component: 'VisaOraclePage' });

    try {
      const item = await intelligenceApi.getPreview(type, id);
      setPreviewId(id);
      setPreviewContent(item.content || "No content available");
      logger.info(`Preview loaded for ${id}`, {
        component: 'VisaOraclePage',
        action: 'preview_success',
        itemType: type,
        itemId: id,
      });
    } catch (error) {
      logger.error(`Preview failed for ${id}`, {
        component: 'VisaOraclePage',
        action: 'preview_error',
        itemType: type,
        itemId: id,
      }, error as Error);
      toast.error("Preview failed", "Could not load content");
    }
  };

  const handleApprove = async (id: string) => {
    logger.userAction('approve_confirm_prompt', 'visa', id, { component: 'VisaOraclePage' });

    if (!confirm("This will ingest the content into the Knowledge Base. Continue?")) {
      logger.info('Approval cancelled by user', {
        component: 'VisaOraclePage',
        action: 'approve_cancelled',
        itemType: 'visa',
        itemId: id,
      });
      return;
    }

    logger.info('Starting approval process', {
      component: 'VisaOraclePage',
      action: 'approve_start',
      itemType: 'visa',
      itemId: id,
    });

    setProcessing(id);
    try {
      await intelligenceApi.approveItem("visa", id);
      toast.success(
        "Visa approved",
        "Item has been ingested into visa_oracle collection successfully."
      );
      setItems((prev) => prev.filter((i) => i.id !== id));
      if (previewId === id) {
        setPreviewId(null);
        setPreviewContent("");
      }
      logger.info('Approval completed successfully', {
        component: 'VisaOraclePage',
        action: 'approve_success',
        itemType: 'visa',
        itemId: id,
      });
    } catch (error) {
      logger.error('Approval failed', {
        component: 'VisaOraclePage',
        action: 'approve_error',
        itemType: 'visa',
        itemId: id,
      }, error as Error);
      toast.error("Approval failed", "Could not ingest item. Check backend logs.");
    } finally {
      setProcessing(null);
    }
  };

  const toggleSelectItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === filteredAndSortedItems.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(filteredAndSortedItems.map((item) => item.id)));
    }
  };

  const handleBulkApprove = async () => {
    if (selectedItems.size === 0) {
      toast.error("No items selected", "Please select items to approve.");
      return;
    }

    if (!confirm(`Approve ${selectedItems.size} item(s)? This will ingest them into the Knowledge Base.`)) {
      return;
    }

    logger.info('Starting bulk approval', {
      component: 'VisaOraclePage',
      action: 'bulk_approve_start',
      metadata: { count: selectedItems.size },
    });

    const ids = Array.from(selectedItems);
    const results = { success: 0, failed: 0 };

    for (const id of ids) {
      setProcessing(id);
      try {
        await intelligenceApi.approveItem("visa", id);
        results.success++;
        setItems((prev) => prev.filter((i) => i.id !== id));
      } catch (error) {
        results.failed++;
        logger.error('Bulk approval failed for item', {
          component: 'VisaOraclePage',
          action: 'bulk_approve_error',
          itemId: id,
        }, error as Error);
      } finally {
        setProcessing(null);
      }
    }

    setSelectedItems(new Set());
    toast.success(
      "Bulk approval completed",
      `${results.success} approved, ${results.failed} failed.`
    );

    logger.info('Bulk approval completed', {
      component: 'VisaOraclePage',
      action: 'bulk_approve_complete',
      metadata: results,
    });
  };

  const handleBulkReject = async () => {
    if (selectedItems.size === 0) {
      toast.error("No items selected", "Please select items to reject.");
      return;
    }

    if (!confirm(`Reject ${selectedItems.size} item(s)? They will be archived.`)) {
      return;
    }

    logger.info('Starting bulk rejection', {
      component: 'VisaOraclePage',
      action: 'bulk_reject_start',
      metadata: { count: selectedItems.size },
    });

    const ids = Array.from(selectedItems);
    const results = { success: 0, failed: 0 };

    for (const id of ids) {
      setProcessing(id);
      try {
        await intelligenceApi.rejectItem("visa", id);
        results.success++;
        setItems((prev) => prev.filter((i) => i.id !== id));
      } catch (error) {
        results.failed++;
        logger.error('Bulk rejection failed for item', {
          component: 'VisaOraclePage',
          action: 'bulk_reject_error',
          itemId: id,
        }, error as Error);
      } finally {
        setProcessing(null);
      }
    }

    setSelectedItems(new Set());
    toast.success(
      "Bulk rejection completed",
      `${results.success} rejected, ${results.failed} failed.`
    );

    logger.info('Bulk rejection completed', {
      component: 'VisaOraclePage',
      action: 'bulk_reject_complete',
      metadata: results,
    });
  };

  const handleReject = async (id: string) => {
    logger.userAction('reject_confirm_prompt', 'visa', id, { component: 'VisaOraclePage' });

    if (!confirm("Are you sure you want to reject this update? It will be archived.")) {
      logger.info('Rejection cancelled by user', {
        component: 'VisaOraclePage',
        action: 'reject_cancelled',
        itemType: 'visa',
        itemId: id,
      });
      return;
    }

    logger.info('Starting rejection process', {
      component: 'VisaOraclePage',
      action: 'reject_start',
      itemType: 'visa',
      itemId: id,
    });

    setProcessing(id);
    try {
      await intelligenceApi.rejectItem("visa", id);
      toast.success("Update rejected", "Item has been archived as rejected.");
      setItems((prev) => prev.filter((i) => i.id !== id));
      if (previewId === id) {
        setPreviewId(null);
        setPreviewContent("");
      }
      logger.info('Rejection completed successfully', {
        component: 'VisaOraclePage',
        action: 'reject_success',
        itemType: 'visa',
        itemId: id,
      });
    } catch (error) {
      logger.error('Rejection failed', {
        component: 'VisaOraclePage',
        action: 'reject_error',
        itemType: 'visa',
        itemId: id,
      }, error as Error);
      toast.error("Rejection failed", "Could not archive item. Check backend logs.");
    } finally {
      setProcessing(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-[var(--accent)]" />
        <p className="text-[var(--foreground-muted)] animate-pulse text-lg">
          Scanning Intelligence Feed...
        </p>
      </div>
    );
  }

  if (items.length === 0 || filteredAndSortedItems.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 bg-[var(--background-secondary)] rounded-2xl border-2 border-dashed border-[var(--border)]">
        <div className="bg-[var(--accent)]/10 p-6 rounded-full mb-6">
          <Sparkles className="h-12 w-12 text-[var(--accent)]" />
        </div>
        <h3 className="text-2xl font-bold text-[var(--foreground)] mb-2">
          All Caught Up!
        </h3>
        <p className="text-[var(--foreground-muted)] text-center max-w-md mb-8">
          {items.length === 0
            ? "No pending visa updates detected. The Intelligent Visa Agent is continuously monitoring imigrasi.go.id for new regulations."
            : "No items match your current filters. Try adjusting your search or filters."}
        </p>
        <Button
          variant="outline"
          className="gap-2"
          onClick={loadItems}
        >
          <RefreshCw className="w-4 h-4" />
          Check Again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Stats Bar */}
      <div className="flex justify-between items-center p-4 rounded-lg bg-[var(--background-elevated)] border border-[var(--border)]">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-500" />
            <span className="text-sm font-medium text-[var(--foreground)]">
              {filteredAndSortedItems.length} of {items.length} {items.length === 1 ? "item" : "items"} pending review
            </span>
          </div>
          <div className="h-4 w-px bg-[var(--border)]" />
          <div className="text-sm text-[var(--foreground-muted)]">
            {items.filter((i) => i.detection_type === "NEW").length} new ·{" "}
            {items.filter((i) => i.detection_type === "UPDATED").length} updated
          </div>
          {selectedItems.size > 0 && (
            <>
              <div className="h-4 w-px bg-[var(--border)]" />
              <div className="text-sm font-medium text-[var(--accent)]">
                {selectedItems.size} selected
              </div>
            </>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={loadItems} className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      {/* Filters and Bulk Actions */}
      <div className="flex flex-col sm:flex-row gap-4 p-4 rounded-lg bg-[var(--background-elevated)] border border-[var(--border)]">
        {/* Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-[var(--foreground-muted)]" />
          <Input
            placeholder="Search by title, ID, or source..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Filters */}
        <div className="flex gap-2">
          <Select value={filterType} onValueChange={(value) => setFilterType(value as FilterType)}>
            <SelectTrigger className="w-[140px]">
              <Filter className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="NEW">New Only</SelectItem>
              <SelectItem value="UPDATED">Updated Only</SelectItem>
            </SelectContent>
          </Select>

          <Select value={sortType} onValueChange={(value) => setSortType(value as SortType)}>
            <SelectTrigger className="w-[160px]">
              <ArrowUpDown className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date-desc">Newest First</SelectItem>
              <SelectItem value="date-asc">Oldest First</SelectItem>
              <SelectItem value="title-asc">Title A-Z</SelectItem>
              <SelectItem value="title-desc">Title Z-A</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Bulk Actions */}
        {selectedItems.size > 0 && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={toggleSelectAll}
              className="gap-2"
            >
              {selectedItems.size === filteredAndSortedItems.length ? (
                <>
                  <CheckSquare className="w-4 h-4" />
                  Deselect All
                </>
              ) : (
                <>
                  <Square className="w-4 h-4" />
                  Select All
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleBulkApprove}
              className="gap-2 text-green-600 hover:text-green-700 hover:bg-green-50 border-green-200"
              disabled={!!processing}
            >
              <Check className="w-4 h-4" />
              Approve ({selectedItems.size})
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleBulkReject}
              className="gap-2 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
              disabled={!!processing}
            >
              <X className="w-4 h-4" />
              Reject ({selectedItems.size})
            </Button>
          </div>
        )}
      </div>

      {/* Items Grid */}
      <div className="grid gap-4">
        {filteredAndSortedItems.map((item) => (
          <Card
            key={item.id}
            className={cn(
              "group overflow-hidden transition-all duration-200",
              "border-l-4 shadow-sm hover:shadow-lg",
              item.detection_type === "NEW"
                ? "border-l-blue-500"
                : "border-l-amber-500"
            )}
          >
            <CardHeader className="bg-[var(--background-secondary)] pb-4">
              <div className="flex justify-between items-start gap-4">
                <div className="flex items-start gap-3 flex-1">
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleSelectItem(item.id)}
                    className="mt-1 p-1 rounded hover:bg-[var(--background-elevated)] transition-colors"
                    aria-label={`Select ${item.title}`}
                  >
                    {selectedItems.has(item.id) ? (
                      <CheckSquare className="w-5 h-5 text-[var(--accent)]" />
                    ) : (
                      <Square className="w-5 h-5 text-[var(--foreground-muted)]" />
                    )}
                  </button>
                  <div className="space-y-2 flex-1">
                  {/* Badge */}
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-3 py-1 text-xs font-bold shadow-sm",
                        item.detection_type === "NEW"
                          ? "bg-blue-100 text-blue-700 border border-blue-200"
                          : "bg-amber-100 text-amber-700 border border-amber-200"
                      )}
                    >
                      {item.detection_type === "NEW"
                        ? "✨ NEW REGULATION"
                        : "📝 UPDATED POLICY"}
                    </span>
                  </div>

                  {/* Title */}
                  <CardTitle className="text-xl group-hover:text-[var(--accent)] transition-colors">
                    {item.title}
                  </CardTitle>

                  {/* Metadata */}
                  <div className="flex items-center gap-4 text-xs text-[var(--foreground-muted)]">
                    <div className="flex items-center gap-1.5">
                      <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent)]" />
                      <span className="font-mono">ID: {item.id}</span>
                    </div>
                    <div className="h-3 w-px bg-[var(--border)]" />
                    <span>
                      Detected {new Date(item.detected_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </span>
                  </div>
                  </div>
                </div>

                {/* Source Link */}
                <a
                  href={item.source}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent)]/10 border border-[var(--accent)]/20 transition-all"
                >
                  Official Source
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>
            </CardHeader>

            <CardContent className="pt-6 space-y-4">
              {/* Preview Section */}
              {previewId === item.id && (
                <div className="mb-4 p-4 rounded-lg bg-[var(--background)] border border-[var(--border)]">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-semibold text-[var(--foreground)]">
                      Content Preview
                    </h4>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setPreviewId(null);
                        setPreviewContent("");
                      }}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                  <pre className="text-xs text-[var(--foreground-muted)] whitespace-pre-wrap font-mono max-h-64 overflow-auto p-3 bg-[var(--background-secondary)] rounded">
                    {previewContent}
                  </pre>
                </div>
              )}

              {/* Info Box */}
              <div className="flex items-center gap-3 p-3 rounded-lg bg-[var(--background)]">
                <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-[var(--accent)]/10">
                  <FileText className="w-5 h-5 text-[var(--accent)]" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-[var(--foreground)]">
                    Processing Required
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)]">
                    Will be ingested into <code className="font-mono bg-[var(--background-secondary)] px-1 py-0.5 rounded">visa_oracle</code> collection
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3 pt-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-2"
                  onClick={() => handlePreview(item.id, item.type)}
                >
                  <Eye className="w-4 h-4" />
                  {previewId === item.id ? "Hide Preview" : "View Content"}
                </Button>

                <div className="flex-1" />

                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                  onClick={() => handleReject(item.id)}
                  disabled={!!processing}
                >
                  <X className="w-4 h-4" />
                  Reject
                </Button>

                <Button
                  size="sm"
                  className="gap-2 bg-green-600 hover:bg-green-700 text-white shadow-sm hover:shadow-md"
                  onClick={() => handleApprove(item.id)}
                  disabled={!!processing}
                >
                  {processing === item.id ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Ingesting...
                    </>
                  ) : (
                    <>
                      <Check className="w-4 h-4" />
                      Approve & Ingest
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
