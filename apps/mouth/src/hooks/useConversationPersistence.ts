/**
 * Conversation Persistence Hook
 * Manages session_id generation and persistence across page refreshes
 */

import { useEffect, useState } from "react";
import { logger } from "@/lib/logger";

const SESSION_STORAGE_KEY = "zantara_session_id";
const SESSION_EXPIRY_KEY = "zantara_session_expiry";
const SESSION_DURATION_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Generate a unique session ID
 */
function generateSessionId(): string {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 15);
  return `session-${timestamp}-${random}`;
}

/**
 * Check if session is expired
 */
function isSessionExpired(expiryTime: string | null): boolean {
  if (!expiryTime) return true;
  return Date.now() > parseInt(expiryTime, 10);
}

/**
 * Hook for managing conversation session persistence
 *
 * Features:
 * - Generates session_id once per session
 * - Persists session_id in sessionStorage
 * - Auto-expires after 24 hours
 * - Provides manual reset function
 *
 * @returns Session ID and reset function
 */
export function useConversationPersistence() {
  const [sessionId, setSessionId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Client-side only
    if (typeof window === "undefined") return;

    try {
      const storedSessionId = sessionStorage.getItem(SESSION_STORAGE_KEY);
      const storedExpiry = sessionStorage.getItem(SESSION_EXPIRY_KEY);

      // Check if we have a valid session
      if (storedSessionId && !isSessionExpired(storedExpiry)) {
        setSessionId(storedSessionId);
        logger.info("Restored session", {
          component: "useConversationPersistence",
          action: "restore",
          metadata: { session_id: storedSessionId },
        });
      } else {
        // Generate new session
        const newSessionId = generateSessionId();
        const newExpiry = (Date.now() + SESSION_DURATION_MS).toString();

        sessionStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
        sessionStorage.setItem(SESSION_EXPIRY_KEY, newExpiry);

        setSessionId(newSessionId);
        logger.info("Created new session", {
          component: "useConversationPersistence",
          action: "create",
          metadata: { session_id: newSessionId },
        });
      }
    } catch (error) {
      // Fallback if sessionStorage is unavailable
      const fallbackSessionId = generateSessionId();
      setSessionId(fallbackSessionId);
      logger.warn("SessionStorage unavailable, using fallback", {
        component: "useConversationPersistence",
        action: "fallback",
        metadata: { session_id: fallbackSessionId },
      });
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Reset session (start new conversation)
   */
  const resetSession = () => {
    const newSessionId = generateSessionId();
    const newExpiry = (Date.now() + SESSION_DURATION_MS).toString();

    try {
      sessionStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
      sessionStorage.setItem(SESSION_EXPIRY_KEY, newExpiry);
    } catch {
      // Ignore storage errors
    }

    setSessionId(newSessionId);
    logger.info("Reset session", {
      component: "useConversationPersistence",
      action: "reset",
      metadata: { session_id: newSessionId },
    });
  };

  return {
    sessionId,
    setSessionId, // Export the setter
    isLoading,
    resetSession,
  };
}
