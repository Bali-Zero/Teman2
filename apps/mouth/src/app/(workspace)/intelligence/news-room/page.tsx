"use client";

import { useEffect, useState, useMemo } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { cn, renderMiniMarkdown } from "@/lib/utils";
import { logger } from "@/lib/logger";
import {
  Loader2,
  ExternalLink,
  Calendar,
  RefreshCw,
  Sparkles,
  Flame,
  Filter,
  ArrowUpDown,
  Search,
  CheckSquare,
  Square,
  Check,
  X,
  Eye,
  Edit,
  Image as ImageIcon,
  MapPin,
} from "lucide-react";
import { ArticleEditor } from "./components/ArticleEditor";
import { CoverImageUploader } from "./components/CoverImageUploader";

type FilterType = "all" | "NEW" | "UPDATED" | "critical";
type SortType = "date-desc" | "date-asc" | "title-asc" | "title-desc";

export default function NewsRoomPage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishingIds, setPublishingIds] = useState<Set<string>>(new Set());
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [sortType, setSortType] = useState<SortType>("date-desc");
  const [searchQuery, setSearchQuery] = useState("");
  const [previewItem, setPreviewItem] = useState<StagingItem | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [editingItem, setEditingItem] = useState<StagingItem | null>(null);
  const [coverUploadItem, setCoverUploadItem] = useState<StagingItem | null>(
    null,
  );
  const toast = useToast();
  const [publishPosition, setPublishPosition] = useState<
    Record<string, string>
  >({});
  const getPosition = (id: string) => publishPosition[id] || "latest";

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
          (item.source && item.source.toLowerCase().includes(query)),
      );
    }

    // Apply type filter
    if (filterType === "critical") {
      filtered = filtered.filter((item) => item.is_critical === true);
    } else if (filterType !== "all") {
      filtered = filtered.filter((item) => item.detection_type === filterType);
    }

    // Apply sorting
    const sorted = [...filtered].sort((a, b) => {
      switch (sortType) {
        case "date-desc":
          return (
            new Date(b.detected_at).getTime() -
            new Date(a.detected_at).getTime()
          );
        case "date-asc":
          return (
            new Date(a.detected_at).getTime() -
            new Date(b.detected_at).getTime()
          );
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
    logger.componentMount("NewsRoomPage");
    loadNews();

    return () => {
      logger.componentUnmount("NewsRoomPage");
    };
  }, []);

  const loadNews = async () => {
    logger.info("Loading news items", {
      component: "NewsRoomPage",
      action: "load_news",
    });
    setLoading(true);
    try {
      const res = await intelligenceApi.getPendingItems("all");
      setItems(res.items);
      logger.info(`Loaded ${res.count} news items`, {
        component: "NewsRoomPage",
        action: "load_news_success",
        metadata: {
          count: res.count,
          criticalCount: res.items.filter((i) => i.is_critical).length,
        },
      });
    } catch (error) {
      logger.error(
        "Failed to load news items",
        {
          component: "NewsRoomPage",
          action: "load_news_error",
        },
        error as Error,
      );
      toast.error("Error", "Failed to load news drafts");
    } finally {
      setLoading(false);
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

  const handleBulkPublish = async () => {
    if (selectedItems.size === 0) {
      toast.error("No items selected", "Please select items to publish.");
      return;
    }

    logger.info("Starting bulk publish", {
      component: "NewsRoomPage",
      action: "bulk_publish_start",
      metadata: { count: selectedItems.size },
    });

    const ids = Array.from(selectedItems);
    const results = { success: 0, failed: 0 };

    for (const id of ids) {
      setPublishingIds((prev) => new Set(prev).add(id));
      const item = items.find((i) => i.id === id);
      if (!item) continue;

      try {
        await intelligenceApi.publishItem(item.type, id, getPosition(id));
        results.success++;
        setItems((prev) => prev.filter((i) => i.id !== id));
      } catch (error) {
        results.failed++;
        logger.error(
          "Bulk publish failed for item",
          {
            component: "NewsRoomPage",
            action: "bulk_publish_error",
            itemId: id,
          },
          error as Error,
        );
      } finally {
        setPublishingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    }

    setSelectedItems(new Set());
    toast.success(
      "Bulk publish completed",
      `${results.success} published, ${results.failed} failed.`,
    );

    logger.info("Bulk publish completed", {
      component: "NewsRoomPage",
      action: "bulk_publish_complete",
      metadata: results,
    });

    loadNews();
  };

  const handlePreview = async (item: StagingItem) => {
    setPreviewLoading(true);
    try {
      const fullItem = await intelligenceApi.getPreview(item.type, item.id);
      setPreviewItem({
        ...fullItem,
        id: fullItem.id ?? item.id,
        type: fullItem.type ?? item.type,
      });
    } catch (error) {
      logger.error(
        "Failed to load preview",
        {
          component: "NewsRoomPage",
          action: "preview_error",
          itemId: item.id,
        },
        error as Error,
      );
      toast.error("Error", "Failed to load article preview");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handlePublish = async (item: StagingItem) => {
    const position = getPosition(item.id);

    logger.info("Publishing item", {
      component: "NewsRoomPage",
      action: "publish_item",
      itemId: item.id,
      metadata: { title: item.title, position },
    });

    // Add to publishing set
    setPublishingIds((prev) => new Set(prev).add(item.id));

    try {
      const response = await intelligenceApi.publishItem(
        item.type,
        item.id,
        position,
      );

      logger.info("Item published successfully", {
        component: "NewsRoomPage",
        action: "publish_success",
        itemId: item.id,
        metadata: { published_url: response.published_url, position },
      });

      toast.success(
        "Published!",
        `"${response.title}" published${position !== "latest" ? ` to ${position.replace("_", " ")}` : ""}`,
      );

      // Reload news list to remove published item
      loadNews();
    } catch (error) {
      logger.error(
        "Failed to publish item",
        {
          component: "NewsRoomPage",
          action: "publish_error",
          itemId: item.id,
        },
        error as Error,
      );

      toast.error("Error", "Failed to publish article");
    } finally {
      // Remove from publishing set
      setPublishingIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <Loader2
          className="w-8 h-8 animate-spin"
          style={{ color: "var(--bz-accent)" }}
        />
        <p
          className="text-[12px] animate-pulse"
          style={{ color: "var(--bz-text-2)" }}
        >
          Gathering Intelligence...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div
        className="flex flex-col sm:flex-row gap-3 px-4 py-3 rounded-2xl border mb-6"
        style={{
          background: "rgba(255,255,255,0.03)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderColor: "rgba(255,255,255,0.07)",
        }}
      >
        {/* Search input */}
        <div className="flex-1 relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
            style={{ color: "var(--bz-text-3)" }}
          />
          <input
            placeholder="Search articles..."
            aria-label="Search articles"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-xl text-[12px] outline-none transition-all"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.07)",
              color: "var(--bz-text-1)",
            }}
          />
        </div>

        {/* Type filter */}
        <Select
          value={filterType}
          onValueChange={(v) => setFilterType(v as FilterType)}
        >
          <SelectTrigger
            className="w-[130px] h-8 text-[11px] rounded-xl"
            style={{
              background: "rgba(255,255,255,0.04)",
              borderColor: "rgba(255,255,255,0.07)",
              color: "var(--bz-text-2)",
            }}
          >
            <Filter
              className="w-3 h-3 mr-1.5"
              style={{ color: "var(--bz-text-3)" }}
            />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="NEW">New Only</SelectItem>
            <SelectItem value="UPDATED">Updated Only</SelectItem>
            <SelectItem value="critical">Critical Only</SelectItem>
          </SelectContent>
        </Select>

        {/* Sort select */}
        <Select
          value={sortType}
          onValueChange={(v) => setSortType(v as SortType)}
        >
          <SelectTrigger
            className="w-[140px] h-8 text-[11px] rounded-xl"
            style={{
              background: "rgba(255,255,255,0.04)",
              borderColor: "rgba(255,255,255,0.07)",
              color: "var(--bz-text-2)",
            }}
          >
            <ArrowUpDown
              className="w-3 h-3 mr-1.5"
              style={{ color: "var(--bz-text-3)" }}
            />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="date-desc">Newest First</SelectItem>
            <SelectItem value="date-asc">Oldest First</SelectItem>
            <SelectItem value="title-asc">Title A-Z</SelectItem>
            <SelectItem value="title-desc">Title Z-A</SelectItem>
          </SelectContent>
        </Select>

        {/* Sync button */}
        <button
          onClick={loadNews}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all hover:bg-white/[0.04]"
          style={{
            color: "var(--bz-text-2)",
            border: "1px solid rgba(255,255,255,0.07)",
          }}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Sync
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20">
          <Loader2
            className="w-8 h-8 animate-spin mb-3"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
            Loading news items...
          </p>
        </div>
      ) : items.length === 0 || filteredAndSortedItems.length === 0 ? (
        /* Empty state */
        <div
          className="flex flex-col items-center justify-center py-24 rounded-2xl border-2 border-dashed"
          style={{
            borderColor: "rgba(255,255,255,0.07)",
            background: "rgba(255,255,255,0.01)",
          }}
        >
          <div
            className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
            style={{
              background: "rgba(212,132,90,0.08)",
              border: "1px solid rgba(212,132,90,0.15)",
            }}
          >
            <Sparkles
              className="w-8 h-8"
              style={{ color: "var(--bz-accent)" }}
            />
          </div>
          <h3
            className="text-[15px] font-semibold mb-1"
            style={{ color: "var(--bz-text-1)" }}
          >
            All Caught Up!
          </h3>
          <p
            className="text-[12px] text-center max-w-sm mb-6"
            style={{ color: "var(--bz-text-2)" }}
          >
            {items.length === 0
              ? "The intelligence scraper hasn't flagged any new items for review. Check back later or run a manual scrape."
              : "No items match your current filters. Try adjusting your search or filters."}
          </p>
          <button
            onClick={loadNews}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[12px] font-medium transition-all hover:bg-white/[0.04]"
            style={{
              color: "var(--bz-text-2)",
              border: "1px solid rgba(255,255,255,0.07)",
            }}
          >
            <RefreshCw className="w-3.5 h-3.5" /> Check Again
          </button>
        </div>
      ) : (
        /* Article card grid */
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {filteredAndSortedItems.map((item) => (
            <div
              key={item.id}
              className="rounded-2xl border overflow-hidden transition-all duration-200 hover:shadow-lg group relative"
              style={{
                background: "rgba(255,255,255,0.03)",
                backdropFilter: "blur(12px)",
                WebkitBackdropFilter: "blur(12px)",
                borderColor: "rgba(255,255,255,0.07)",
              }}
            >
              {/* Critical ribbon */}
              {item.is_critical && (
                <div className="absolute top-0 right-0 z-10">
                  <div
                    className="flex items-center gap-1 px-2 py-1 text-[9px] font-bold rounded-bl-lg"
                    style={{ background: "rgba(239,68,68,0.9)", color: "#fff" }}
                  >
                    <Flame className="w-3 h-3" /> CRITICAL
                  </div>
                </div>
              )}

              {/* Checkbox overlay (top-left) */}
              <div className="absolute top-2 left-2 z-10">
                <button
                  onClick={() => toggleSelectItem(item.id)}
                  className="w-6 h-6 rounded-md flex items-center justify-center transition-all"
                  style={{
                    background: "rgba(0,0,0,0.5)",
                    backdropFilter: "blur(4px)",
                  }}
                  aria-label={`Select ${item.title}`}
                >
                  {selectedItems.has(item.id) ? (
                    <CheckSquare
                      className="w-4 h-4"
                      style={{ color: "var(--bz-accent)" }}
                    />
                  ) : (
                    <Square
                      className="w-4 h-4 opacity-60"
                      style={{ color: "#fff" }}
                    />
                  )}
                </button>
              </div>

              {/* Cover image */}
              <div className="relative h-32 overflow-hidden">
                {item.cover_image ? (
                  <img
                    src={item.cover_image}
                    alt={item.title}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                ) : (
                  <div
                    className="w-full h-full flex items-center justify-center"
                    style={{
                      background:
                        "linear-gradient(135deg, rgba(212,132,90,0.08) 0%, rgba(99,102,241,0.08) 100%)",
                    }}
                  >
                    <ImageIcon
                      className="w-8 h-8"
                      style={{ color: "var(--bz-text-3)" }}
                    />
                  </div>
                )}
                {/* Hover overlay — desktop */}
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150 hidden sm:flex items-center justify-center gap-2"
                  style={{
                    background: "rgba(0,0,0,0.6)",
                    backdropFilter: "blur(4px)",
                  }}
                >
                  <button
                    onClick={() => handlePreview(item)}
                    className="p-2 rounded-lg transition-all hover:bg-white/[0.1]"
                    style={{ border: "1px solid rgba(255,255,255,0.15)" }}
                  >
                    <Eye className="w-4 h-4 text-white" />
                  </button>
                  <button
                    onClick={() => setEditingItem(item)}
                    className="p-2 rounded-lg transition-all hover:bg-white/[0.1]"
                    style={{ border: "1px solid rgba(255,255,255,0.15)" }}
                  >
                    <Edit className="w-4 h-4 text-white" />
                  </button>
                  <button
                    onClick={() => setCoverUploadItem(item)}
                    className="p-2 rounded-lg transition-all hover:bg-white/[0.1]"
                    style={{ border: "1px solid rgba(255,255,255,0.15)" }}
                  >
                    <ImageIcon className="w-4 h-4 text-white" />
                  </button>
                </div>
                {/* Touch fallback — always visible on mobile */}
                <div className="absolute bottom-2 right-2 flex gap-1 sm:hidden">
                  <button
                    onClick={() => setEditingItem(item)}
                    className="p-1.5 rounded-md"
                    style={{
                      background: "rgba(0,0,0,0.7)",
                      border: "1px solid rgba(255,255,255,0.15)",
                    }}
                  >
                    <Edit className="w-3 h-3 text-white" />
                  </button>
                  <button
                    onClick={() => setCoverUploadItem(item)}
                    className="p-1.5 rounded-md"
                    style={{
                      background: "rgba(0,0,0,0.7)",
                      border: "1px solid rgba(255,255,255,0.15)",
                    }}
                  >
                    <ImageIcon className="w-3 h-3 text-white" />
                  </button>
                </div>
              </div>

              {/* Card body */}
              <div className="p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span
                    className="text-[9.5px] font-semibold px-2 py-0.5 rounded-full"
                    style={{
                      background: "rgba(212,132,90,0.1)",
                      color: "var(--bz-accent)",
                      border: "1px solid rgba(212,132,90,0.15)",
                    }}
                  >
                    {item.source && item.source.startsWith("http")
                      ? (() => {
                          try {
                            return new URL(item.source).hostname.replace(
                              "www.",
                              "",
                            );
                          } catch {
                            return item.source;
                          }
                        })()
                      : item.source || "intel"}
                  </span>
                  <span
                    className="text-[10px] flex items-center gap-1"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    <Calendar className="w-3 h-3" />
                    {new Date(item.detected_at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
                <h3
                  className="text-[12.5px] font-semibold leading-snug line-clamp-2"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  {item.title}
                </h3>
              </div>

              {/* Card footer */}
              <div className="px-3 pb-3 space-y-2">
                {/* Position select */}
                <Select
                  value={getPosition(item.id)}
                  onValueChange={(v) =>
                    setPublishPosition((prev) => ({ ...prev, [item.id]: v }))
                  }
                >
                  <SelectTrigger
                    className="h-7 text-[10.5px] rounded-lg"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      borderColor: "rgba(255,255,255,0.07)",
                      color: "var(--bz-text-2)",
                    }}
                  >
                    <MapPin
                      className="w-3 h-3 mr-1"
                      style={{ color: "var(--bz-text-3)" }}
                    />
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="latest">Latest</SelectItem>
                    <SelectItem value="hero_main">Hero Main</SelectItem>
                    <SelectItem value="hero_2">Hero 2</SelectItem>
                    <SelectItem value="hero_3">Hero 3</SelectItem>
                    <SelectItem value="hero_4">Hero 4</SelectItem>
                    <SelectItem value="hero_5">Hero 5</SelectItem>
                    <SelectItem value="insight_1">Insight 1</SelectItem>
                    <SelectItem value="insight_2">Insight 2</SelectItem>
                    <SelectItem value="insight_3">Insight 3</SelectItem>
                  </SelectContent>
                </Select>
                {/* Publish button */}
                <button
                  onClick={() => handlePublish(item)}
                  disabled={publishingIds.has(item.id)}
                  className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-xl text-[11px] font-semibold transition-all"
                  style={{
                    background: "rgba(212,132,90,0.12)",
                    color: "var(--bz-accent)",
                    border: "1px solid rgba(212,132,90,0.2)",
                  }}
                >
                  {publishingIds.has(item.id) ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />{" "}
                      Publishing...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" /> Publish
                    </>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Bulk actions sticky bar */}
      {selectedItems.size > 0 && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2.5 rounded-2xl shadow-2xl z-50"
          style={{
            background: "rgba(18,18,20,0.9)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          <span
            className="text-[12px] font-semibold"
            style={{ color: "var(--bz-text-1)" }}
          >
            {selectedItems.size} selected
          </span>
          <div
            className="w-px h-4"
            style={{ background: "rgba(255,255,255,0.1)" }}
          />
          <button
            onClick={handleBulkPublish}
            className="text-[11px] font-medium px-3 py-1.5 rounded-lg transition-all"
            style={{
              background: "rgba(212,132,90,0.12)",
              color: "var(--bz-accent)",
              border: "1px solid rgba(212,132,90,0.2)",
            }}
          >
            Publish all
          </button>
          <button
            onClick={() => setSelectedItems(new Set())}
            className="text-[11px] px-3 py-1.5 rounded-lg transition-all hover:bg-white/[0.04]"
            style={{ color: "var(--bz-text-2)" }}
          >
            Deselect
          </button>
        </div>
      )}

      {/* Preview Dialog */}
      <Dialog
        open={!!previewItem}
        onOpenChange={(open) => !open && setPreviewItem(null)}
      >
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-2xl">{previewItem?.title}</DialogTitle>
            <DialogDescription>
              {previewItem && (
                <div
                  className="flex items-center gap-4 text-sm mt-2"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  <span>
                    {new Date(previewItem.detected_at).toLocaleDateString(
                      "en-US",
                      {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      },
                    )}
                  </span>
                  <span>•</span>
                  <span>
                    {(previewItem as any).source_name || previewItem.source}
                  </span>
                  <span>•</span>
                  <span style={{ color: "var(--bz-accent)" }}>
                    {previewItem.detection_type}
                  </span>
                </div>
              )}
            </DialogDescription>
          </DialogHeader>
          {previewItem?.cover_image && (
            <div className="w-full h-64 rounded-lg overflow-hidden mb-4">
              <img
                src={previewItem.cover_image}
                alt={previewItem.title}
                className="w-full h-full object-cover"
              />
            </div>
          )}
          {previewItem?.content && (
            <div
              className="prose prose-sm max-w-none mt-4"
              style={{ color: "var(--bz-text-1)" }}
            >
              <div
                className="whitespace-pre-wrap"
                dangerouslySetInnerHTML={renderMiniMarkdown(
                  previewItem.content,
                )}
              />
            </div>
          )}
          <div className="flex gap-2 mt-6">
            <Select
              value={previewItem ? getPosition(previewItem.id) : "latest"}
              onValueChange={(value) =>
                previewItem &&
                setPublishPosition((prev) => ({
                  ...prev,
                  [previewItem.id]: value,
                }))
              }
            >
              <SelectTrigger
                className="w-[160px] rounded-xl"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  borderColor: "rgba(255,255,255,0.07)",
                  color: "var(--bz-text-2)",
                }}
              >
                <MapPin
                  className="w-3 h-3 mr-1 shrink-0"
                  style={{ color: "var(--bz-text-3)" }}
                />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="latest">Latest</SelectItem>
                <SelectItem value="hero_main">Hero Main</SelectItem>
                <SelectItem value="hero_2">Hero 2</SelectItem>
                <SelectItem value="hero_3">Hero 3</SelectItem>
                <SelectItem value="hero_4">Hero 4</SelectItem>
                <SelectItem value="hero_5">Hero 5</SelectItem>
                <SelectItem value="insight_1">Insight 1</SelectItem>
                <SelectItem value="insight_2">Insight 2</SelectItem>
                <SelectItem value="insight_3">Insight 3</SelectItem>
              </SelectContent>
            </Select>
            <button
              className="flex-1 flex items-center justify-center gap-2 py-2 rounded-xl text-[12px] font-semibold transition-all"
              style={{
                background: "rgba(212,132,90,0.12)",
                color: "var(--bz-accent)",
                border: "1px solid rgba(212,132,90,0.2)",
              }}
              onClick={() => previewItem && handlePublish(previewItem)}
              disabled={previewItem ? publishingIds.has(previewItem.id) : false}
            >
              {previewItem && publishingIds.has(previewItem.id) ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Publishing...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Publish Article
                </>
              )}
            </button>
            {previewItem?.source && previewItem.source.startsWith("http") && (
              <a
                href={previewItem.source}
                target="_blank"
                rel="noreferrer"
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-[12px] font-medium transition-all hover:bg-white/[0.04]"
                style={{
                  color: "var(--bz-text-2)",
                  border: "1px solid rgba(255,255,255,0.07)",
                }}
              >
                <ExternalLink className="h-4 w-4" />
                View Source
              </a>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Dialog */}
      {editingItem && (
        <ArticleEditor
          item={editingItem}
          open={!!editingItem}
          onOpenChange={(open) => !open && setEditingItem(null)}
          onSaved={() => {
            loadNews();
            setEditingItem(null);
          }}
        />
      )}

      {/* Cover Image Upload Dialog */}
      {coverUploadItem && (
        <CoverImageUploader
          item={coverUploadItem}
          open={!!coverUploadItem}
          onOpenChange={(open) => !open && setCoverUploadItem(null)}
          onUploaded={() => {
            loadNews();
            setCoverUploadItem(null);
          }}
        />
      )}
    </div>
  );
}
