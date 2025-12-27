/**
 * Memory Context Component
 * Combines User Facts and Episodic Timeline in a unified view
 */

'use client';

import { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { UserFactsDisplay } from './UserFactsDisplay';
import { EpisodicTimeline } from './EpisodicTimeline';
import type {
  UserMemory,
  EpisodicEvent,
} from '@/lib/api/zantara-sdk/types';
import { ZantaraSDK } from '@/lib/api/zantara-sdk';

export interface MemoryContextProps {
  userId: string;
  sdk: ZantaraSDK;
  readonly?: boolean;
}

export function MemoryContext({ userId, sdk, readonly = false }: MemoryContextProps) {
  const [userMemory, setUserMemory] = useState<UserMemory | null>(null);
  const [episodicEvents, setEpisodicEvents] = useState<EpisodicEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadMemory();
  }, [userId]);

  const loadMemory = async () => {
    setLoading(true);
    setError(null);
    try {
      const [memory, events] = await Promise.all([
        sdk.getUserMemory(userId),
        sdk.getEpisodicTimeline({ user_id: userId, limit: 50 }),
      ]);
      setUserMemory(memory);
      setEpisodicEvents(events);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load memory');
    } finally {
      setLoading(false);
    }
  };

  const handleAddFact = async (fact: string) => {
    try {
      await sdk.addUserFact(userId, fact);
      await loadMemory();
    } catch (err) {
      throw err;
    }
  };

  const handleRemoveFact = async (index: number) => {
    // Note: SDK doesn't have remove fact endpoint yet
    // This would need to be implemented in the backend
    console.warn('Remove fact not implemented');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-muted-foreground">Loading memory...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-destructive">Error: {error}</p>
      </div>
    );
  }

  return (
    <Tabs defaultValue="facts" className="w-full">
      <TabsList className="grid w-full grid-cols-2">
        <TabsTrigger value="facts">Profile Facts</TabsTrigger>
        <TabsTrigger value="timeline">Event Timeline</TabsTrigger>
      </TabsList>
      <TabsContent value="facts" className="mt-4">
        <UserFactsDisplay
          facts={userMemory?.profile_facts || []}
          onAddFact={readonly ? undefined : handleAddFact}
          onRemoveFact={readonly ? undefined : handleRemoveFact}
          readonly={readonly}
        />
      </TabsContent>
      <TabsContent value="timeline" className="mt-4">
        <EpisodicTimeline events={episodicEvents} />
      </TabsContent>
    </Tabs>
  );
}






