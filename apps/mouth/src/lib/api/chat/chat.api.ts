import type { IApiClient } from '../types/api-client.types';
import { AgentStep } from '@/types';
import type { AgenticQueryResponse } from './chat.types';
import { logger } from '@/lib/logger';
import {
  retryableFetch,
  classifyStreamError,
  DEFAULT_RETRY_CONFIG,
  type RetryConfig,
} from './streaming-retry';

/**
 * NOTE: Image response cleaning is now handled by the backend.
 *
 * The backend's `clean_image_generation_response` function (in agentic_rag.py)
 * is the SINGLE SOURCE OF TRUTH for image response cleaning.
 *
 * It processes token events during streaming, removing:
 * - Pollinations URLs and subdomains
 * - Markdown image syntax
 * - Version numbers and intro/outro lines
 * - URL-encoded content
 * - Other image generation artifacts
 *
 * This frontend function has been removed to eliminate code duplication.
 * The backend ensures all responses are cleaned before being sent to the client.
 */

/**
 * Chat/Streaming API methods
 *
 * Uses Zantara AI v2.0 - Single LLM architecture with RAG
 */
export class ChatApi {
  constructor(private client: IApiClient) {}

  async sendMessage(
    message: string,
    userId?: string
  ): Promise<{
    response: string;
    sources: Array<{ title?: string; content?: string }>;
  }> {
    const userProfile = this.client.getUserProfile();
    const response = await this.client.request<AgenticQueryResponse>('/api/agentic-rag/query', {
      method: 'POST',
      body: JSON.stringify({
        query: message,
        user_id: userId || userProfile?.id || 'anonymous',
        enable_vision: false,
      }),
    });

    return {
      response: response.answer,
      sources: response.sources,
    };
  }

  /**
   * SSE streaming via backend `/api/agentic-rag/stream` (Zantara AI v2.0)
   *
   * **SOURCE OF TRUTH** for client-side streaming. This is the active implementation.
   *
   * Features:
   * - ✅ Robust error handling with error codes (TIMEOUT, ABORTED)
   * - ✅ Configurable timeouts (request, idle, max total time)
   * - ✅ Abort signal support for cancellation
   * - ✅ Image cleaning (removes pollinations URLs and artifacts)
   * - ✅ Correlation ID support for end-to-end tracing
   * - ✅ CSRF token handling for cookie-based auth
   * - ✅ Support for 13 event types (token, sources, metadata, image, reasoning_step, phase, keepalive, thinking, tool_call, observation, status, tool_start, tool_end)
   * - ✅ Vision support (image attachments)
   * - ✅ Conversation history management
   * - ✅ Unmount detection (doesn't call callbacks if component unmounted)
   *
   * @param message - User message text
   * @param conversationId - Session ID for conversation continuity
   * @param onChunk - Callback for each token chunk (receives accumulated text)
   * @param onDone - Callback when stream completes (receives full response, sources, metadata)
   * @param onError - Callback for errors (receives Error with optional code)
   * @param onStep - Optional callback for step events (reasoning, tool calls, etc.)
   * @param timeoutMs - Request timeout in ms (default: 120s)
   * @param conversationHistory - Previous messages for context (max 200)
   * @param abortSignal - AbortSignal for cancellation
   * @param correlationId - Correlation ID for tracing
   * @param idleTimeoutMs - Idle timeout in ms, resets on data (default: 60s)
   * @param maxTotalTimeMs - Maximum total time in ms (default: 10min)
   * @param images - Vision images (base64 encoded)
   *
   * @throws Never throws - all errors are passed to onError callback
   *
   * @example
   * ```typescript
   * await api.sendMessageStreaming(
   *   'Hello',
   *   sessionId,
   *   (chunk) => logger.debug('Chunk:', chunk, { component: "AUTO", action: "log" }),
   *   (full, sources, metadata) => logger.debug('Done:', full, { component: "AUTO", action: "log" }),
   *   (error) => logger.error('Error:', error, { component: "AUTO", action: "error" }, toError('Error:', error)),
   *   (step) => logger.debug('Step:', step, { component: "AUTO", action: "log" })
   * );
   * ```
   */
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
        user_memory_facts?: string[];
        collective_memory_facts?: string[];
        golden_answer_used?: boolean;
        followup_questions?: string[];
        generated_image?: string;
      }
    ) => void,
    onError: (error: Error) => void,
    onStep?: (step: AgentStep) => void,
    timeoutMs: number = 120000,
    conversationHistory?: Array<{ role: string; content: string }>,
    abortSignal?: AbortSignal,
    correlationId?: string,
    idleTimeoutMs: number = 300000, // 5min idle timeout for testing (reset on data)
    maxTotalTimeMs: number = 600000, // 10min max total time
    images?: Array<{ base64: string; name: string }> // Vision images
  ): Promise<void> {
    // CRITICAL FIX: Bypass Vercel proxy for SSE streaming (Vercel kills SSE streams)
    // Use direct Fly.io endpoint when NEXT_PUBLIC_SSE_DIRECT=true
    const useDirectEndpoint = process.env.NEXT_PUBLIC_SSE_DIRECT === 'true';
    const endpoint = useDirectEndpoint
      ? `${process.env.NEXT_PUBLIC_API_URL}/api/agentic-rag/stream`
      : '/api/agentic-rag/stream';

    // Metrics tracking
    const startTime = Date.now();
    let firstChunkTime: number | null = null;
    let lastChunkTime: number | null = null;
    let chunkCount = 0;
    let totalBytesReceived = 0;
    let eventTypeCounts: Record<string, number> = {};

    const controller = new AbortController();
    let timedOut = false;
    let userCancelled = false;
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
      const hasImages = !!(images && images.length > 0);
      const requestBody: {
        query: string;
        user_id: string;
        enable_vision: boolean;
        session_id?: string;
        conversation_history?: Array<{ role: string; content: string }>;
        images?: Array<{ base64: string; name: string }>;
      } = {
        query: message,
        user_id: userProfile?.email || userProfile?.id || 'anonymous',
        enable_vision: hasImages, // Enable vision when images are attached
        ...(hasImages && { images }), // Include images if present
      };

      // Add session_id if provided (CRITICAL for conversation memory)
      if (conversationId) {
        requestBody.session_id = conversationId;
      }

      // Add conversation history directly (fallback when DB is unavailable)
      if (conversationHistory && conversationHistory.length > 0) {
        // Send last 200 messages for context (~100 turns of conversation)
        requestBody.conversation_history = conversationHistory.slice(-200);
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

      // Build full URL: if endpoint is absolute (starts with http), use it directly
      // Otherwise, concatenate with baseUrl (proxy path)
      const baseUrl = this.client.getBaseUrl();
      const fullUrl = endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint}`;

      // Retry only the initial handshake on classified network errors.
      // Mid-stream drops are surfaced after `firstChunkTime` is set; the UI
      // decides whether to offer a manual retry (full re-send) since the
      // backend cannot resume from an arbitrary chunk yet.
      // TODO(backend-resume-token): pass `X-Stream-Resume-Token` once available
      // (see apps/mouth/docs/issues/backend-resume-token-DRAFT.md).
      const response = await retryableFetch(
        () =>
          fetch(fullUrl, {
            method: 'POST',
            headers: streamHeaders,
            body: JSON.stringify(requestBody),
            credentials: 'include', // Send httpOnly cookies
            signal: signalToUse,
          }),
        {
          signal: signalToUse,
          onRetry: (attempt, delayMs, err) => {
            logger.info('Retrying SSE handshake', {
              component: 'ChatApi',
              action: 'retryHandshake',
              metadata: {
                attempt,
                delayMs,
                errorClass: classifyStreamError(err),
                correlationId,
              },
            });
          },
        }
      );

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
      let generatedImageUrl: string | undefined = undefined; // Track generated images
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

          // Track metrics
          if (value) {
            totalBytesReceived += value.length;
            if (!firstChunkTime) {
              firstChunkTime = Date.now();
            }
            lastChunkTime = Date.now();
          }

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
              logger.warn('Failed to parse SSE message', {
                component: 'ChatApi',
                action: 'parseSSE',
                metadata: { line: line.substring(0, 100) }, // Truncate for safety
              });
              continue;
            }

            if (!isRecord(data) || typeof data.type !== 'string') continue;

            // Track event types for metrics
            eventTypeCounts[data.type] = (eventTypeCounts[data.type] || 0) + 1;

            // Handle reasoning events
            if (data.type === 'reasoning_step') {
              resetIdleTimeout();
              if (
                onStep &&
                isRecord(data.data) &&
                typeof data.data.phase === 'string' &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({
                  type: 'reasoning_step',
                  data: {
                    phase: data.data.phase as string,
                    status: (data.data.status as string) || 'in_progress',
                    message: (data.data.message as string) || '',
                    description: data.data.description as string | undefined,
                    details: data.data.details as Record<string, unknown> | undefined,
                  },
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'phase') {
              // Reset idle timeout on phase update
              resetIdleTimeout();
              if (
                onStep &&
                isRecord(data.data) &&
                typeof data.data.name === 'string' &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({
                  type: 'phase',
                  data: {
                    name: data.data.name as string,
                    status: (data.data.status as string) || 'started',
                  },
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'keepalive') {
              // Reset idle timeout on keepalive - this keeps connection alive during long operations
              resetIdleTimeout();
              // Optionally notify about progress
              if (onStep && isRecord(data.data) && !signalToUse.aborted && !requestAborted) {
                const phase = (data.data.phase as string) || 'processing';
                const elapsed = (data.data.elapsed as number) || 0;
                // Only show status for longer operations (after 20s)
                if (elapsed >= 20) {
                  onStep({
                    type: 'status',
                    data: `⏳ Still ${phase}... (${elapsed}s)`,
                    timestamp: new Date(),
                  });
                }
              }
            } else if (data.type === 'thinking') {
              // Emit thinking event with step info
              resetIdleTimeout();
              if (
                onStep &&
                typeof data.data === 'string' &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({
                  type: 'thinking',
                  data: data.data,
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'tool_call') {
              // Emit tool_call event with tool name and args
              resetIdleTimeout();
              if (
                onStep &&
                isRecord(data.data) &&
                typeof data.data.tool === 'string' &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({
                  type: 'tool_call',
                  data: {
                    tool: data.data.tool,
                    args: isRecord(data.data.args) ? data.data.args : {},
                  },
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'observation') {
              // Emit observation event (tool result)
              resetIdleTimeout();
              if (
                onStep &&
                typeof data.data === 'string' &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                onStep({
                  type: 'observation',
                  data: data.data,
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'token') {
              const text =
                (typeof data.content === 'string' && data.content) ||
                (typeof data.data === 'string' && data.data) ||
                '';
              fullResponse += text;
              chunkCount++;
              // Reset idle timeout on token (data arrival)
              resetIdleTimeout();
              // Only call callback if not aborted
              // Note: Image cleaning is handled by backend (clean_image_generation_response)
              if (!signalToUse.aborted && !requestAborted) {
                onChunk(fullResponse);
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
                onStep({
                  type: 'status',
                  data: data.data,
                  timestamp: new Date(),
                });
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
              finalMetadata = isRecord(data.data)
                ? { ...(finalMetadata ?? {}), ...data.data }
                : finalMetadata;
            } else if (data.type === 'image') {
              // Handle generated images from image generation tool
              resetIdleTimeout();
              if (isRecord(data.data) && typeof data.data.url === 'string') {
                generatedImageUrl = data.data.url;
              }
            } else if (data.type === 'nlm_status') {
              resetIdleTimeout();
              if (onStep && isRecord(data.data) && !signalToUse.aborted && !requestAborted) {
                onStep({
                  type: 'nlm_status',
                  data: data.data,
                  timestamp: new Date(),
                });
              }
              finalMetadata = {
                ...(finalMetadata ?? {}),
                nlm_status: isRecord(data.data) ? (data.data.status as string) : undefined,
                nlm_domain_label: isRecord(data.data)
                  ? (data.data.domain_label as string)
                  : undefined,
              };
            } else if (data.type === 'nlm_enrichment') {
              resetIdleTimeout();
              finalMetadata = {
                ...(finalMetadata ?? {}),
                nlm_status: 'verified',
                nlm_citations: isRecord(data.data) ? (data.data.citations as unknown[]) : undefined,
                nlm_domain_label: isRecord(data.data)
                  ? (data.data.domain_label as string)
                  : undefined,
              };
              if (onStep && isRecord(data.data) && !signalToUse.aborted && !requestAborted) {
                onStep({
                  type: 'nlm_enrichment',
                  data: data.data,
                  timestamp: new Date(),
                });
              }
            } else if (data.type === 'evidence_score') {
              resetIdleTimeout();
              finalMetadata = {
                ...(finalMetadata ?? {}),
                evidence_score: isRecord(data.data) ? (data.data.score as number) : undefined,
              };
            } else if (data.type === 'error') {
              const errorData = data.data;
              if (isRecord(errorData) && typeof errorData.message === 'string') {
                const error = new Error(errorData.message) as Error & {
                  code?: string;
                };
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
                // Note: Image cleaning is handled by backend
                if (!signalToUse.aborted && !requestAborted) {
                  onChunk(fullResponse);
                }
              } else if (isRecord(data) && data.type === 'sources') {
                sources = Array.isArray(data.data)
                  ? (data.data as Array<{ title?: string; content?: string }>)
                  : [];
              } else if (isRecord(data) && data.type === 'metadata') {
                finalMetadata = isRecord(data.data)
                  ? { ...(finalMetadata ?? {}), ...data.data }
                  : finalMetadata;
              }
            }
          } catch {
            // ignore
          }
        }

        // Only call onDone if not aborted
        if (!signalToUse.aborted && !requestAborted) {
          // Calculate final metrics
          const totalDuration = Date.now() - startTime;
          const timeToFirstChunk = firstChunkTime ? firstChunkTime - startTime : null;
          const streamingDuration =
            lastChunkTime && firstChunkTime ? lastChunkTime - firstChunkTime : null;

          // Log metrics
          logger.info('Stream completed', {
            component: 'ChatApi',
            action: 'sendMessageStreaming',
            metadata: {
              correlationId,
              totalDuration: `${totalDuration}ms`,
              timeToFirstChunk: timeToFirstChunk ? `${timeToFirstChunk}ms` : null,
              streamingDuration: streamingDuration ? `${streamingDuration}ms` : null,
              chunkCount,
              totalBytesReceived,
              responseLength: fullResponse.length,
              sourcesCount: sources.length,
              eventTypes: eventTypeCounts,
              hasGeneratedImage: !!generatedImageUrl,
            },
          });

          // Merge generated image into metadata if present
          let metadataWithImage = generatedImageUrl
            ? { ...finalMetadata, generated_image: generatedImageUrl }
            : finalMetadata;

          // Graceful NLM badge fade: if response landed outside CAUTIOUS zone
          // but the badge was still showing "consulting", clear it to "not_needed"
          if (
            isRecord(metadataWithImage) &&
            metadataWithImage.confidence_zone !== 'cautious' &&
            metadataWithImage.nlm_status === 'consulting'
          ) {
            metadataWithImage = {
              ...metadataWithImage,
              nlm_status: 'not_needed',
            };
          }

          // Note: Image cleaning is handled by backend (clean_image_generation_response)
          // Backend processes token events during streaming, so fullResponse is already cleaned
          onDone(fullResponse, sources, metadataWithImage);
        }
      }
    } catch (error) {
      // Calculate error metrics
      const errorDuration = Date.now() - startTime;

      // Check abortSignal state at catch time (may have changed since listener was set)
      const isAbortSignalActive = abortSignal?.aborted === true;
      const isUserCancel = isAbortSignalActive && !timedOut;

      // Log error metrics
      logger.error(
        'Stream error',
        {
          component: 'ChatApi',
          action: 'sendMessageStreaming',
          metadata: {
            correlationId,
            errorType: error instanceof Error ? error.name : 'Unknown',
            errorMessage: error instanceof Error ? error.message : String(error),
            duration: `${errorDuration}ms`,
            timedOut,
            userCancelled: isUserCancel || userCancelled,
            chunkCount,
            totalBytesReceived,
            eventTypes: eventTypeCounts,
          },
        },
        error instanceof Error ? error : new Error(String(error))
      );

      // Always call onError for timeouts and user cancellations
      // Only skip if component was unmounted (abortSignal.aborted but not timedOut/userCancelled)
      if (timedOut) {
        const timeoutError = new Error('Request timeout') as Error & {
          code?: string;
        };
        timeoutError.code = 'TIMEOUT';
        onError(timeoutError);
      } else if (isUserCancel || userCancelled) {
        // User cancellation - call onError with ABORTED code
        const abortError = new Error('Request cancelled') as Error & {
          code?: string;
        };
        abortError.code = 'ABORTED';
        onError(abortError);
      } else if (error instanceof Error && error.name === 'AbortError') {
        // Generic abort (could be timeout or user cancel)
        // Check abortSignal to determine if it was user-initiated
        if (timedOut) {
          const timeoutError = new Error('Request timeout') as Error & {
            code?: string;
          };
          timeoutError.code = 'TIMEOUT';
          onError(timeoutError);
        } else if (isAbortSignalActive || userCancelled) {
          // User cancellation via abort signal
          const abortError = new Error('Request cancelled') as Error & {
            code?: string;
          };
          abortError.code = 'ABORTED';
          onError(abortError);
        } else {
          // Unmount scenario - don't call onError
        }
      } else if (error instanceof Error && error.message === 'Request aborted') {
        // Request was aborted - determine reason
        if (timedOut) {
          const timeoutError = new Error('Request timeout') as Error & {
            code?: string;
          };
          timeoutError.code = 'TIMEOUT';
          onError(timeoutError);
        } else if (userCancelled || isAbortSignalActive) {
          const abortError = new Error('Request cancelled') as Error & {
            code?: string;
          };
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
