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
    const response = (await (this.client as any).request('/api/agentic-rag/query', {
      method: 'POST',
      body: JSON.stringify({
        query: message,
        user_id: userId || userProfile?.id || 'anonymous',
        enable_vision: false,
      }),
    })) as AgenticQueryResponse;

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
    abortSignal?: AbortSignal,
    correlationId?: string,
    idleTimeoutMs: number = 60000, // 60s idle timeout (reset on data)
    maxTotalTimeMs: number = 600000 // 10min max total time
  ): Promise<void> {
    console.log('ChatApi: sendMessageStreaming called', { correlationId, timeoutMs, idleTimeoutMs, maxTotalTimeMs });
    const controller = new AbortController();
    let timedOut = false;
    let userCancelled = false;
    const startTime = Date.now();
    let lastDataTime = Date.now();
    
    // Max total time budget
    const maxTimeId = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, maxTotalTimeMs);
    
    // Idle timeout (reset on data arrival)
    let idleTimeoutId: NodeJS.Timeout | null = null;
    const resetIdleTimeout = () => {
      if (idleTimeoutId) {
        clearTimeout(idleTimeoutId);
      }
      lastDataTime = Date.now();
      idleTimeoutId = setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, idleTimeoutMs);
    };
    resetIdleTimeout(); // Start idle timer

    // Combine abort signals: abort controller if external signal aborts
    let abortListener: (() => void) | null = null;
    let wasAbortedBeforeStart = false;
    let requestAborted = false; // Track if request was aborted
    if (abortSignal) {
      // If external signal is already aborted, mark it but don't throw yet
      if (abortSignal.aborted) {
        wasAbortedBeforeStart = true;
        userCancelled = true;
        requestAborted = true;
        controller.abort();
        if (idleTimeoutId) clearTimeout(idleTimeoutId);
        clearTimeout(maxTimeId);
      } else {
        // Listen for external abort (user cancellation)
        abortListener = () => {
          userCancelled = true;
          requestAborted = true; // Mark request as aborted
          controller.abort();
          if (idleTimeoutId) clearTimeout(idleTimeoutId);
          clearTimeout(maxTimeId);
        };
        abortSignal.addEventListener('abort', abortListener);
      }
    }

    const signalToUse = controller.signal;

    // If aborted before start, call onError with appropriate message
    if (wasAbortedBeforeStart) {
      const error = new Error('Request cancelled') as Error & { code?: string };
      error.code = 'ABORTED';
      onError(error);
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

      // Add correlation ID for end-to-end tracing
      if (correlationId) {
        streamHeaders['X-Correlation-ID'] = correlationId;
      }

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
      console.log('ChatApi: about to fetch', { baseUrl, url: `${baseUrl}/api/agentic-rag/stream` });
      const response = await fetch(`${baseUrl}/api/agentic-rag/stream`, {
        method: 'POST',
        headers: streamHeaders,
        body: JSON.stringify(requestBody),
        credentials: 'include', // Send httpOnly cookies
        signal: signalToUse,
      });
      console.log('ChatApi: fetch returned', { status: response.status, ok: response.ok });

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
      // requestAborted already declared above in function scope

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
          if (signalToUse.aborted || requestAborted) {
            requestAborted = true; // Ensure flag is set
            await cancelReader();
            throw new Error('Request aborted');
          }

          const { done, value } = await reader.read();
          if (done) break;

          // Check if aborted after reading
          if (signalToUse.aborted || requestAborted) {
            requestAborted = true; // Ensure flag is set
            await cancelReader();
            throw new Error('Request aborted');
          }

          // Reset idle timeout on data arrival
          resetIdleTimeout();
          
          sseBuffer += decoder.decode(value, { stream: true });

          // SSE frames can be split across network chunks; buffer until we have full lines.
          const lines = sseBuffer.split('\n');
          sseBuffer = lines.pop() ?? '';

          let receivedDone = false;

          for (const rawLine of lines) {
            // Check if aborted during processing
            if (signalToUse.aborted || requestAborted) {
              requestAborted = true; // Ensure flag is set
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
              // Reset idle timeout on token (data arrival)
              resetIdleTimeout();
              // Only call callback if not aborted
              if (!signalToUse.aborted && !requestAborted) {
                onChunk(text);
              }
            } else if (data.type === 'status') {
              // Reset idle timeout on status update (data arrival)
              resetIdleTimeout();
              if (
                onStep &&
                typeof data.data === 'string' &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({ type: 'status', data: data.data, timestamp: new Date() });
              }
            } else if (data.type === 'tool_start') {
              // Reset idle timeout on tool_start (data arrival)
              resetIdleTimeout();
              if (
                onStep &&
                isRecord(data.data) &&
                typeof data.data.name === 'string' &&
                isRecord(data.data.args) &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({
                  type: 'tool_start',
                  data: { name: data.data.name, args: data.data.args },
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'tool_end') {
              // Reset idle timeout on tool_end (data arrival)
              resetIdleTimeout();
              if (
                onStep &&
                isRecord(data.data) &&
                typeof data.data.result === 'string' &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({
                  type: 'tool_end',
                  data: { result: data.data.result },
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'sources') {
              // Reset idle timeout on sources (data arrival)
              resetIdleTimeout();
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
      if (!signalToUse.aborted && !requestAborted) {
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
                if (!signalToUse.aborted && !requestAborted) {
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
        if (!signalToUse.aborted && !requestAborted) {
          onDone(fullResponse, sources, finalMetadata);
        }
      }
    } catch (error) {
      // Check abortSignal state at catch time (may have changed since listener was set)
      const isAbortSignalActive = abortSignal?.aborted === true;
      const isUserCancel = isAbortSignalActive && !timedOut;
      
      // Always call onError for timeouts and user cancellations
      // Only skip if component was unmounted (abortSignal.aborted but not timedOut/userCancelled)
      if (timedOut) {
        const timeoutError = new Error('Request timeout') as Error & { code?: string };
        timeoutError.code = 'TIMEOUT';
        onError(timeoutError);
      } else if (isUserCancel || userCancelled) {
        // User cancellation - call onError with ABORTED code
        const abortError = new Error('Request cancelled') as Error & { code?: string };
        abortError.code = 'ABORTED';
        onError(abortError);
      } else if (error instanceof Error && error.name === 'AbortError') {
        // Generic abort (could be timeout or user cancel)
        // Check abortSignal to determine if it was user-initiated
        if (timedOut) {
          const timeoutError = new Error('Request timeout') as Error & { code?: string };
          timeoutError.code = 'TIMEOUT';
          onError(timeoutError);
        } else if (isAbortSignalActive || userCancelled) {
          // User cancellation via abort signal
          const abortError = new Error('Request cancelled') as Error & { code?: string };
          abortError.code = 'ABORTED';
          onError(abortError);
        } else {
          // Unmount scenario - don't call onError
        }
      } else if (error instanceof Error && error.message === 'Request aborted') {
        // Request was aborted - determine reason
        if (timedOut) {
          const timeoutError = new Error('Request timeout') as Error & { code?: string };
          timeoutError.code = 'TIMEOUT';
          onError(timeoutError);
        } else if (userCancelled || isAbortSignalActive) {
          const abortError = new Error('Request cancelled') as Error & { code?: string };
          abortError.code = 'ABORTED';
          onError(abortError);
        }
        // If neither timedOut nor userCancelled, it might be unmount - skip onError
      } else {
        // Other errors - always call onError
        onError(error instanceof Error ? error : new Error('Streaming failed'));
      }
    } finally {
      // Clean up abort listener
      if (abortSignal && abortListener) {
        abortSignal.removeEventListener('abort', abortListener);
      }
      // Clean up all timeouts
      if (idleTimeoutId) {
        clearTimeout(idleTimeoutId);
      }
      clearTimeout(maxTimeId);
    }
  }
}
