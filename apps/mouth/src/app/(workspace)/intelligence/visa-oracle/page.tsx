"use client";

import { useEffect, useState } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
} from "lucide-react";
import { cn } from "@/lib/utils";

export default function VisaOraclePage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string>("");
  const toast = useToast();

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
      toast.error("Rejection failed");
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

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-32 bg-[var(--background-secondary)] rounded-2xl border-2 border-dashed border-[var(--border)]">
        <div className="bg-[var(--accent)]/10 p-6 rounded-full mb-6">
          <Sparkles className="h-12 w-12 text-[var(--accent)]" />
        </div>
        <h3 className="text-2xl font-bold text-[var(--foreground)] mb-2">
          All Caught Up!
        </h3>
        <p className="text-[var(--foreground-muted)] text-center max-w-md mb-8">
          No pending visa updates detected. The Intelligent Visa Agent is continuously
          monitoring imigrasi.go.id for new regulations.
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
              {items.length} {items.length === 1 ? "item" : "items"} pending review
            </span>
          </div>
          <div className="h-4 w-px bg-[var(--border)]" />
          <div className="text-sm text-[var(--foreground-muted)]">
            {items.filter((i) => i.detection_type === "NEW").length} new ·{" "}
            {items.filter((i) => i.detection_type === "UPDATED").length} updated
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={loadItems} className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
      </div>

      {/* Items Grid */}
      <div className="grid gap-4">
        {items.map((item) => (
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
