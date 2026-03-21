"use client";
import { useState, useEffect, useCallback } from "react";
import { Badge, Button, Card, CardContent } from "@/components/ui/primitives";
import {
  FileText,
  Search,
  ChevronRight,
  Scale,
  Hash,
  Layers,
  RefreshCw,
  Filter,
  BookOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface LegalChunk {
  id: string;
  text: string;
  regulation_type: string;
  document_number: string;
  year: number;
  pasal?: string;
  ayat?: string;
  huruf?: string;
  doc_title?: string;
  hierarchy_path?: string;
  chunk_type?: string;
  section_title?: string;
  metadata?: Record<string, any>;
}

interface Stats {
  total_chunks: number;
  by_regulation_type: Record<string, number>;
  by_year: Record<string, number>;
}

export default function LegalDocumentsPage() {
  const [chunks, setChunks] = useState<LegalChunk[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedChunk, setSelectedChunk] = useState<LegalChunk | null>(null);
  const [search, setSearch] = useState("");
  const [filterType, setFilterType] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  const LIMIT = 50;

  const fetchStats = async () => {
    try {
      const res = await fetch("/api/legal/stats");
      const data = await res.json();
      if (data.stats) setStats(data.stats);
    } catch (e) {
      // Stats fetch failed - silent
    }
  };

  const fetchChunks = useCallback(
    async (reset = false) => {
      setLoading(true);
      const currentOffset = reset ? 0 : offset;
      try {
        const params = new URLSearchParams({
          limit: String(LIMIT),
          offset: String(currentOffset),
        });
        if (search) params.set("search", search);
        if (filterType) params.set("regulation_type", filterType);

        const res = await fetch(`/api/legal/chunks?${params}`);
        const data = await res.json();

        if (data.chunks) {
          if (reset) {
            setChunks(data.chunks);
            setOffset(LIMIT);
          } else {
            setChunks((prev) => [...prev, ...data.chunks]);
            setOffset((prev) => prev + LIMIT);
          }
          setHasMore(data.chunks.length === LIMIT);
        }
      } catch (e) {
        // Chunks fetch failed - silent
      } finally {
        setLoading(false);
      }
    },
    [offset, search, filterType],
  );

  useEffect(() => {
    fetchStats();
    fetchChunks(true);
  }, []);

  const handleSearch = () => {
    setOffset(0);
    fetchChunks(true);
  };

  const handleFilterChange = (type: string) => {
    setFilterType(type);
    setOffset(0);
    setTimeout(() => fetchChunks(true), 0);
  };

  const getRegTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      PP: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
      PERPRES:
        "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
      PERMEN:
        "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
      UU: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
      PERDA:
        "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
    };
    return (
      colors[type] ||
      "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200"
    );
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* LEFT SIDEBAR: Filters & Stats */}
      <div className="w-72 border-r bg-muted/10 flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center gap-2 mb-4">
            <Scale className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold tracking-tight">
              Legal Documents
            </h1>
          </div>
          <p className="text-xs text-muted-foreground">
            Collection: <code className="font-mono">legal_unified_hybrid</code>
          </p>
        </div>

        {/* Search */}
        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              className="w-full bg-background border rounded-md pl-9 pr-4 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
              placeholder="Search text..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="p-4 border-b space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Layers className="h-4 w-4" />
              <span>Total Chunks:</span>
              <Badge variant="secondary">
                {stats.total_chunks.toLocaleString()}
              </Badge>
            </div>

            <div>
              <div className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                <Filter className="h-3 w-3" /> By Regulation Type
              </div>
              <div className="space-y-1">
                <button
                  onClick={() => handleFilterChange("")}
                  className={cn(
                    "w-full text-left px-2 py-1 rounded text-sm hover:bg-muted transition-colors",
                    filterType === "" && "bg-primary/10 font-medium",
                  )}
                >
                  All Types
                </button>
                {Object.entries(stats.by_regulation_type).map(
                  ([type, count]) => (
                    <button
                      key={type}
                      onClick={() => handleFilterChange(type)}
                      className={cn(
                        "w-full text-left px-2 py-1 rounded text-sm hover:bg-muted transition-colors flex justify-between items-center",
                        filterType === type && "bg-primary/10 font-medium",
                      )}
                    >
                      <span
                        className={cn(
                          "px-1.5 py-0.5 rounded text-xs",
                          getRegTypeColor(type),
                        )}
                      >
                        {type}
                      </span>
                      <span className="text-muted-foreground text-xs">
                        {count.toLocaleString()}
                      </span>
                    </button>
                  ),
                )}
              </div>
            </div>
          </div>
        )}

        {/* Refresh */}
        <div className="p-4">
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => {
              fetchStats();
              fetchChunks(true);
            }}
          >
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
        </div>
      </div>

      {/* MIDDLE: Chunk List */}
      <div className="w-1/3 border-r flex flex-col">
        <div className="p-4 border-b bg-background">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">
              {chunks.length} chunks loaded
            </span>
            {hasMore && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => fetchChunks(false)}
              >
                Load More
              </Button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-auto">
          {loading && chunks.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground animate-pulse">
              Loading legal documents...
            </div>
          ) : chunks.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              No documents found.
            </div>
          ) : (
            <div className="divide-y">
              {chunks.map((chunk) => (
                <div
                  key={chunk.id}
                  onClick={() => setSelectedChunk(chunk)}
                  className={cn(
                    "p-3 cursor-pointer hover:bg-muted/50 transition-all",
                    selectedChunk?.id === chunk.id &&
                      "bg-primary/5 border-l-2 border-l-primary",
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={cn(
                        "px-1.5 py-0.5 rounded text-xs font-medium",
                        getRegTypeColor(chunk.regulation_type),
                      )}
                    >
                      {chunk.regulation_type}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      No. {chunk.document_number}/{chunk.year}
                    </span>
                  </div>
                  <div className="text-sm font-medium flex items-center gap-1">
                    {chunk.pasal && <span>Pasal {chunk.pasal}</span>}
                    {chunk.ayat && (
                      <span className="text-muted-foreground">
                        ({chunk.ayat})
                      </span>
                    )}
                    {chunk.huruf && (
                      <span className="text-muted-foreground">
                        huruf {chunk.huruf}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                    {chunk.text}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT: Detail Panel */}
      <div className="flex-1 overflow-auto bg-background">
        {!selectedChunk ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
            <BookOpen className="h-16 w-16 mb-4 opacity-20" />
            <p>Select a chunk to view details.</p>
          </div>
        ) : (
          <div className="p-8 max-w-4xl mx-auto space-y-6">
            {/* Header */}
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    "px-2 py-1 rounded text-sm font-bold",
                    getRegTypeColor(selectedChunk.regulation_type),
                  )}
                >
                  {selectedChunk.regulation_type}
                </span>
                <span className="text-xl font-bold">
                  No. {selectedChunk.document_number} Tahun {selectedChunk.year}
                </span>
              </div>
              {selectedChunk.doc_title && (
                <p className="text-lg text-muted-foreground">
                  {selectedChunk.doc_title}
                </p>
              )}
            </div>

            {/* Location */}
            <Card>
              <CardContent className="p-4">
                <div className="text-sm font-medium text-muted-foreground mb-2">
                  Location
                </div>
                <div className="flex flex-wrap gap-2">
                  {selectedChunk.pasal && (
                    <Badge variant="outline">
                      <Hash className="h-3 w-3 mr-1" /> Pasal{" "}
                      {selectedChunk.pasal}
                    </Badge>
                  )}
                  {selectedChunk.ayat && (
                    <Badge variant="outline">Ayat ({selectedChunk.ayat})</Badge>
                  )}
                  {selectedChunk.huruf && (
                    <Badge variant="outline">Huruf {selectedChunk.huruf}</Badge>
                  )}
                  {selectedChunk.chunk_type && (
                    <Badge variant="secondary">
                      {selectedChunk.chunk_type}
                    </Badge>
                  )}
                </div>
                {selectedChunk.hierarchy_path && (
                  <div className="mt-3 text-xs text-muted-foreground font-mono bg-muted p-2 rounded">
                    {selectedChunk.hierarchy_path}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Content */}
            <Card>
              <CardContent className="p-4">
                <div className="text-sm font-medium text-muted-foreground mb-2">
                  Content
                </div>
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <p className="whitespace-pre-wrap leading-relaxed">
                    {selectedChunk.text}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Metadata */}
            {selectedChunk.metadata &&
              Object.keys(selectedChunk.metadata).length > 0 && (
                <Card>
                  <CardContent className="p-4">
                    <div className="text-sm font-medium text-muted-foreground mb-2">
                      Raw Metadata
                    </div>
                    <pre className="text-xs bg-muted p-3 rounded overflow-auto max-h-[300px]">
                      {JSON.stringify(selectedChunk.metadata, null, 2)}
                    </pre>
                  </CardContent>
                </Card>
              )}

            {/* ID */}
            <div className="text-xs text-muted-foreground font-mono">
              ID: {selectedChunk.id}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
