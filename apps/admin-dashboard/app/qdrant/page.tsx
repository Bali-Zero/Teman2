"use client";
import { useEffect, useState } from "react";
import { error as logError } from "@/lib/logger";
import Link from "next/link";
import {
  Card,
  CardContent,
  CardTitle,
  Badge,
} from "@/components/ui/primitives";
import { FolderTree, Layers } from "lucide-react";

export default function QdrantPage() {
  const [collections, setCollections] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<any>(null);

  useEffect(() => {
    fetch("/api/qdrant/collections")
      .then((res) => res.json())
      .then((data) => {
        if (data.error)
          throw new Error(data.error + (data.url ? ` (${data.url})` : ""));
        if (data.collections) setCollections(data.collections);
        setLoading(false);
      })
      .catch((err) => {
        logError(err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Qdrant Collections
          </h1>
          <p className="text-muted-foreground">
            Vector database collections overview.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-muted-foreground">
          Loading collections...
        </div>
      ) : error ? (
        <div className="p-8 border-2 border-dashed border-destructive/50 rounded-lg bg-destructive/5 text-center">
          <h3 className="text-lg font-bold text-destructive mb-2">
            Connection Failed
          </h3>
          <p className="text-muted-foreground mb-4">{error}</p>
          <p className="text-xs text-muted-foreground">
            Check your VPN or Proxy tunnel to Qdrant.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {collections.map((col) => (
            <Link key={col.name} href={`/qdrant/${col.name}`}>
              <Card className="hover:bg-muted/5 transition-colors cursor-pointer border-l-4 border-l-purple-500/20 hover:border-l-purple-500 h-full">
                <CardContent className="p-6 flex flex-col gap-4">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-lg">{col.name}</span>
                    <Layers className="h-5 w-5 text-purple-500" />
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <div className="bg-secondary px-2 py-1 rounded-md text-secondary-foreground font-mono text-xs">
                      {col.vectors_count !== undefined
                        ? col.vectors_count.toLocaleString()
                        : "Unknown"}{" "}
                      vectors
                    </div>
                    {col.status && (
                      <div
                        className={`px-2 py-1 rounded-md text-xs uppercase font-bold text-white ${col.status === "green" ? "bg-green-500" : "bg-yellow-500"}`}
                      >
                        {col.status}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
