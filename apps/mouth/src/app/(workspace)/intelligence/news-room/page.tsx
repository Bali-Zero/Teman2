"use client";

import { useEffect, useState } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Loader2, ExternalLink, Calendar, Globe, ArrowRight, RefreshCw } from "lucide-react";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";

export default function NewsRoomPage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  useEffect(() => {
    loadNews();
  }, []);

  const loadNews = async () => {
    setLoading(true);
    try {
      const res = await intelligenceApi.getPendingItems("news");
      setItems(res.items);
    } catch (error) {
      toast.error("Error", "Failed to load news drafts");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-96 space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground animate-pulse">Gathering Global Intelligence...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex justify-between items-end border-b pb-6">
        <div className="space-y-1">
          <h2 className="text-3xl font-bold tracking-tight">News Room</h2>
          <p className="text-muted-foreground text-lg">Curate and publish intelligence reports.</p>
        </div>
        <Button onClick={loadNews} variant="secondary" size="sm" className="gap-2">
          <RefreshCw className="h-4 w-4" /> Sync Sources
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-32 bg-slate-50 dark:bg-slate-900/50 rounded-2xl border-2 border-dashed">
          <div className="bg-slate-100 dark:bg-slate-800 p-6 rounded-full mb-6">
            <Globe className="h-12 w-12 text-slate-400" />
          </div>
          <h3 className="text-xl font-semibold mb-2">No Drafts Pending</h3>
          <p className="text-muted-foreground max-w-md text-center">
            The intelligence scraper hasn't flagged any new items for review. 
            Check back later or run a manual scrape.
          </p>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <Card key={item.id} className="group flex flex-col h-full overflow-hidden hover:shadow-lg transition-all duration-300 border-t-4 border-t-transparent hover:border-t-primary">
              <div className="h-40 bg-slate-100 dark:bg-slate-800 relative overflow-hidden">
                {/* Placeholder pattern since we don't have real images yet */}
                <div className="absolute inset-0 bg-gradient-to-br from-slate-200 to-slate-300 dark:from-slate-800 dark:to-slate-900 opacity-50" />
                <div className="absolute inset-0 flex items-center justify-center">
                   <span className="text-4xl">📰</span>
                </div>
                <div className="absolute top-3 left-3">
                   <span className={cn(
                      "px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide",
                      "bg-white/90 text-slate-900 shadow-sm backdrop-blur-sm"
                    )}>
                      {item.source || "Unknown Source"}
                    </span>
                </div>
              </div>
              
              <CardContent className="flex-1 p-5 space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Calendar className="h-3 w-3" />
                    <span>{new Date(item.detected_at).toLocaleDateString()}</span>
                    <span>•</span>
                    <span className="text-primary font-medium">{item.detection_type}</span>
                  </div>
                  <h3 className="font-bold text-lg leading-snug group-hover:text-primary transition-colors line-clamp-3">
                    {item.title}
                  </h3>
                </div>
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {/* Summary would go here if available in list view */}
                  Pending editorial review. Click to open the full editor and generated content.
                </p>
              </CardContent>
              
              <CardFooter className="p-5 pt-0 mt-auto">
                <div className="flex gap-2 w-full">
                  <Button className="flex-1 gap-2 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                    Open Editor <ArrowRight className="h-4 w-4" />
                  </Button>
                  <Button size="icon" variant="secondary" asChild title="View Source">
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
