'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { QdrantCollection, QdrantPoint } from '@/lib/api/admin/admin.types';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { RefreshCw, Layers, Terminal } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

export function VectorExplorer() {
  const [collections, setCollections] = useState<QdrantCollection[]>([]);
  const [selectedCol, setSelectedCol] = useState<string>('');
  const [points, setPoints] = useState<QdrantPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    try {
      const data = await api.getQdrantCollections();
      if (data && data.collections) {
          setCollections(data.collections);
      }
    } catch (err) {
      console.error('Failed to load collections', err);
    }
  };

  const loadPoints = async (collection: string) => {
    setIsLoading(true);
    try {
      const data = await api.getQdrantPoints(collection, 20); // Limit 20
      setPoints(data.points || []);
    } catch (err) {
      console.error('Failed to load points', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCollectionChange = (value: string) => {
    setSelectedCol(value);
    loadPoints(value);
  };

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-4 bg-black/40 p-4 rounded-lg border border-white/10">
        <Layers className="text-purple-500 w-5 h-5" />
        <Select value={selectedCol} onValueChange={handleCollectionChange}>
          <SelectTrigger className="w-[300px] bg-black border-white/20 text-white">
            <SelectValue placeholder="Select Vector Collection" />
          </SelectTrigger>
          <SelectContent className="bg-zinc-900 border-zinc-800 text-white">
            {collections.map((c) => (
              <SelectItem key={c.name} value={c.name} className="focus:bg-zinc-800 focus:text-white cursor-pointer">
                {c.name} <span className="text-zinc-500 ml-2">({c.status})</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="icon"
          onClick={() => selectedCol && loadPoints(selectedCol)}
          className="ml-auto"
          disabled={!selectedCol || isLoading}
        >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Points Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {points.length > 0 ? (
          points.map((point) => (
            <Card key={point.id} className="bg-black/40 border-white/10 p-4 font-mono text-xs overflow-hidden">
                <div className="flex justify-between items-center mb-2 border-b border-white/5 pb-2">
                    <span className="text-purple-400 font-bold">ID: {point.id}</span>
                    {point.score && <span className="text-zinc-500">Score: {point.score.toFixed(4)}</span>}
                </div>
                <ScrollArea className="h-[200px]">
                    <pre className="text-zinc-300 whitespace-pre-wrap">
                        {JSON.stringify(point.payload, null, 2)}
                    </pre>
                </ScrollArea>
            </Card>
          ))
        ) : (
             <div className="col-span-full h-[300px] flex flex-col items-center justify-center border border-white/5 rounded-lg border-dashed text-muted-foreground gap-2">
                <Terminal className="w-8 h-8 opacity-50" />
                {selectedCol ? 'No points found in this collection' : 'Select a collection to inspect vectors'}
            </div>
        )}
      </div>
    </div>
  );
}
