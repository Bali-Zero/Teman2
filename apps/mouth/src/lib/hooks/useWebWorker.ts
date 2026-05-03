"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { logger } from "@/lib/logger";

type WorkerMessage = {
  type: string;
  data: unknown;
  id: string;
};

type WorkerResponse = {
  type: string;
  result: unknown;
  id: string;
  error?: string;
};

/**
 * Hook per utilizzare Web Workers
 * Migliora INP offloadando task pesanti dal main thread
 */
export function useWebWorker() {
  const workerRef = useRef<Worker | null>(null);
  const pendingRef = useRef<Map<string, (data: unknown) => void>>(new Map());
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    // Create worker only in browser
    if (typeof window !== "undefined") {
      workerRef.current = new Worker("/workers/data-processor.js");
      setIsReady(true);

      workerRef.current.onmessage = (event: MessageEvent<WorkerResponse>) => {
        const { id, result, error } = event.data;
        const resolver = pendingRef.current.get(id);

        if (resolver) {
          if (error) {
            logger.error("Worker error", { note: String(error) });
          } else {
            resolver(result);
          }
          pendingRef.current.delete(id);
        }
      };

      workerRef.current.onerror = (error) => {
        logger.error("Worker error", { note: error.message });
      };

      return () => {
        workerRef.current?.terminate();
      };
    }
  }, []);

  const sendMessage = useCallback(
    <T>(type: string, data: unknown): Promise<T> => {
      return new Promise((resolve) => {
        if (!workerRef.current) {
          // Fallback to main thread if worker not available
          resolve(data as T);
          return;
        }

        const id = `${type}-${Date.now()}-${Math.random()}`;
        pendingRef.current.set(id, resolve as (data: unknown) => void);

        workerRef.current.postMessage({
          type,
          data,
          id,
        });
      });
    },
    [],
  );

  const sortArticles = useCallback(
    <T extends { publishedAt: string }>(articles: T[]): Promise<T[]> => {
      return sendMessage<T[]>("SORT_ARTICLES", articles);
    },
    [sendMessage],
  );

  const filterArticles = useCallback(
    <T>(
      articles: T[],
      query: string,
      filters?: { category?: string },
    ): Promise<T[]> => {
      return sendMessage<T[]>("FILTER_ARTICLES", {
        articles,
        query,
        filters,
      });
    },
    [sendMessage],
  );

  const processConversations = useCallback(
    <T>(conversations: T[], page: number, pageSize: number): Promise<T[]> => {
      return sendMessage<T[]>("PROCESS_CONVERSATIONS", {
        conversations,
        page,
        pageSize,
      });
    },
    [sendMessage],
  );

  const calculateStats = useCallback(
    (
      numbers: number[],
    ): Promise<{
      count: number;
      sum: number;
      avg: number;
      min: number;
      max: number;
    }> => {
      return sendMessage("CALCULATE_STATS", numbers);
    },
    [sendMessage],
  );

  return {
    isReady,
    sortArticles,
    filterArticles,
    processConversations,
    calculateStats,
  };
}

export type UseWebWorkerReturn = ReturnType<typeof useWebWorker>;
