/**
 * React Hook for Cell-Giant SSE Streaming
 * Handles three-phase reasoning with progress indicators
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  CellGiantQueryRequest,
  CellGiantSSEEvent,
  CellGiantPhase,
  PhaseStatus,
} from '@/lib/api/zantara-sdk/types';

export interface CellGiantStreamState {
  phase: CellGiantPhase | null;
  phaseStatus: PhaseStatus | null;
  keepaliveElapsed: number;
  metadata: {
    giant_quality_score: number;
    giant_domain: string;
    corrections_count: number;
    enhancements_count: number;
    calibrations_count: number;
  } | null;
  tokens: string;
  isStreaming: boolean;
  isComplete: boolean;
  error: string | null;
  executionTime: number | null;
}

const initialState: CellGiantStreamState = {
  phase: null,
  phaseStatus: null,
  keepaliveElapsed: 0,
  metadata: null,
  tokens: '',
  isStreaming: false,
  isComplete: false,
  error: null,
  executionTime: null,
};

export function useCellGiantStream(baseUrl: string, apiKey?: string) {
  const [state, setState] = useState<CellGiantStreamState>(initialState);
  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const stream = useCallback(
    async (request: CellGiantQueryRequest) => {
      // Reset state
      setState(initialState);

      // Create abort controller for cleanup
      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      // Build URL
      const url = `${baseUrl}/api/agentic-rag/stream/cell-giant`;
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
                  const event: CellGiantSSEEvent = JSON.parse(data);
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

  const handleSSEEvent = useCallback((event: CellGiantSSEEvent) => {
    switch (event.type) {
      case 'phase':
        setState((prev) => ({
          ...prev,
          phase: event.data.name,
          phaseStatus: event.data.status,
        }));
        break;

      case 'keepalive':
        setState((prev) => ({
          ...prev,
          keepaliveElapsed: event.data.elapsed,
        }));
        break;

      case 'metadata':
        setState((prev) => ({
          ...prev,
          metadata: event.data,
        }));
        break;

      case 'token':
        setState((prev) => ({
          ...prev,
          tokens: prev.tokens + event.data,
        }));
        break;

      case 'done':
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          isComplete: true,
          executionTime: event.data.execution_time,
        }));
        break;

      case 'error':
        setState((prev) => ({
          ...prev,
          isStreaming: false,
          error: event.data.message,
        }));
        break;
    }
  }, []);

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
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

