"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button, Badge } from "@/components/ui/primitives";
import { ArrowLeft, RefreshCw, Braces } from "lucide-react";

export default function CollectionDataPage({
  params,
}: {
  params: { collection: string };
}) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState<string | null>(null);
  const [nextOffset, setNextOffset] = useState<string | null>(null);

  const fetchData = (currentOffset: string | null = null) => {
    setLoading(true);
    const url =
      `/api/qdrant/points?collection=${params.collection}` +
      (currentOffset ? `&offset=${currentOffset}` : "");

    fetch(url)
      .then((res) => res.json())
      .then((res) => {
        if (res.points) {
          setData(res.points);
          setNextOffset(res.next_page_offset);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchData();
  }, []);

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <div className="border-b p-4 flex items-center justify-between bg-background z-10">
        <div className="flex items-center gap-4">
          <Link href="/qdrant">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              {params.collection}
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => fetchData(offset)}>
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!nextOffset}
            onClick={() => {
              setOffset(nextOffset);
              fetchData(nextOffset);
            }}
          >
            Load More
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4 bg-muted/10">
        {loading ? (
          <div className="text-center py-20 text-muted-foreground">
            Loading vectors...
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.map((point) => (
              <div
                key={point.id}
                className="border rounded-md bg-card p-4 space-y-3 font-mono text-sm shadow-sm overflow-hidden"
              >
                <div className="flex justify-between items-start border-b pb-2">
                  <span className="text-xs text-muted-foreground font-sans uppercase tracking-wider">
                    ID
                  </span>
                  <span
                    className="bg-primary/10 text-primary px-2 py-0.5 rounded text-xs truncate max-w-[200px]"
                    title={point.id}
                  >
                    {point.id}
                  </span>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                    <Braces className="h-3 w-3" /> Payload
                  </div>
                  <pre className="bg-muted p-2 rounded text-xs overflow-auto max-h-[200px] text-muted-foreground">
                    {JSON.stringify(point.payload, null, 2)}
                  </pre>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
