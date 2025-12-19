import { ApiClientBase } from '../client';
import { AgentStep } from '@/types';
import type { AgenticQueryResponse } from './chat.types';

/**
 * Chat/Streaming API methods
 */
export class ChatApi {
  constructor(private client: ApiClientBase) {}

  async sendMessage(
    message: string,
    userId?: string
  ): Promise<{
    response: string;
    sources: Array<{ title?: string; content?: string }>;
  }> {
    const userProfile = this.client.getUserProfile();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await (this.client as any).request(
      '/api/agentic-rag/query',
      {
        method: 'POST',
        body: JSON.stringify({
          query: message,
          user_id: userId || userProfile?.id || 'anonymous',
          enable_vision: false,
        }),
      }
    ) as AgenticQueryResponse;

    return {
      response: response.answer,
      sources: response.sources,
    };
  }

  // SSE streaming via backend `/api/agentic-rag/stream`
  async sendMessageStreaming(
    message: string,
    conversationId: string | undefined,
    onChunk: (chunk: string) => void,
    onDone: (
      fullResponse: string,
      sources: Array<{ title?: string; content?: string }>,
      metadata?: {
        execution_time?: number;
        route_used?: string;
        context_length?: number;
        emotional_state?: string;
        status?: string;
      }
    ) => void,
    onError: (error: Error) => void,
    onStep?: (step: AgentStep) => void,
    timeoutMs: number = 120000,
    conversationHistory?: Array<{ role: string; content: string }>,
    abortSignal?: AbortSignal
  ): Promise<void> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    
    // Combine abort signals: abort controller if external signal aborts
    let abortListener: (() => void) | null = null;
    let wasAbortedBeforeStart = false;
    if (abortSignal) {
      // If external signal is already aborted, mark it but don't throw yet
      if (abortSignal.aborted) {
        wasAbortedBeforeStart = true;
        controller.abort();
        clearTimeout(timeoutId);
      } else {
        // Listen for external abort
        abortListener = () => {
          // #region agent log
          const logData = {
            location: 'chat.api.ts:abortListener:called',
            message: 'Abort listener called - external signal aborted',
            data: { signalAborted: abortSignal.aborted, controllerAborted: controller.signal.aborted },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'C',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          controller.abort();
          clearTimeout(timeoutId);
        };
        abortSignal.addEventListener('abort', abortListener);
      }
    }
    
    const signalToUse = controller.signal;
    
    // If aborted before start, return early without calling callbacks
    if (wasAbortedBeforeStart) {
      return;
    }

    try {
      const userProfile = this.client.getUserProfile();
      // Build request body with session_id for conversation history
      const requestBody: {
        query: string;
        user_id: string;
        enable_vision: boolean;
        session_id?: string;
        conversation_history?: Array<{ role: string; content: string }>;
      } = {
        query: message,
        user_id: userProfile?.email || userProfile?.id || 'anonymous',
        enable_vision: false,
      };

      // Add session_id if provided (CRITICAL for conversation memory)
      if (conversationId) {
        requestBody.session_id = conversationId;
      }

      // Add conversation history directly (fallback when DB is unavailable)
      if (conversationHistory && conversationHistory.length > 0) {
        // Send last 10 messages for context
        requestBody.conversation_history = conversationHistory.slice(-10);
      }

      // Build headers with CSRF token for state-changing request
      const streamHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
      };

      // Add CSRF token for cookie-based auth
      const csrf = this.client.getCsrfToken();
      if (csrf) {
        streamHeaders['X-CSRF-Token'] = csrf;
      }

      // Keep Authorization header for backward compatibility
      const token = this.client.getToken();
      if (token) {
        streamHeaders['Authorization'] = `Bearer ${token}`;
      }

      const baseUrl = this.client.getBaseUrl();
      const response = await fetch(`${baseUrl}/api/agentic-rag/stream`, {
        method: 'POST',
        headers: streamHeaders,
        body: JSON.stringify(requestBody),
        credentials: 'include', // Send httpOnly cookies
        signal: signalToUse,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let sseBuffer = '';
      let fullResponse = '';
      let sources: Array<{ title?: string; content?: string }> = [];
      let finalMetadata: Record<string, unknown> | undefined = undefined;
      let readerCancelled = false;

      const cancelReader = async () => {
        if (!readerCancelled) {
          readerCancelled = true;
          try {
            await reader.cancel();
          } catch {
            // Ignore errors when canceling
          }
        }
      };

      const isRecord = (value: unknown): value is Record<string, unknown> =>
        typeof value === 'object' && value !== null;

      try {
        while (true) {
          // Check if aborted before reading
          if (signalToUse.aborted) {
            await cancelReader();
            throw new Error('Request aborted');
          }

          const { done, value } = await reader.read();
          if (done) break;

          // Check if aborted after reading
          if (signalToUse.aborted) {
            await cancelReader();
            throw new Error('Request aborted');
          }

          sseBuffer += decoder.decode(value, { stream: true });

          // SSE frames can be split across network chunks; buffer until we have full lines.
          const lines = sseBuffer.split('\n');
          sseBuffer = lines.pop() ?? '';

          let receivedDone = false;

          for (const rawLine of lines) {
            // Check if aborted during processing
            if (signalToUse.aborted) {
              await cancelReader();
              throw new Error('Request aborted');
            }

            const line = rawLine.replace(/\r$/, '');
            if (!line.startsWith('data:')) continue;

            const jsonStr = line.slice('data:'.length).trimStart();
            if (!jsonStr) continue;
            if (jsonStr === '[DONE]') {
              receivedDone = true;
              break;
            }

            let data: unknown;
            try {
              data = JSON.parse(jsonStr);
            } catch {
              console.warn('Failed to parse SSE message:', line);
              continue;
            }

            if (!isRecord(data) || typeof data.type !== 'string') continue;

            if (data.type === 'token') {
              const text =
                (typeof data.content === 'string' && data.content) ||
                (typeof data.data === 'string' && data.data) ||
                '';
              fullResponse += text;
              // Only call callback if not aborted
              // Hypothesis C: AbortSignal not synchronized with isMountedRef
              if (!signalToUse.aborted) {
                // #region agent log
                const logData = {
                  location: 'chat.api.ts:onChunk:called',
                  message: 'onChunk callback called from chat.api',
                  data: { signalAborted: signalToUse.aborted, textLength: text.length },
                  timestamp: Date.now(),
                  sessionId: 'debug-session',
                  runId: 'run1',
                  hypothesisId: 'C',
                };
                console.warn('[DEBUG]', logData);
                fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(logData),
                }).catch(() => {});
                // #endregion
                onChunk(text);
              } else {
                // #region agent log
                const logData = {
                  location: 'chat.api.ts:onChunk:blocked',
                  message: 'onChunk callback blocked due to abort signal',
                  data: { signalAborted: signalToUse.aborted },
                  timestamp: Date.now(),
                  sessionId: 'debug-session',
                  runId: 'run1',
                  hypothesisId: 'C',
                };
                console.warn('[DEBUG]', logData);
                fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(logData),
                }).catch(() => {});
                // #endregion
              }
            } else if (data.type === 'status') {
              if (onStep && typeof data.data === 'string' && !signalToUse.aborted) {
                onStep({ type: 'status', data: data.data, timestamp: new Date() });
              }
            } else if (data.type === 'tool_start') {
              if (
                onStep &&
                isRecord(data.data) &&
                typeof data.data.name === 'string' &&
                isRecord(data.data.args) &&
                !signalToUse.aborted
              ) {
                onStep({
                  type: 'tool_start',
                  data: { name: data.data.name, args: data.data.args },
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'tool_end') {
              if (onStep && isRecord(data.data) && typeof data.data.result === 'string' && !signalToUse.aborted) {
                onStep({
                  type: 'tool_end',
                  data: { result: data.data.result },
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'sources') {
              sources = Array.isArray(data.data)
                ? (data.data as Array<{ title?: string; content?: string }>)
                : [];
            } else if (data.type === 'metadata') {
              finalMetadata = isRecord(data.data) ? data.data : undefined;
            } else if (data.type === 'error') {
              const errorData = data.data;
              if (isRecord(errorData) && typeof errorData.message === 'string') {
                const error = new Error(errorData.message) as Error & { code?: string };
                if (typeof errorData.code === 'string') error.code = errorData.code;
                throw error;
              }
              throw new Error(typeof errorData === 'string' ? errorData : 'Unknown error');
            }
          }

          if (receivedDone) break;
        }
      } finally {
        // Always release the reader, even if aborted
        await cancelReader();
      }

      // Flush any remaining buffered line (best-effort), but only if not aborted
      if (!signalToUse.aborted) {
        const remaining = sseBuffer.trim();
        if (remaining.startsWith('data:')) {
          try {
            const jsonStr = remaining.slice('data:'.length).trimStart();
            if (jsonStr && jsonStr !== '[DONE]') {
              const data: unknown = JSON.parse(jsonStr);
              if (isRecord(data) && data.type === 'token') {
                const text =
                  (typeof data.content === 'string' && data.content) ||
                  (typeof data.data === 'string' && data.data) ||
                  '';
                fullResponse += text;
                if (!signalToUse.aborted) {
                  onChunk(text);
                }
              } else if (isRecord(data) && data.type === 'sources') {
                sources = Array.isArray(data.data)
                  ? (data.data as Array<{ title?: string; content?: string }>)
                  : [];
              } else if (isRecord(data) && data.type === 'metadata') {
                finalMetadata = isRecord(data.data) ? data.data : undefined;
              }
            }
          } catch {
            // ignore
          }
        }

        // Only call onDone if not aborted
        // Hypothesis C: AbortSignal not synchronized with isMountedRef
        if (!signalToUse.aborted) {
          // #region agent log
          const logData = {
            location: 'chat.api.ts:onDone:called',
            message: 'onDone callback called from chat.api',
            data: { signalAborted: signalToUse.aborted, responseLength: fullResponse.length },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'C',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          onDone(fullResponse, sources, finalMetadata);
        } else {
          // #region agent log
          const logData = {
            location: 'chat.api.ts:onDone:blocked',
            message: 'onDone callback blocked due to abort signal',
            data: { signalAborted: signalToUse.aborted },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'C',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
        }
      }
    } catch (error) {
      // Only call onError if not aborted (abort is expected behavior)
      // Hypothesis C: AbortSignal not synchronized with isMountedRef
      if (!signalToUse.aborted && !abortSignal?.aborted) {
        // #region agent log
        const logData = {
          location: 'chat.api.ts:onError:called',
          message: 'onError callback called from chat.api',
          data: { 
            signalAborted: signalToUse.aborted, 
            abortSignalAborted: abortSignal?.aborted,
            errorName: error instanceof Error ? error.name : 'Unknown',
            errorMessage: error instanceof Error ? error.message : String(error),
          },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'C',
        };
        console.warn('[DEBUG]', logData);
        fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(logData),
        }).catch(() => {});
        // #endregion
        
        if (error instanceof Error && error.name === 'AbortError') {
          onError(new Error('Request timeout'));
        } else if (error instanceof Error && error.message === 'Request aborted') {
          // Silently ignore abort - component was unmounted
          // Don't call onError for expected aborts
        } else {
          onError(error instanceof Error ? error : new Error('Streaming failed'));
        }
      } else {
        // #region agent log
        const logData = {
          location: 'chat.api.ts:onError:blocked',
          message: 'onError callback blocked due to abort signal',
          data: { 
            signalAborted: signalToUse.aborted, 
            abortSignalAborted: abortSignal?.aborted,
            errorName: error instanceof Error ? error.name : 'Unknown',
          },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'C',
        };
        console.warn('[DEBUG]', logData);
        fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(logData),
        }).catch(() => {});
        // #endregion
      }
    } finally {
      // Clean up abort listener
      if (abortSignal && abortListener) {
        abortSignal.removeEventListener('abort', abortListener);
      }
      clearTimeout(timeoutId);
    }
  }
}

