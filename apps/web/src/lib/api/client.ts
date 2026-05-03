/**
 * API client for the V6 graph-engine.
 *
 * Supports both synchronous query and SSE streaming.
 */

import type {
  QueryRequest,
  QueryResponse,
  StreamNodeEvent,
} from "@nuzantara/ts-schemas";
import { parseSSEStream } from "./sse";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export class GraphClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = API_URL) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string) {
    this.token = token;
  }

  private headers(): HeadersInit {
    const h: HeadersInit = { "Content-Type": "application/json" };
    if (this.token) {
      h["Authorization"] = `Bearer ${this.token}`;
    }
    return h;
  }

  /** Synchronous query — waits for full result. */
  async query(req: QueryRequest): Promise<QueryResponse> {
    const resp = await fetch(`${this.baseUrl}/api/query`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(req),
    });

    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(`Query failed (${resp.status}): ${detail}`);
    }

    return resp.json();
  }

  /**
   * Streaming query — returns an async iterable of node events.
   *
   * Uses POST /api/query/stream with SSE response.
   */
  async *queryStream(
    req: QueryRequest,
    signal?: AbortSignal,
  ): AsyncGenerator<StreamNodeEvent> {
    const resp = await fetch(`${this.baseUrl}/api/query/stream`, {
      method: "POST",
      headers: this.headers(),
      body: JSON.stringify(req),
      signal,
    });

    if (!resp.ok) {
      const detail = await resp.text();
      throw new Error(`Stream failed (${resp.status}): ${detail}`);
    }

    if (!resp.body) {
      throw new Error("Response body is null — streaming not supported");
    }

    yield* parseSSEStream(resp.body);
  }

  /** Clear conversation history for a session (new chat). */
  async clearSession(sessionId: string): Promise<void> {
    await fetch(
      `${this.baseUrl}/api/session/${encodeURIComponent(sessionId)}`,
      {
        method: "DELETE",
        headers: this.headers(),
      },
    );
  }

  /** Health check. */
  async health(): Promise<Record<string, unknown>> {
    const resp = await fetch(`${this.baseUrl}/health`);
    return resp.json();
  }
}

/** Default client instance. */
export const graphClient = new GraphClient();
