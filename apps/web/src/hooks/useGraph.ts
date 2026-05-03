/**
 * useGraph — SSE subscription to the V6 graph-engine streaming endpoint.
 *
 * Emits StreamNodeEvent[] as the graph executes, with abort support.
 * Pattern from V5: isMountedRef safety for all async state updates.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { StreamNodeEvent, QueryRequest } from "@nuzantara/ts-schemas";
import { StreamEventType } from "@nuzantara/ts-schemas";
import { graphClient } from "@/lib/api/client";

export interface UseGraphOptions {
  onNodeStart?: (node: string) => void;
  onNodeEnd?: (node: string, data: Record<string, unknown>) => void;
  onAnswer?: (answer: string) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
}

export interface ExecuteOptions {
  user_id?: string;
  session_id?: string;
}

export interface UseGraphReturn {
  events: StreamNodeEvent[];
  currentNode: string;
  isRunning: boolean;
  error: string | null;
  execute: (query: string, options?: ExecuteOptions) => Promise<void>;
  abort: () => void;
}

export function useGraph(options: UseGraphOptions = {}): UseGraphReturn {
  const [events, setEvents] = useState<StreamNodeEvent[]>([]);
  const [currentNode, setCurrentNode] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      abortControllerRef.current?.abort();
    };
  }, []);

  const abort = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    if (isMountedRef.current) {
      setIsRunning(false);
    }
  }, []);

  const execute = useCallback(
    async (query: string, options: ExecuteOptions = {}) => {
      if (!isMountedRef.current) return;

      // Abort any previous run
      abortControllerRef.current?.abort();

      const controller = new AbortController();
      abortControllerRef.current = controller;

      setEvents([]);
      setCurrentNode("");
      setError(null);
      setIsRunning(true);

      const req: QueryRequest = {
        query,
        user_id: options.user_id ?? "anonymous",
        session_id: options.session_id,
      };

      try {
        for await (const event of graphClient.queryStream(
          req,
          controller.signal,
        )) {
          if (!isMountedRef.current) break;

          setEvents((prev) => [...prev, event]);

          if (event.event_type === StreamEventType.NODE_START && event.node) {
            setCurrentNode(event.node);
            optionsRef.current.onNodeStart?.(event.node);
          }

          if (event.event_type === StreamEventType.NODE_END && event.node) {
            optionsRef.current.onNodeEnd?.(event.node, event.data);
            if (event.data?.answer && typeof event.data.answer === "string") {
              optionsRef.current.onAnswer?.(event.data.answer);
            }
          }

          if (event.event_type === StreamEventType.ERROR) {
            const errMsg = (event.data?.error as string) ?? "Unknown error";
            setError(errMsg);
            optionsRef.current.onError?.(errMsg);
          }

          if (event.event_type === StreamEventType.DONE) {
            optionsRef.current.onDone?.();
          }
        }
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        const msg = (e as Error).message;
        if (isMountedRef.current) {
          setError(msg);
          optionsRef.current.onError?.(msg);
        }
      } finally {
        if (isMountedRef.current) {
          setIsRunning(false);
          setCurrentNode("");
        }
      }
    },
    [],
  );

  return { events, currentNode, isRunning, error, execute, abort };
}
