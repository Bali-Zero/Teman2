"use server";

import { cookies } from "next/headers";
import type { Source } from "@/types";

// Types
export interface ChatImage {
  id: string;
  base64: string;
  name: string;
  size: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  images?: ChatImage[];
  sources?: Source[];
  steps?: AgentStep[];
  timestamp: Date;
  metadata?: MessageMetadata;
  imageUrl?: string; // Generated image URL from image generation tool
}

// Re-export Source from canonical types to avoid duplicate definitions
export type { Source } from "@/types";

export interface AgentStep {
  type: "status" | "tool_start" | "tool_end" | "phase" | "reasoning_step";
  data: unknown;
  timestamp: Date;
}

export interface MessageMetadata {
  execution_time?: number;
  route_used?: string;
  context_length?: number;
  followup_questions?: string[];
}

/**
 * Stream event types for useOptimisticChat hook
 */
export type StreamEvent =
  | { type: "token"; data: string }
  | { type: "status"; data: string }
  | { type: "sources"; data: Source[] }
  | { type: "error"; data: string }
  | { type: "done" };

// Backend API URL
const BACKEND_URL =
  process.env.BACKEND_RAG_URL || "https://nuzantara-rag.fly.dev";

/**
 * Server Action: Get auth token from cookies
 */
async function getAuthToken(): Promise<string | null> {
  const cookieStore = await cookies();
  return cookieStore.get("nz_access_token")?.value || null;
}

/**
 * Server Action: Save conversation to backend
 */
export async function saveConversation(
  messages: ChatMessage[],
  sessionId: string,
): Promise<{ success: boolean; conversationId?: number }> {
  const token = await getAuthToken();

  if (!token) {
    return { success: false };
  }

  try {
    const response = await fetch(
      `${BACKEND_URL}/api/bali-zero/conversations/save`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          messages: messages.map((m) => ({
            role: m.role,
            content: m.content,
            sources: m.sources,
            timestamp: m.timestamp.toISOString(),
          })),
        }),
      },
    );

    if (!response.ok) {
      throw new Error("Failed to save");
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
    return { conversations: [], error: "Not authenticated" };
  }

  try {
    const response = await fetch(
      `${BACKEND_URL}/api/bali-zero/conversations/list`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        next: { revalidate: 60 }, // Cache for 60 seconds
      },
    );

    if (!response.ok) {
      throw new Error("Failed to load");
    }

    const data = await response.json();
    return { conversations: data.conversations || [] };
  } catch {
    return { conversations: [], error: "Failed to load conversations" };
  }
}

/**
 * Server Action: Delete conversation
 */
export async function deleteConversation(
  id: number,
): Promise<{ success: boolean }> {
  const token = await getAuthToken();

  if (!token) {
    return { success: false };
  }

  try {
    const response = await fetch(
      `${BACKEND_URL}/api/bali-zero/conversations/${id}`,
      {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    return { success: response.ok };
  } catch {
    return { success: false };
  }
}

/**
 * Server Action: Toggle clock in/out
 */
export async function toggleClockStatus(
  currentStatus: boolean,
): Promise<{ isClockIn: boolean; error?: string }> {
  const token = await getAuthToken();

  if (!token) {
    return { isClockIn: currentStatus, error: "Not authenticated" };
  }

  try {
    const endpoint = currentStatus ? "clock-out" : "clock-in";
    const response = await fetch(
      `${BACKEND_URL}/api/bali-zero/team/${endpoint}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      },
    );

    if (!response.ok) {
      throw new Error("Clock toggle failed");
    }

    return { isClockIn: !currentStatus };
  } catch {
    return { isClockIn: currentStatus, error: "Failed to toggle clock" };
  }
}
