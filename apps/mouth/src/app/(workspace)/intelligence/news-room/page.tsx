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
        /* Article card grid — vivid liquid glassmorphism */
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {filteredAndSortedItems.map((item, idx) => {
            const PALETTES = [
              {
                bg: "rgba(212,132,90,0.12)",
                border: "rgba(212,132,90,0.25)",
                glow: "rgba(212,132,90,0.15)",
                accent: "#d4845a",
                gradient:
                  "linear-gradient(145deg, rgba(212,132,90,0.18) 0%, rgba(180,100,60,0.06) 100%)",
              },
              {
                bg: "rgba(99,102,241,0.12)",
                border: "rgba(99,102,241,0.25)",
                glow: "rgba(99,102,241,0.15)",
                accent: "#818cf8",
                gradient:
                  "linear-gradient(145deg, rgba(99,102,241,0.18) 0%, rgba(67,56,202,0.06) 100%)",
              },
              {
                bg: "rgba(16,185,129,0.12)",
                border: "rgba(16,185,129,0.25)",
                glow: "rgba(16,185,129,0.15)",
                accent: "#34d399",
                gradient:
                  "linear-gradient(145deg, rgba(16,185,129,0.18) 0%, rgba(5,150,105,0.06) 100%)",
              },
              {
                bg: "rgba(244,63,94,0.12)",
                border: "rgba(244,63,94,0.25)",
                glow: "rgba(244,63,94,0.15)",
                accent: "#fb7185",
                gradient:
                  "linear-gradient(145deg, rgba(244,63,94,0.18) 0%, rgba(190,18,60,0.06) 100%)",
              },
              {
                bg: "rgba(245,158,11,0.12)",
                border: "rgba(245,158,11,0.25)",
                glow: "rgba(245,158,11,0.15)",
                accent: "#fbbf24",
                gradient:
                  "linear-gradient(145deg, rgba(245,158,11,0.18) 0%, rgba(180,83,9,0.06) 100%)",
              },
              {
                bg: "rgba(14,165,233,0.12)",
                border: "rgba(14,165,233,0.25)",
                glow: "rgba(14,165,233,0.15)",
                accent: "#38bdf8",
                gradient:
                  "linear-gradient(145deg, rgba(14,165,233,0.18) 0%, rgba(2,132,199,0.06) 100%)",
              },
              {
                bg: "rgba(168,85,247,0.12)",
                border: "rgba(168,85,247,0.25)",
                glow: "rgba(168,85,247,0.15)",
                accent: "#c084fc",
                gradient:
                  "linear-gradient(145deg, rgba(168,85,247,0.18) 0%, rgba(126,34,206,0.06) 100%)",
              },
              {
                bg: "rgba(236,72,153,0.12)",
                border: "rgba(236,72,153,0.25)",
                glow: "rgba(236,72,153,0.15)",
                accent: "#f472b6",
                gradient:
                  "linear-gradient(145deg, rgba(236,72,153,0.18) 0%, rgba(190,24,93,0.06) 100%)",
              },
            ];
            const pal = PALETTES[idx % PALETTES.length];

            return (
              <div
                key={item.id}
                className="group relative rounded-[18px] overflow-hidden transition-all duration-500 hover:-translate-y-1.5 flex flex-col"
                style={{
                  background: pal.gradient,
                  backdropFilter: "blur(24px) saturate(1.5)",
                  WebkitBackdropFilter: "blur(24px) saturate(1.5)",
                  border: `1px solid ${pal.border}`,
                  boxShadow: `inset 0 1px 0 rgba(255,255,255,0.08), 0 4px 24px -4px rgba(0,0,0,0.25), 0 0 0 0 ${pal.glow}`,
                }}
              >
                {/* Hover glow */}
                <div
                  className="absolute inset-0 rounded-[18px] opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                  style={{
                    boxShadow: `0 8px 40px -8px ${pal.glow}, inset 0 0 30px -15px ${pal.glow}`,
                  }}
                />

                {/* Top accent bar */}
                <div
                  className="h-1 w-full"
                  style={{
                    background: `linear-gradient(90deg, ${pal.accent}, transparent)`,
                  }}
                />

                {/* Light refraction */}
                <div
                  className="absolute top-1 left-0 right-0 h-px opacity-30 group-hover:opacity-60 transition-opacity duration-500 pointer-events-none"
                  style={{
                    background: `linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.5) 20%, rgba(255,255,255,0.1) 60%, transparent 100%)`,
                  }}
                />

                {/* Critical ribbon */}
                {item.is_critical && (
                  <div className="absolute top-1 right-0 z-10">
                    <div
                      className="flex items-center gap-1 px-2 py-0.5 text-[7px] font-bold tracking-wider rounded-bl-xl rounded-tr-[18px]"
                      style={{
                        background: "linear-gradient(135deg, #ef4444, #dc2626)",
                        color: "#fff",
                        boxShadow: "0 2px 12px rgba(239,68,68,0.4)",
                      }}
                    >
                      <Flame className="w-2 h-2" /> CRITICAL
                    </div>
                  </div>
                )}

                {/* Checkbox */}
                <div className="absolute top-2.5 left-2.5 z-10">
                  <button
                    onClick={() => toggleSelectItem(item.id)}
                    className="w-5 h-5 rounded-md flex items-center justify-center transition-all duration-200 hover:scale-110"
                    style={{
                      background: selectedItems.has(item.id)
                        ? pal.bg
                        : "rgba(0,0,0,0.3)",
                      backdropFilter: "blur(12px)",
                      border: selectedItems.has(item.id)
                        ? `1.5px solid ${pal.accent}`
                        : "1px solid rgba(255,255,255,0.12)",
                      boxShadow: selectedItems.has(item.id)
                        ? `0 0 10px ${pal.glow}`
                        : "none",
                    }}
                    aria-label={`Select ${item.title}`}
                  >
                    {selectedItems.has(item.id) ? (
                      <Check
                        className="w-3 h-3"
                        style={{ color: pal.accent }}
                      />
                    ) : (
                      <Square
                        className="w-3 h-3 opacity-40"
                        style={{ color: "#fff" }}
                      />
                    )}
                  </button>
                </div>

                {/* Card body — no image, just content */}
                <div className="px-3 pt-7 pb-1 flex-1 flex flex-col gap-2">
                  {/* Source + date */}
                  <div className="flex items-center justify-between">
                    <span
                      className="text-[8px] font-bold uppercase tracking-widest px-1.5 py-[2px] rounded-md"
                      style={{
                        background: pal.bg,
                        color: pal.accent,
                        border: `1px solid ${pal.border}`,
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
                      className="text-[9px] flex items-center gap-0.5"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      <Calendar className="w-2.5 h-2.5" />
                      {new Date(item.detected_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })}
                    </span>
                  </div>

                  {/* Title — big and visible */}
                  <h3
                    className="text-[13px] font-bold leading-snug line-clamp-3"
                    style={{ color: "#fff" }}
                  >
                    {item.title}
                  </h3>

                  {/* Type badge */}
                  <div className="flex items-center gap-1 mt-auto">
                    <span
                      className="text-[7px] font-bold uppercase tracking-widest px-1 py-[1px] rounded"
                      style={{
                        background: "rgba(255,255,255,0.06)",
                        color: "var(--bz-text-3)",
                        border: "1px solid rgba(255,255,255,0.06)",
                      }}
                    >
                      {item.type}
                    </span>
                  </div>
                </div>

                {/* Hover action row */}
                <div className="px-3 py-1.5 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                  <button
                    onClick={() => handlePreview(item)}
                    className="p-1.5 rounded-lg transition-all hover:scale-110"
                    style={{
                      background: "rgba(255,255,255,0.08)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    <Eye className="w-3 h-3 text-white/70" />
                  </button>
                  <button
                    onClick={() => setEditingItem(item)}
                    className="p-1.5 rounded-lg transition-all hover:scale-110"
                    style={{
                      background: "rgba(255,255,255,0.08)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    <Edit className="w-3 h-3 text-white/70" />
                  </button>
                  <button
                    onClick={() => setCoverUploadItem(item)}
                    className="p-1.5 rounded-lg transition-all hover:scale-110"
                    style={{
                      background: "rgba(255,255,255,0.08)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  >
                    <ImageIcon className="w-3 h-3 text-white/70" />
                  </button>
                </div>

                {/* Footer — position select + publish */}
                <div className="px-3 pb-3 space-y-1.5">
                  <Select
                    value={getPosition(item.id)}
                    onValueChange={(v) =>
                      setPublishPosition((prev) => ({ ...prev, [item.id]: v }))
                    }
                  >
                    <SelectTrigger
                      className="h-7 text-[10px] rounded-lg font-medium"
                      style={{
                        background: "rgba(20,20,24,0.9)",
                        borderColor: "rgba(255,255,255,0.1)",
                        color: "var(--bz-text-1)",
                      }}
                    >
                      <MapPin
                        className="w-3 h-3 mr-1"
                        style={{ color: pal.accent }}
                      />
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent
                      className="rounded-xl"
                      style={{
                        background: "rgba(20,20,24,0.98)",
                        border: "1px solid rgba(255,255,255,0.12)",
                        backdropFilter: "blur(20px)",
                      }}
                    >
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
                    onClick={() => handlePublish(item)}
                    disabled={publishingIds.has(item.id)}
                    className="w-full flex items-center justify-center gap-1 py-2 rounded-xl text-[10px] font-bold tracking-wide transition-all duration-300 disabled:opacity-50"
                    style={{
                      background: `linear-gradient(135deg, ${pal.accent}30, ${pal.accent}15)`,
                      color: pal.accent,
                      border: `1px solid ${pal.border}`,
                      boxShadow: `0 2px 12px -2px ${pal.glow}`,
                    }}
                  >
                    {publishingIds.has(item.id) ? (
                      <>
                        <Loader2 className="w-3 h-3 animate-spin" />{" "}
                        Publishing...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-3 h-3" /> Publish
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Bulk actions — floating glass bar */}
      {selectedItems.size > 0 && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-5 py-3 rounded-2xl z-50 animate-in slide-in-from-bottom-4 duration-300"
          style={{
            background:
              "linear-gradient(135deg, rgba(18,18,22,0.85) 0%, rgba(30,30,36,0.8) 100%)",
            backdropFilter: "blur(32px) saturate(1.5)",
            WebkitBackdropFilter: "blur(32px) saturate(1.5)",
            border: "1px solid rgba(255,255,255,0.1)",
            boxShadow:
              "0 20px 60px -10px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.06)",
          }}
        >
          <span
            className="text-[12px] font-bold tabular-nums"
            style={{
              background: "linear-gradient(135deg, #f0ede8 0%, #d4845a 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            {selectedItems.size} selected
          </span>
          <div
            className="w-px h-4"
            style={{ background: "rgba(255,255,255,0.08)" }}
          />
          <button
            onClick={handleBulkPublish}
            className="text-[11px] font-bold px-4 py-1.5 rounded-xl transition-all duration-300 hover:shadow-[0_4px_20px_-4px_rgba(212,132,90,0.4)]"
            style={{
              background:
                "linear-gradient(135deg, rgba(212,132,90,0.2) 0%, rgba(212,132,90,0.1) 100%)",
              color: "var(--bz-accent)",
              border: "1px solid rgba(212,132,90,0.25)",
            }}
          >
            Publish all
          </button>
          <button
            onClick={() => setSelectedItems(new Set())}
            className="text-[11px] px-3 py-1.5 rounded-xl transition-all hover:bg-white/[0.06]"
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
