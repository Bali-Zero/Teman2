"use client";

import { useEffect, useState } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Loader2, ExternalLink, Calendar, RefreshCw, Sparkles, Flame } from "lucide-react";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";

export default function NewsRoomPage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishingIds, setPublishingIds] = useState<Set<string>>(new Set());
  const toast = useToast();

  useEffect(() => {
    logger.componentMount('NewsRoomPage');
    loadNews();

    return () => {
      logger.componentUnmount('NewsRoomPage');
    };
  }, []);

  const loadNews = async () => {
    logger.info('Loading news items', { component: 'NewsRoomPage', action: 'load_news' });
    setLoading(true);
    try {
      const res = await intelligenceApi.getPendingItems("news");
      setItems(res.items);
      logger.info(`Loaded ${res.count} news items`, {
        component: 'NewsRoomPage',
        action: 'load_news_success',
        metadata: {
          count: res.count,
          criticalCount: res.items.filter(i => i.is_critical).length,
        },
      });
    } catch (error) {
      logger.error('Failed to load news items', {
        component: 'NewsRoomPage',
        action: 'load_news_error',
      }, error as Error);
      toast.error("Error", "Failed to load news drafts");
    } finally {
      setLoading(false);
    }
  };

  const handlePublish = async (item: StagingItem) => {
    logger.info('Publishing item', {
      component: 'NewsRoomPage',
      action: 'publish_item',
      itemId: item.id,
      metadata: { title: item.title },
    });

    // Add to publishing set
    setPublishingIds(prev => new Set(prev).add(item.id));

    try {
      const response = await intelligenceApi.publishItem(item.type, item.id);

      logger.info('Item published successfully', {
        component: 'NewsRoomPage',
        action: 'publish_success',
        itemId: item.id,
        metadata: { published_url: response.published_url },
      });

      toast.success(
        "Published!",
        `"${response.title}" has been published to the knowledge base`
      );

      // Reload news list to remove published item
      loadNews();
    } catch (error) {
      logger.error('Failed to publish item', {
        component: 'NewsRoomPage',
        action: 'publish_error',
        itemId: item.id,
      }, error as Error);

      toast.error("Error", "Failed to publish article");
    } finally {
      // Remove from publishing set
      setPublishingIds(prev => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-[var(--accent)]" />
        <p className="text-[var(--foreground-muted)] animate-pulse text-lg">
          Gathering Global Intelligence...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex justify-between items-end border-b border-[var(--border)] pb-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight text-[var(--foreground)]">
            News Room
          </h2>
          <p className="text-[var(--foreground-muted)] text-lg">
            Curate and publish intelligence reports
          </p>
        </div>
        <Button onClick={loadNews} variant="secondary" size="sm" className="gap-2">
          <RefreshCw className="h-4 w-4" /> Sync Sources
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 bg-[var(--background-secondary)] rounded-2xl border-2 border-dashed border-[var(--border)]">
          <div className="bg-[var(--accent)]/10 p-6 rounded-full mb-6">
            <Sparkles className="h-12 w-12 text-[var(--accent)]" />
          </div>
          <h3 className="text-xl font-semibold mb-2 text-[var(--foreground)]">
            No Drafts Pending
          </h3>
          <p className="text-[var(--foreground-muted)] max-w-md text-center">
            The intelligence scraper hasn't flagged any new items for review. Check
            back later or run a manual scrape.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <Card
              key={item.id}
              className="group flex flex-col h-full overflow-hidden hover:shadow-lg transition-all duration-300 border-t-4 border-t-transparent hover:border-t-[var(--accent)]"
            >
              {/* Header Image Placeholder */}
              <div className="h-40 bg-gradient-to-br from-slate-100 to-slate-200 relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-slate-200 to-slate-300 opacity-50" />
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-5xl">📰</span>
                </div>
                {item.is_critical && (
                  <div className="absolute top-3 right-3">
                    <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-100 text-red-700 border border-red-200 shadow-sm">
                      <Flame className="w-3 h-3" />
                      CRITICAL
                    </span>
                  </div>
                )}
                <div className="absolute top-3 left-3">
                  <span
                    className={cn(
                      "px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide",
                      "bg-white/90 text-slate-900 shadow-sm backdrop-blur-sm"
                    )}
                  >
                    {item.source || "Unknown Source"}
                  </span>
                </div>
              </div>

              <CardContent className="flex-1 p-5 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs text-[var(--foreground-muted)]">
                    <Calendar className="h-3 w-3" />
                    <span>
                      {new Date(item.detected_at).toLocaleDateString()}
                    </span>
                    <span>•</span>
                    <span className="text-[var(--accent)] font-medium">
                      {item.detection_type}
                    </span>
                  </div>
                  <h3 className="font-bold text-lg leading-snug group-hover:text-[var(--accent)] transition-colors line-clamp-3 text-[var(--foreground)]">
                    {item.title}
                  </h3>
                </div>
                <p className="text-sm text-[var(--foreground-muted)] line-clamp-3">
                  Pending editorial review. Agent-detected immigration news awaiting
                  approval.
                </p>
              </CardContent>

              <CardFooter className="p-5 pt-0 mt-auto">
                <div className="flex gap-2 w-full">
                  <Button
                    className="flex-1 gap-2 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
                    size="sm"
                    onClick={() => handlePublish(item)}
                    disabled={publishingIds.has(item.id)}
                  >
                    {publishingIds.has(item.id) ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Publishing...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" />
                        Publish
                      </>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    asChild
                    title="View Source"
                  >
                    <a href={item.source} target="_blank" rel="noreferrer">
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </Button>
                </div>
              </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
