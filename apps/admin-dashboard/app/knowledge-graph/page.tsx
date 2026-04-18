"use client";
import { useState, useEffect } from "react";
import { error as logError } from "@/lib/logger";
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardTitle,
} from "@/components/ui/primitives";
import { Network, Search, ArrowRight, GitMerge, CircleDot } from "lucide-react";
import { cn } from "@/lib/utils";

interface KGNode {
  entity_id: string;
  name: string;
  entity_type: string;
  description?: string;
  created_at?: string;
  source_collection?: string;
  properties?: Record<string, string | number | boolean>;
}

interface KGEdge {
  relationship_id: string;
  relationship_type: string;
  source_entity_id: string;
  target_entity_id: string;
  source_name?: string;
  target_name?: string;
  weight?: number;
}

export default function KnowledgeGraphPage() {
  const [nodes, setNodes] = useState<KGNode[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);
  const [edges, setEdges] = useState<KGEdge[]>([]);
  const [edgesLoading, setEdgesLoading] = useState(false);

  // Initial load
  useEffect(() => {
    fetchNodes();
  }, []);

  const fetchNodes = async (query = "") => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/kg/nodes${query ? `?search=${query}` : ""}`,
      );
      const data = await res.json();
      if (data.nodes) setNodes(data.nodes);
    } catch (e) {
      logError(e as string);
    } finally {
      setLoading(false);
    }
  };

  const handleNodeClick = async (node: KGNode) => {
    setSelectedNode(node);
    setEdgesLoading(true);
    try {
      const res = await fetch(`/api/kg/edges?nodeId=${node.entity_id}`);
      const data = await res.json();
      if (data.edges) setEdges(data.edges);
    } catch (e) {
      logError(e as string);
    } finally {
      setEdgesLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* LEFT: Node List */}
      <div className="w-1/3 border-r bg-muted/10 flex flex-col">
        <div className="p-4 border-b space-y-4">
          <div className="flex items-center gap-2">
            <Network className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold tracking-tight">
              Knowledge Graph
            </h1>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              className="w-full bg-background border rounded-md pl-9 pr-4 py-2 text-sm focus:ring-2 focus:ring-primary focus:outline-none"
              placeholder="Search entities..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && fetchNodes(search)}
            />
          </div>
        </div>

        <div className="flex-1 overflow-auto p-2 space-y-2">
          {loading ? (
            <div className="text-center py-10 text-muted-foreground animate-pulse">
              Scanning graph...
            </div>
          ) : nodes.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              No nodes found.
            </div>
          ) : (
            nodes.map((node) => (
              <div
                key={node.entity_id}
                onClick={() => handleNodeClick(node)}
                className={cn(
                  "p-3 rounded-md border cursor-pointer hover:bg-muted transition-all",
                  selectedNode?.entity_id === node.entity_id
                    ? "bg-primary/5 border-primary shadow-sm"
                    : "bg-card border-transparent",
                )}
              >
                <div className="flex justify-between items-start mb-1">
                  <span className="font-semibold block truncate">
                    {node.name}
                  </span>
                  <Badge variant="outline" className="text-[10px] uppercase">
                    {node.entity_type}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {node.description}
                </p>
              </div>
            ))
          )}
        </div>
      </div>

      {/* RIGHT: Node Detail & Edges */}
      <div className="flex-1 overflow-auto bg-background p-8">
        {!selectedNode ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
            <Network className="h-16 w-16 mb-4 opacity-20" />
            <p>Select a node to inspect its relationships.</p>
          </div>
        ) : (
          <div className="space-y-8 max-w-4xl mx-auto">
            {/* Node Header */}
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h2 className="text-3xl font-bold">{selectedNode.name}</h2>
                <Badge>{selectedNode.entity_type}</Badge>
              </div>
              <p className="text-lg text-muted-foreground leading-relaxed">
                {selectedNode.description}
              </p>
              <div className="mt-4 flex gap-4 text-xs text-muted-foreground">
                <div>
                  Created:{" "}
                  {selectedNode.created_at
                    ? new Date(selectedNode.created_at).toLocaleDateString()
                    : "—"}
                </div>
                <div>Source: {selectedNode.source_collection || "System"}</div>
              </div>
            </div>

            {/* Relationships */}
            <div className="space-y-4">
              <h3 className="text-xl font-bold flex items-center gap-2">
                <GitMerge className="h-5 w-5" />
                Relationships ({edges.length})
              </h3>

              {edgesLoading ? (
                <div className="py-8 text-center text-muted-foreground">
                  Tracing edges...
                </div>
              ) : edges.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground border-2 border-dashed rounded-lg">
                  This node is isolated (no edges found).
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3">
                  {edges.map((edge) => {
                    const isSource =
                      edge.source_entity_id === selectedNode.entity_id;
                    const otherName = isSource
                      ? edge.target_name
                      : edge.source_name;
                    const otherId = isSource
                      ? edge.target_entity_id
                      : edge.source_entity_id;

                    return (
                      <Card
                        key={edge.relationship_id}
                        className="hover:bg-muted/30 transition-colors"
                      >
                        <CardContent className="p-4 flex items-center gap-4">
                          <div
                            className={cn(
                              "p-2 rounded-full",
                              isSource
                                ? "bg-blue-100 text-blue-700"
                                : "bg-purple-100 text-purple-700",
                            )}
                          >
                            <CircleDot className="h-4 w-4" />
                          </div>
                          <div className="flex-1 flex items-center gap-2">
                            <span className="font-semibold text-sm">
                              {isSource ? "Sources" : "Targeted by"}
                            </span>
                            <ArrowRight className="h-4 w-4 text-muted-foreground" />
                            <Badge variant="outline">
                              {edge.relationship_type}
                            </Badge>
                            <ArrowRight className="h-4 w-4 text-muted-foreground" />
                            <span className="font-bold">{otherName}</span>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
