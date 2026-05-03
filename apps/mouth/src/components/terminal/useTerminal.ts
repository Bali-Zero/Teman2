/**
 * useTerminal — state machine + SSE streaming for the Zantara Terminal.
 *
 * Responsibilities:
 *  - Maintain the block timeline (user prompts + assistant responses).
 *  - Parse the gateway SSE stream (same format as WorkspaceAssistant).
 *  - Track tool calls, latency and token counts.
 *  - Persist command history to localStorage (last 50 entries).
 *  - Expose cancel (AbortController) + history navigation.
 *
 * Gateway contract (re-used from WorkspaceAssistant):
 *   data: {"type":"token","data":"..."}
 *   data: {"type":"tool_call","data":{"name":"..."}}
 *   data: {"type":"tool_result","data":{"name":"...","result":"..."}}
 *   data: [DONE]
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { sendChat } from "@/lib/gateway";
import {
  TERMINAL_HISTORY_KEY,
  TERMINAL_HISTORY_MAX,
  type BlockRole,
  type TerminalBlock,
  type ToolCall,
} from "./types";

// ── Utilities ─────────────────────────────────────────────────────────

const genId = (): string =>
  `tb_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

// Rough token estimate — 4 chars/token. Good enough for display purposes.
const estimateTokens = (text: string): number =>
  Math.max(1, Math.ceil(text.length / 4));

function loadHistory(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(TERMINAL_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === "string");
  } catch {
    return [];
  }
}

function saveHistory(history: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      TERMINAL_HISTORY_KEY,
      JSON.stringify(history.slice(-TERMINAL_HISTORY_MAX)),
    );
  } catch {
    // Quota exceeded — ignore.
  }
}

// ── Hook ──────────────────────────────────────────────────────────────

export interface UseTerminalOptions {
  sessionId: string;
  workspacePage?: string;
  initialHistory?: Array<{ role: BlockRole; content: string }>;
}

export interface UseTerminalReturn {
  blocks: TerminalBlock[];
  input: string;
  setInput: (value: string) => void;
  isStreaming: boolean;
  sendMessage: (text?: string) => Promise<void>;
  cancelStream: () => void;
  history: string[];
  historyIndex: number;
  navigateHistory: (direction: "up" | "down") => void;
  clearBlocks: () => void;
  seedFromHandoff: (msgs: Array<{ role: BlockRole; content: string }>) => void;
}

export function useTerminal(options: UseTerminalOptions): UseTerminalReturn {
  const { sessionId, workspacePage, initialHistory } = options;

  const [blocks, setBlocks] = useState<TerminalBlock[]>(() => {
    if (!initialHistory || initialHistory.length === 0) return [];
    return initialHistory.map((m) => ({
      id: genId(),
      role: m.role,
      content: m.content,
      toolCalls: [],
      timestamp: Date.now(),
      status: "complete" as const,
      tokenCount: estimateTokens(m.content),
    }));
  });
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [history, setHistoryState] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number>(-1);

  const abortRef = useRef<AbortController | null>(null);
  const draftInputRef = useRef<string>("");

  // Load history from localStorage on mount (client-only).
  useEffect(() => {
    setHistoryState(loadHistory());
  }, []);

  // ── Block helpers ─────────────────────────────────────────────────

  const updateLastAssistantBlock = useCallback(
    (patch: (block: TerminalBlock) => TerminalBlock) => {
      setBlocks((prev) => {
        if (prev.length === 0) return prev;
        const last = prev[prev.length - 1];
        if (!last || last.role !== "assistant") return prev;
        return [...prev.slice(0, -1), patch(last)];
      });
    },
    [],
  );

  // ── SSE parsing ───────────────────────────────────────────────────

  const parseSsePayload = useCallback(
    (payload: string, accRef: { current: string }, startTime: number) => {
      if (payload === "[DONE]") return;
      try {
        const parsed = JSON.parse(payload) as {
          type?: string;
          data?: unknown;
        };

        if (parsed.type === "token" && typeof parsed.data === "string") {
          accRef.current += parsed.data;
          const accumulated = accRef.current;
          updateLastAssistantBlock((block) => ({
            ...block,
            content: accumulated,
            status: "streaming",
            tokenCount: estimateTokens(accumulated),
          }));
          return;
        }

        if (parsed.type === "tool_call" && parsed.data && typeof parsed.data === "object") {
          const data = parsed.data as { name?: string; args?: Record<string, unknown> };
          if (!data.name) return;
          const newCall: ToolCall = {
            name: data.name,
            args: data.args,
            status: "running",
            startedAt: Date.now(),
          };
          updateLastAssistantBlock((block) => ({
            ...block,
            toolCalls: [...block.toolCalls, newCall],
          }));
          return;
        }

        if (parsed.type === "tool_result" && parsed.data && typeof parsed.data === "object") {
          const data = parsed.data as {
            name?: string;
            result?: unknown;
            error?: unknown;
          };
          updateLastAssistantBlock((block) => ({
            ...block,
            toolCalls: block.toolCalls.map((tc) => {
              if (tc.name !== data.name || tc.status !== "running") return tc;
              const duration = tc.startedAt ? Date.now() - tc.startedAt : undefined;
              return {
                ...tc,
                status: data.error ? "error" : "complete",
                result:
                  typeof data.result === "string"
                    ? data.result
                    : data.result !== undefined
                      ? JSON.stringify(data.result, null, 2)
                      : typeof data.error === "string"
                        ? data.error
                        : undefined,
                duration,
              };
            }),
          }));
          return;
        }

        if (parsed.type === "model" && typeof parsed.data === "string") {
          updateLastAssistantBlock((block) => ({
            ...block,
            model: parsed.data as string,
          }));
          return;
        }
      } catch {
        // Unparseable line — ignore.
      }
      // Suppress unused start-time warnings; retained for future telemetry.
      void startTime;
    },
    [updateLastAssistantBlock],
  );

  // ── Cancel ────────────────────────────────────────────────────────

  const cancelStream = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsStreaming(false);
    updateLastAssistantBlock((block) => ({
      ...block,
      status: "cancelled",
      content: block.content || "[cancelled]",
    }));
  }, [updateLastAssistantBlock]);

  // ── Send ──────────────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (override?: string) => {
      const text = (override ?? input).trim();
      if (!text || isStreaming) return;

      // Reset input + history cursor.
      setInput("");
      setHistoryIndex(-1);
      draftInputRef.current = "";

      // Persist to history (dedupe consecutive duplicates).
      setHistoryState((prev) => {
        const next =
          prev.length > 0 && prev[prev.length - 1] === text
            ? prev
            : [...prev, text].slice(-TERMINAL_HISTORY_MAX);
        saveHistory(next);
        return next;
      });

      const userBlock: TerminalBlock = {
        id: genId(),
        role: "user",
        content: text,
        toolCalls: [],
        timestamp: Date.now(),
        status: "complete",
        tokenCount: estimateTokens(text),
      };
      const assistantBlock: TerminalBlock = {
        id: genId(),
        role: "assistant",
        content: "",
        toolCalls: [],
        timestamp: Date.now(),
        status: "streaming",
      };

      // Capture current blocks for conversation history.
      let prevBlocks: TerminalBlock[] = [];
      setBlocks((prev) => {
        prevBlocks = prev;
        return [...prev, userBlock, assistantBlock];
      });
      setIsStreaming(true);

      const conversationHistory = prevBlocks
        .filter((b) => b.status === "complete" && b.content.trim().length > 0)
        .map((b) => ({ role: b.role as string, content: b.content }));

      const accRef = { current: "" };
      const startTime = Date.now();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await sendChat({
          query: text,
          session_id: sessionId,
          conversation_history: conversationHistory,
          workspace_page: workspacePage,
        });

        if (!res.ok || !res.body) {
          if (res.status === 401) {
            throw new Error(
              "Not authenticated. Please log in at https://kita.balizero.com/login or configure the local gateway token."
            );
          }
          if (res.status === 403) {
            throw new Error("Access denied. Your account is not a registered team member.");
          }
          if (res.status >= 500) {
            throw new Error(`Server error (${res.status}). Try again in a moment.`);
          }
          throw new Error(`Request failed with HTTP ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          if (controller.signal.aborted) {
            try {
              await reader.cancel();
            } catch {
              // ignore
            }
            break;
          }
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          // Split on newlines; keep trailing partial line in buffer.
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const payload = trimmed.slice(5).trim();
            if (!payload) continue;
            parseSsePayload(payload, accRef, startTime);
          }
        }

        // Drain any buffered tail after stream end.
        if (buffer.trim().startsWith("data:")) {
          const payload = buffer.trim().slice(5).trim();
          if (payload) parseSsePayload(payload, accRef, startTime);
        }

        if (!controller.signal.aborted) {
          const latencyMs = Date.now() - startTime;
          const finalContent = accRef.current || "[empty response]";
          updateLastAssistantBlock((block) => ({
            ...block,
            content: finalContent,
            status: "complete",
            latencyMs,
            tokenCount: estimateTokens(finalContent),
            toolCalls: block.toolCalls.map((tc) =>
              tc.status === "running"
                ? {
                    ...tc,
                    status: "complete",
                    duration: tc.startedAt ? Date.now() - tc.startedAt : undefined,
                  }
                : tc,
            ),
          }));
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          updateLastAssistantBlock((block) => ({
            ...block,
            content:
              block.content ||
              `[error] ${err instanceof Error ? err.message : String(err)}`,
            status: "error",
            latencyMs: Date.now() - startTime,
          }));
        }
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
        setIsStreaming(false);
      }
    },
    [
      input,
      isStreaming,
      sessionId,
      workspacePage,
      parseSsePayload,
      updateLastAssistantBlock,
    ],
  );

  // ── History navigation ───────────────────────────────────────────

  const navigateHistory = useCallback(
    (direction: "up" | "down") => {
      if (history.length === 0) return;
      setHistoryIndex((prevIdx) => {
        // Starting fresh — preserve current draft.
        if (prevIdx === -1 && direction === "up") {
          draftInputRef.current = input;
          const nextIdx = history.length - 1;
          setInput(history[nextIdx] ?? "");
          return nextIdx;
        }
        if (direction === "up") {
          const nextIdx = Math.max(0, prevIdx - 1);
          setInput(history[nextIdx] ?? "");
          return nextIdx;
        }
        // direction === "down"
        if (prevIdx === -1) return prevIdx;
        const nextIdx = prevIdx + 1;
        if (nextIdx >= history.length) {
          setInput(draftInputRef.current);
          return -1;
        }
        setInput(history[nextIdx] ?? "");
        return nextIdx;
      });
    },
    [history, input],
  );

  // ── Misc ─────────────────────────────────────────────────────────

  const clearBlocks = useCallback(() => {
    setBlocks([]);
  }, []);

  const seedFromHandoff = useCallback(
    (msgs: Array<{ role: BlockRole; content: string }>) => {
      if (!msgs || msgs.length === 0) return;
      setBlocks(
        msgs.map((m) => ({
          id: genId(),
          role: m.role,
          content: m.content,
          toolCalls: [],
          timestamp: Date.now(),
          status: "complete" as const,
          tokenCount: estimateTokens(m.content),
        })),
      );
    },
    [],
  );

  // Abort any in-flight request on unmount.
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
    };
  }, []);

  return {
    blocks,
    input,
    setInput,
    isStreaming,
    sendMessage,
    cancelStream,
    history,
    historyIndex,
    navigateHistory,
    clearBlocks,
    seedFromHandoff,
  };
}
