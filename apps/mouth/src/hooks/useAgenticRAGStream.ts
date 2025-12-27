/**
 * React Hook for Agentic RAG SSE Streaming
 * Handles standard RAG queries with streaming responses
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  AgenticRAGQueryRequest,
  Source,
} from '@/lib/api/zantara-sdk/types';

export interface AgenticRAGStreamEvent {
  type: 'status' | 'token' | 'sources' | 'done' | 'error';
  data: string | Source[] | Record<string, unknown>;
}

export interface AgenticRAGStreamState {
  status: string | null;
  tokens: string;
  sources: Source[];
  isStreaming: boolean;
  isComplete: boolean;
  error: string | null;
  executionTime: number | null;
  routeUsed: string | null;
}

const initialState: AgenticRAGStreamState = {
  status: null,
  tokens: '',
  sources: [],
  isStreaming: false,
  isComplete: false,
  error: null,
  executionTime: null,
  routeUsed: null,
};

export function useAgenticRAGStream(baseUrl: string, apiKey?: string) {
  const [state, setState] = useState<AgenticRAGStreamState>(initialState);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stream = useCallback(
    async (request: AgenticRAGQueryRequest) => {
      // Reset state
      setState(initialState);

      // Create abort controller for cleanup
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // Build URL
      const url = `${baseUrl}/api/agentic-rag/stream`;
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };

      if (apiKey) {
        headers['Authorization'] = `Bearer ${apiKey}`;
      }

      setState((prev) => ({ ...prev, isStreaming: true }));

      try {
        const response = await fetch(url, {
          method: 'POST',
          headers,
          body: JSON.stringify(request),
          signal: abortController.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error('Response body is null');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE messages
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data.trim()) {
                try {
                  const event: AgenticRAGStreamEvent = JSON.parse(data);
                  handleSSEEvent(event);
                } catch (e) {
                  console.error('Failed to parse SSE event:', e);
                }
              }
            }
          }
        }

        setState((prev) => ({ ...prev, isStreaming: false, isComplete: true }));
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') {
          // Aborted, don't set error
          return;
        }
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: error instanceof Error ? error.message : 'Unknown error',
        }));
      }
    },
    [baseUrl, apiKey]
  );

  const handleSSEEvent = useCallback((event: AgenticRAGStreamEvent) => {
    switch (event.type) {
      case 'status':
        setState((prev) => ({
          ...prev,
          status: typeof event.data === 'string' ? event.data : null,
        }));
        break;

      case 'token':
        setState((prev) => ({
          ...prev,
          tokens: prev.tokens + (typeof event.data === 'string' ? event.data : ''),
        }));
        break;

      case 'sources':
        setState((prev) => ({
          ...prev,
          sources: Array.isArray(event.data) ? event.data : [],
        }));
        break;

      case 'done':
        const doneData = event.data as Record<string, unknown>;
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          isComplete: true,
          executionTime: doneData.execution_time as number | null,
          routeUsed: doneData.route_used as string | null,
        }));
        break;

      case 'error':
        const errorData = event.data as Record<string, unknown>;
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: (errorData.message as string) || 'Unknown error',
        }));
        break;
    }
  }, []);

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState((prev) => ({ ...prev, isStreaming: false }));
  }, []);

  const reset = useCallback(() => {
    stop();
    setState(initialState);
  }, [stop]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    ...state,
    stream,
    stop,
    reset,
  };
}





