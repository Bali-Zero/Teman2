import type { IApiClient } from '../types/api-client.types';
import { AgentStep } from '@/types';
import type { AgenticQueryResponse } from './chat.types';

/**
 * Clean image generation response to remove ugly pollinations URLs
 * NOTE: This is duplicated in actions.ts for server-side use.
 * Keep both in sync if making changes.
 */
function cleanImageResponse(text: string): string {
  if (!text || !text.toLowerCase().includes('pollinations')) {
    return text;
  }

  // Process line by line
  const lines = text.split('\n');
  const cleanedLines = lines.filter(line => {
    const lineLower = line.toLowerCase();
    // Skip lines with pollinations URLs
    if (lineLower.includes('pollinations')) return false;
    // Skip [Visualizza Immagine] lines
    if (line.trim().startsWith('[Visualizza')) return false;
    // Skip numbered version lines like "1. **Versione..." or "1. Versione..."
    if (/^\s*\d+\.\s*\*{0,2}(Versione|Prima|Seconda|Opzione)/i.test(line)) return false;
    // Skip intro lines that mention "opzioni" or "varianti" for images
    if (/ecco le opzioni|ho (elaborato|generato|creato) due|ti propongo|due varianti|ecco i risultati/i.test(lineLower)) return false;
    // Skip "Spero che queste opzioni" outro lines
    if (/spero che queste|se hai bisogno di|vadano bene per/i.test(lineLower)) return false;
    // Skip lines starting with (http...
    if (line.trim().startsWith('(http')) return false;
    // Skip lines that are just URLs
    if (/^https?:\/\//i.test(line.trim())) return false;
    return true;
  });

  let result = cleanedLines.join('\n');
  // Clean up multiple newlines
  result = result.replace(/\n{3,}/g, '\n\n').trim();

  // If almost everything was removed, provide default
  if (result.length < 30) {
    result = "Ecco l'immagine che hai richiesto! 🎨";
  }

  return result;
}

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

  // SSE streaming via backend `/api/agentic-rag/stream` (Zantara AI v2.0)
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
    idleTimeoutMs: number = 60000, // 60s idle timeout (reset on data)
    maxTotalTimeMs: number = 600000 // 10min max total time
  ): Promise<void> {
    // Always use standard Zantara AI endpoint (v2.0)
    const endpoint = '/api/agentic-rag/stream';

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

      const baseUrl = this.client.getBaseUrl();
      const fullUrl = `${baseUrl}${endpoint}`;
      const response = await fetch(fullUrl, {
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
      let generatedImageUrl: string | undefined = undefined;  // Track generated images
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
                    status: (data.data.status as string) || 'started' 
                  }, 
                  timestamp: new Date() 
                });
              }
            } else if (data.type === 'keepalive') {
              // Reset idle timeout on keepalive - this keeps connection alive during long operations
              resetIdleTimeout();
              // Optionally notify about progress
              if (
                onStep &&
                isRecord(data.data) &&
                !signalToUse.aborted &&
                !requestAborted
              ) {
                const phase = (data.data.phase as string) || 'processing';
                const elapsed = (data.data.elapsed as number) || 0;
                // Only show status for longer operations (after 20s)
                if (elapsed >= 20) {
                  onStep({ type: 'status', data: `⏳ Still ${phase}... (${elapsed}s)`, timestamp: new Date() });
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
                onStep({ type: 'thinking', data: data.data, timestamp: new Date() });
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
                    args: isRecord(data.data.args) ? data.data.args : {}
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
                onStep({ type: 'observation', data: data.data, timestamp: new Date() });
              }
            } else if (data.type === 'token') {
              const text =
                (typeof data.content === 'string' && data.content) ||
                (typeof data.data === 'string' && data.data) ||
                '';
              fullResponse += text;
              // Reset idle timeout on token (data arrival)
              resetIdleTimeout();
              // Only call callback if not aborted
              if (!signalToUse.aborted && !requestAborted) {
                // Clean accumulated response to remove ugly pollinations URLs
                const cleanedResponse = cleanImageResponse(fullResponse);
                onChunk(cleanedResponse);
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
            } else if (data.type === 'image') {
              // Handle generated images from image generation tool
              resetIdleTimeout();
              if (isRecord(data.data) && typeof data.data.url === 'string') {
                generatedImageUrl = data.data.url;
              }
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
          // Merge generated image into metadata if present
          const metadataWithImage = generatedImageUrl
            ? { ...finalMetadata, generated_image: generatedImageUrl }
            : finalMetadata;
          // Clean final response to remove ugly pollinations URLs
          const cleanedFinalResponse = cleanImageResponse(fullResponse);
          onDone(cleanedFinalResponse, sources, metadataWithImage);
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
