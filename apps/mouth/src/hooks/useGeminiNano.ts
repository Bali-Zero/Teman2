import { useState, useEffect, useCallback, useRef } from 'react';
import { logger } from '@/lib/logger';

// Experimental Type Definitions for Window.ai
declare global {
  interface Window {
    ai?: {
      assistant: {
        capabilities: () => Promise<AICapabilities>;
        create: (options?: AISessionOptions) => Promise<AIAssistantSession>;
      };
    };
  }
}

interface AICapabilities {
  available: 'readily' | 'after-download' | 'no';
  defaultTemperature?: number;
  defaultTopK?: number;
  maxTopK?: number;
}

interface AISessionOptions {
  temperature?: number;
  topK?: number;
}

interface AIAssistantSession {
  prompt: (text: string) => Promise<string>;
  promptStreaming: (text: string) => AsyncIterable<string>;
  destroy: () => void;
  clone: () => Promise<AIAssistantSession>;
}

export type EdgeAIStatus = 'checking' | 'ready' | 'downloading' | 'unsupported' | 'error';

interface UseGeminiNanoReturn {
  status: EdgeAIStatus;
  isReady: boolean;
  generate: (prompt: string) => Promise<string>;
  generateStream: (prompt: string, onChunk: (chunk: string) => void) => Promise<void>;
  latency: number | null; // Last prompt latency in ms
  error: string | null;
}

export const useGeminiNano = (): UseGeminiNanoReturn => {
  const [status, setStatus] = useState<EdgeAIStatus>('checking');
  const [error, setError] = useState<string | null>(null);
  const [latency, setLatency] = useState<number | null>(null);
  const sessionRef = useRef<AIAssistantSession | null>(null);

  // Initialize and check capabilities
  useEffect(() => {
    let active = true;

    const checkAvailability = async () => {
      try {
        if (!window.ai || !window.ai.assistant) {
          if (active) {
            setStatus('unsupported');
            setError('Window.ai API not found. Please enable Chrome flags.');
          }
          return;
        }

        const capabilities = await window.ai.assistant.capabilities();
        logger.debug('[EdgeAI] Capabilities checked', {
          metadata: { available: capabilities.available },
        });

        if (capabilities.available === 'no') {
          if (active) setStatus('unsupported');
        } else if (capabilities.available === 'after-download') {
          if (active) setStatus('downloading');
          // We could try to initialize here to trigger download, but better let user trigger it
        } else {
          if (active) setStatus('ready');
        }
      } catch (err) {
        if (active) {
          setStatus('error');
          setError(err instanceof Error ? err.message : 'Unknown error checking capabilities');
        }
      }
    };

    checkAvailability();
    return () => {
      active = false;
    };
  }, []);

  // Helper to get or create session
  const getSession = async (): Promise<AIAssistantSession> => {
    if (sessionRef.current) return sessionRef.current;

    if (!window.ai) throw new Error('AI API not available');

    // Create new session
    const session = await window.ai.assistant.create({
      temperature: 0.7,
      topK: 3,
    });
    sessionRef.current = session;
    return session;
  };

  const generate = useCallback(async (text: string): Promise<string> => {
    const startTime = performance.now();
    try {
      setError(null);
      const session = await getSession();
      const result = await session.prompt(text);
      setLatency(performance.now() - startTime);
      return result;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Generation failed';
      setError(msg);
      // Invalidate session on error as it might be dead
      if (sessionRef.current) {
        try {
          sessionRef.current.destroy();
        } catch (e) {
          /* ignore */
        }
        sessionRef.current = null;
      }
      throw err;
    }
  }, []);

  const generateStream = useCallback(async (text: string, onChunk: (chunk: string) => void) => {
    const startTime = performance.now();
    try {
      setError(null);
      const session = await getSession();
      const stream = session.promptStreaming(text);

      let fullResponse = '';
      for await (const chunk of stream) {
        // The API returns the full accumulated text in each chunk usually, or depends on implementation.
        // Current spec says it yields the new string state.
        // Let's assume it yields the accumulated string for now (standard behavior of this API).
        fullResponse = chunk;
        onChunk(chunk);
      }
      setLatency(performance.now() - startTime);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Stream generation failed';
      setError(msg);
      if (sessionRef.current) {
        try {
          sessionRef.current.destroy();
        } catch (e) {
          /* ignore */
        }
        sessionRef.current = null;
      }
      throw err;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (sessionRef.current) {
        try {
          sessionRef.current.destroy();
        } catch (e) {
          logger.error(
            'Error destroying session',
            { component: 'useGeminiNano' },
            e instanceof Error ? e : new Error(String(e))
          );
        }
      }
    };
  }, []);

  return {
    status,
    isReady: status === 'ready',
    generate,
    generateStream,
    latency,
    error,
  };
};
