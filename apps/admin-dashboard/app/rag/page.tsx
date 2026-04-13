"use client";
import { useState, useEffect } from "react";
import { error as logError } from "@/lib/logger";
import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Badge,
} from "@/components/ui/primitives";
import { Search, Sparkles, AlertCircle, Loader2 } from "lucide-react";

export default function RagPlayground() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [collections, setCollections] = useState<string[]>([]);
  const [selectedCollection, setSelectedCollection] =
    useState("knowledge_base");

  useEffect(() => {
    // Fetch collections for dropdown
    fetch("/api/qdrant/collections")
      .then((res) => res.json())
      .then((data) => {
        if (data.collections) {
          setCollections(data.collections.map((c: { name: string }) => c.name));
        }
      });
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setResults([]);

    try {
      const res = await fetch("/api/rag/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query,
          collection: selectedCollection,
          limit: 5,
        }),
      });
      const data = await res.json();
      if (data.results) {
        setResults(data.results);
      } else if (data.error) {
        logError(data.error);
        setResults([]); // Or show error state
      }
    } catch (error) {
      logError(error as string);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Sparkles className="h-8 w-8 text-primary" />
          RAG Playground
        </h1>
        <p className="text-muted-foreground mt-2">
          Debug semantic search by visualizing retrieval results. See exactly
          what the agents see.
        </p>
      </div>

      <Card className="border-2 border-primary/10">
        <CardHeader>
          <CardTitle>Simulation Query</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex gap-4">
            <select
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 w-[200px]"
              value={selectedCollection}
              onChange={(e) => setSelectedCollection(e.target.value)}
            >
              {collections.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
              {!collections.length && (
                <option value="knowledge_base">knowledge_base</option>
              )}
            </select>
            <div className="relative flex-1">
              <input
                type="text"
                placeholder="Ask something... e.g., 'What are the visa requirements for digital nomads?'"
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 pl-10 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <Search className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
            </div>
            <Button type="submit" disabled={loading} className="w-[120px]">
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Search"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold tracking-tight">
          Retrieval Results
        </h2>

        {results.length === 0 && !loading && (
          <div className="text-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
            No results to display. Run a simulation above.
          </div>
        )}

        {results.map((result, i) => (
          <Card
            key={result.id || i}
            className="overflow-hidden transition-all hover:shadow-md"
          >
            <CardHeader className="bg-muted/30 pb-3">
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={result.score > 0.75 ? "default" : "secondary"}
                  >
                    Score: {(result.score * 100).toFixed(1)}%
                  </Badge>
                  <span className="text-xs font-mono text-muted-foreground">
                    ID: {result.id}
                  </span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-3">
              {result.payload?.content ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <p className="whitespace-pre-wrap">
                    {String(result.payload.content).slice(0, 500)}...
                  </p>
                </div>
              ) : (
                <pre className="text-xs bg-muted p-4 rounded-md overflow-auto max-h-[300px]">
                  {JSON.stringify(result.payload, null, 2)}
                </pre>
              )}

              {result.payload?.metadata && (
                <div className="pt-2 border-t mt-2">
                  <div className="text-xs font-semibold text-muted-foreground mb-1">
                    Metadata
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(
                      result.payload.metadata as Record<string, any>,
                    ).map(([k, v]) => (
                      <div
                        key={k}
                        className="text-xs bg-secondary px-2 py-1 rounded"
                      >
                        <span className="font-semibold">{k}:</span>{" "}
                        {String(v).slice(0, 50)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
