"use client";

import { useEffect, useState } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { Loader2, Check, X, FileText, ExternalLink, ShieldAlert, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

export default function VisaOraclePage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);
  const toast = useToast();

  useEffect(() => {
    loadItems();
  }, []);

  const loadItems = async () => {
    setLoading(true);
    try {
      const res = await intelligenceApi.getPendingItems("visa");
      setItems(res.items);
    } catch (error) {
      toast.error("Failed to load items", "Could not fetch pending visa updates.");
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id: string) => {
    setProcessing(id);
    try {
      await intelligenceApi.approveItem("visa", id);
      toast.success("Visa approved", "Item ingested into Knowledge Base successfully.");
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (error) {
      toast.error("Approval failed", "Could not ingest item.");
    } finally {
      setProcessing(null);
    }
  };

  const handleReject = async (id: string) => {
    if (!confirm("Are you sure you want to reject this update?")) return;
    setProcessing(id);
    try {
      await intelligenceApi.rejectItem("visa", id);
      toast.success("Update rejected", "Item archived as rejected.");
      setItems((prev) => prev.filter((i) => i.id !== id));
    } catch (error) {
      toast.error("Rejection failed");
    } finally {
      setProcessing(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground animate-pulse">Scanning Intelligence Feed...</p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 bg-muted/10 rounded-xl border border-dashed border-muted-foreground/20">
        <div className="bg-primary/10 p-4 rounded-full mb-4">
          <Sparkles className="h-8 w-8 text-primary" />
        </div>
        <h3 className="text-xl font-semibold mb-2">All caught up!</h3>
        <p className="text-muted-foreground text-center max-w-sm">
          No pending visa updates. The Intelligent Agent is scanning for new regulations.
        </p>
        <Button variant="outline" className="mt-6" onClick={loadItems}>
          Check again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Visa Oracle</h2>
          <p className="text-muted-foreground mt-1">Review and approve detected visa regulations.</p>
        </div>
        <Button variant="outline" onClick={loadItems} size="sm" className="gap-2">
          <Sparkles className="h-4 w-4" /> Refresh Feed
        </Button>
      </div>

      <div className="grid gap-4">
        {items.map((item) => (
          <Card key={item.id} className="group overflow-hidden border-l-4 border-l-primary shadow-sm hover:shadow-md transition-all">
            <CardHeader className="bg-muted/30 pb-4">
              <div className="flex justify-between items-start gap-4">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-3">
                    <span className={cn(
                      "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold shadow-sm",
                      item.detection_type === "NEW" 
                        ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 border border-blue-200 dark:border-blue-800" 
                        : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                    )}>
                      {item.detection_type === "NEW" ? "✨ NEW REGULATION" : "📝 UPDATED POLICY"}
                    </span>
                    <CardTitle className="text-lg group-hover:text-primary transition-colors">{item.title}</CardTitle>
                  </div>
                  <p className="text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-0.5 rounded w-fit">
                    ID: {item.id}
                  </p>
                </div>
                <div className="text-right flex flex-col items-end gap-1">
                  <span className="text-xs font-medium text-muted-foreground">
                    Detected {new Date(item.detected_at).toLocaleDateString()}
                  </span>
                  <a
                    href={item.source}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary hover:underline inline-flex items-center gap-1 font-medium px-2 py-1 hover:bg-primary/5 rounded"
                  >
                    Official Source <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-4 flex justify-between items-center bg-white dark:bg-slate-950">
              <div className="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-3">
                <div className="bg-slate-100 dark:bg-slate-800 p-2 rounded-md">
                  <FileText className="h-5 w-5 text-slate-500" />
                </div>
                <div className="flex flex-col">
                  <span className="font-medium text-slate-900 dark:text-slate-200">Processing Required</span>
                  <span className="text-xs">Will be ingested into <strong>visa_oracle</strong> collection</span>
                </div>
              </div>
              <div className="flex gap-3">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-foreground"
                  onClick={() => window.open(`/api/intel/staging/preview/visa/${item.id}`, '_blank')}
                >
                  View JSON Content
                </Button>
                <div className="h-8 w-px bg-border mx-1" />
                <Button
                  variant="outline"
                  size="sm"
                  className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/20 border-red-200 dark:border-red-900/50"
                  onClick={() => handleReject(item.id)}
                  disabled={!!processing}
                >
                  <X className="h-4 w-4 mr-1.5" /> Reject
                </Button>
                <Button
                  size="sm"
                  className="bg-green-600 hover:bg-green-700 text-white shadow-sm hover:shadow"
                  onClick={() => handleApprove(item.id)}
                  disabled={!!processing}
                >
                  {processing === item.id ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-1.5" />
                  ) : (
                    <Check className="h-4 w-4 mr-1.5" />
                  )}
                  {processing === item.id ? "Ingesting..." : "Approve & Ingest"}
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
