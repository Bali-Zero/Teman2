'use server';

import { cookies } from 'next/headers';

// Types
export interface ChatImage {
  id: string;
  base64: string;
  name: string;
  size: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  images?: ChatImage[];
  sources?: Source[];
  steps?: AgentStep[];
  timestamp: Date;
  metadata?: MessageMetadata;
  imageUrl?: string; // Generated image URL from image generation tool
}

export interface Source {
  title: string;
  url?: string;
  content?: string;
  score?: number;
}

export interface AgentStep {
  type: 'status' | 'tool_start' | 'tool_end' | 'phase' | 'reasoning_step';
  data: unknown;
  timestamp: Date;
}

export interface MessageMetadata {
  execution_time?: number;
  route_used?: string;
  context_length?: number;
  followup_questions?: string[];
}

export interface StreamEvent {
  type: 'token' | 'status' | 'sources' | 'phase' | 'error' | 'done';
  data: string | Source[] | null;
}

// Backend API URL
const BACKEND_URL = process.env.BACKEND_RAG_URL || 'https://nuzantara-rag.fly.dev';

/**
 * Clean image generation response to remove ugly pollinations URLs
 * NOTE: This is duplicated in chat.api.ts for client-side use.
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
 * Server Action: Get auth token from cookies
 */
async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get('nz_access_token')?.value || null;
}

/**
 * Server Action: Send message and return async iterator for streaming
 * Uses native Web Streams for Next.js 15 compatibility
 */
export async function sendMessageStream(
  messages: ChatMessage[],
  sessionId: string,
  userId: string
): Promise<ReadableStream<StreamEvent>> {
  const token = await getAuthToken();

  if (!token) {
    return new ReadableStream({
      start(controller) {
        controller.enqueue({ type: 'error', data: 'Not authenticated' });
        controller.close();
      },
    });
  }

  const lastUserMessage = messages.filter(m => m.role === 'user').pop();
  if (!lastUserMessage) {
    return new ReadableStream({
      start(controller) {
        controller.enqueue({ type: 'error', data: 'No user message' });
        controller.close();
      },
    });
  }

  // Create a ReadableStream that fetches and processes SSE in the pull() function
  return new ReadableStream<StreamEvent>({
    async start(controller) {
      const decoder = new TextDecoder();

      try {
        const response = await fetch(`${BACKEND_URL}/api/agentic-rag/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            query: lastUserMessage.content,
            user_id: userId,
            session_id: sessionId,
            images: lastUserMessage.images?.map(img => ({
              base64: img.base64,
              name: img.name,
            })),
            enable_vision: (lastUserMessage.images?.length ?? 0) > 0,
            conversation_history: messages.slice(-200).map(m => ({
              role: m.role,
              content: m.content,
            })),
          }),
        });

        if (!response.ok) {
          controller.enqueue({ type: 'error', data: `Backend error: ${response.status}` });
          controller.close();
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          controller.enqueue({ type: 'error', data: 'No response body' });
          controller.close();
          return;
        }

        let buffer = '';
        let fullContent = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);

            if (data === '[DONE]') {
              controller.enqueue({ type: 'done', data: null });
              controller.close();
              return;
            }

            try {
              const event = JSON.parse(data);

              switch (event.type) {
                case 'token': {
                  fullContent += event.data;
                  // Clean image generation URLs from accumulated content
                  const cleanedContent = cleanImageResponse(fullContent);
                  controller.enqueue({ type: 'token', data: cleanedContent });
                  break;
                }

                case 'status':
                case 'phase':
                  controller.enqueue({
                    type: 'status',
                    data: event.data?.message || event.data,
                  });
                  break;

                case 'sources':
                  controller.enqueue({ type: 'sources', data: event.data });
                  break;

                case 'error':
                  controller.enqueue({
                    type: 'error',
                    data: event.data?.message || 'Unknown error',
                  });
                  controller.close();
                  return;
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }

        controller.enqueue({ type: 'done', data: null });
        controller.close();
      } catch (error) {
        controller.enqueue({
          type: 'error',
          data: error instanceof Error ? error.message : 'Stream failed',
        });
        controller.close();
      }
    },
  });
}

/**
 * Server Action: Save conversation to backend
 */
export async function saveConversation(
  messages: ChatMessage[],
  sessionId: string
): Promise<{ success: boolean; conversationId?: number }> {
  const token = await getAuthToken();

  if (!token) {
    return { success: false };
  }

  try {
    const response = await fetch(`${BACKEND_URL}/api/bali-zero/conversations/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        session_id: sessionId,
        messages: messages.map(m => ({
          role: m.role,
          content: m.content,
          sources: m.sources,
          timestamp: m.timestamp.toISOString(),
        })),
      }),
    });

    if (!response.ok) {
      throw new Error('Failed to save');
    }

    const data = await response.json();
    return { success: true, conversationId: data.conversation_id };
  } catch {
    return { success: false };
  }
}

/**
 * Server Action: Load conversations list
 */
export async function loadConversations(): Promise<{
  conversations: Array<{ id: number; title: string; updated_at: string }>;
  error?: string;
}> {
  const token = await getAuthToken();

  if (!token) {
    return { conversations: [], error: 'Not authenticated' };
  }

  try {
    const response = await fetch(`${BACKEND_URL}/api/bali-zero/conversations/list`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      next: { revalidate: 60 }, // Cache for 60 seconds
    });

    if (!response.ok) {
      throw new Error('Failed to load');
    }

    const data = await response.json();
    return { conversations: data.conversations || [] };
  } catch {
    return { conversations: [], error: 'Failed to load conversations' };
  }
}

/**
 * Server Action: Delete conversation
 */
export async function deleteConversation(id: number): Promise<{ success: boolean }> {
  const token = await getAuthToken();

  if (!token) {
    return { success: false };
  }

  try {
    const response = await fetch(`${BACKEND_URL}/api/bali-zero/conversations/${id}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    return { success: response.ok };
  } catch {
    return { success: false };
  }
}

/**
 * Server Action: Toggle clock in/out
 */
export async function toggleClockStatus(
  currentStatus: boolean
): Promise<{ isClockIn: boolean; error?: string }> {
  const token = await getAuthToken();

  if (!token) {
    return { isClockIn: currentStatus, error: 'Not authenticated' };
  }

  try {
    const endpoint = currentStatus ? 'clock-out' : 'clock-in';
    const response = await fetch(`${BACKEND_URL}/api/bali-zero/team/${endpoint}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      throw new Error('Clock toggle failed');
    }

    return { isClockIn: !currentStatus };
  } catch {
    return { isClockIn: currentStatus, error: 'Failed to toggle clock' };
  }
}
