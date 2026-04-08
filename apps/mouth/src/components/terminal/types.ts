/**
 * Zantara Terminal — Shared TypeScript types.
 *
 * A TerminalBlock models a single user prompt or assistant response rendered
 * as a card in the terminal timeline. Blocks stream in-place during assistant
 * generation and carry tool-call metadata, latency and status.
 */

export type BlockStatus = "streaming" | "complete" | "error" | "cancelled";
export type BlockRole = "user" | "assistant";

export type ToolCallStatus = "running" | "complete" | "error";

export interface ToolCall {
  /** Tool identifier, e.g. `search_kbli` or `get_client`. */
  name: string;
  /** Optional argument map parsed from the SSE payload. */
  args?: Record<string, unknown>;
  /** Optional stringified result once the tool finishes. */
  result?: string;
  /** Wall-clock duration in milliseconds (filled at completion). */
  duration?: number;
  /** Lifecycle status of the tool call. */
  status: ToolCallStatus;
  /** Timestamp (ms) at which the tool started — used to compute duration. */
  startedAt?: number;
}

export interface TerminalBlock {
  id: string;
  role: BlockRole;
  content: string;
  toolCalls: ToolCall[];
  timestamp: number;
  /** Model identifier reported by the backend (e.g. "gemini-3-flash"). */
  model?: string;
  /** End-to-end latency in ms, filled on completion. */
  latencyMs?: number;
  /** Approximate token count for the block. */
  tokenCount?: number;
  status: BlockStatus;
}

/**
 * Payload persisted to localStorage when the widget hands off an active
 * conversation to the full terminal. Consumed once on terminal mount.
 */
export interface TerminalHandoff {
  history: Array<{ role: BlockRole; content: string }>;
  createdAt: number;
}

export const TERMINAL_HANDOFF_KEY = "zantara_terminal_handoff";
export const TERMINAL_HISTORY_KEY = "zantara_terminal_history";
export const TERMINAL_HISTORY_MAX = 50;
