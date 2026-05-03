// apps/mouth/src/lib/gateway.ts
/**
 * Local Gateway Client — dual-path: localhost gateway first, cloud fallback.
 */

const GATEWAY_URL_KEY = "zantara_gateway_url";
const GATEWAY_TOKEN_KEY = "zantara_gateway_token";
const DEFAULT_GATEWAY_URL = "https://127.0.0.1:8090";

// SSE streams go DIRECTLY to Fly.io (not through Vercel proxy) because
// Vercel Hobby has a 60s timeout that kills long-running RAG responses.
// Auth is handled via Authorization header from localStorage.
import { getValidToken } from "@/lib/utils/token";

const CLOUD_BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "https://nuzantara-rag.fly.dev";

export function getGatewayUrl(): string {
  if (typeof window === "undefined") return DEFAULT_GATEWAY_URL;
  return localStorage.getItem(GATEWAY_URL_KEY) || DEFAULT_GATEWAY_URL;
}

export function getGatewayToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(GATEWAY_TOKEN_KEY) || "";
}

export function setGatewayToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(GATEWAY_TOKEN_KEY, token);
}

export function setGatewayUrl(url: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(GATEWAY_URL_KEY, url);
}

export function isGatewayConfigured(): boolean {
  return getGatewayToken() !== "";
}

export function clearGatewayConfig(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(GATEWAY_TOKEN_KEY);
  localStorage.removeItem(GATEWAY_URL_KEY);
}

interface ChatRequest {
  query: string;
  session_id: string;
  conversation_history: { role: string; content: string }[];
  workspace_page?: string;
}

export async function sendChat(req: ChatRequest): Promise<Response> {
  const gatewayUrl = getGatewayUrl();
  const token = getGatewayToken();

  if (token) {
    try {
      const res = await fetch(`${gatewayUrl}/v1/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Gateway-Token": token,
        },
        body: JSON.stringify({
          query: req.query,
          session_id: req.session_id,
          conversation_history: req.conversation_history,
        }),
      });
      if (res.ok) return res;
      console.warn(`[gateway] Local returned ${res.status}, falling back to cloud`);
    } catch {
      console.warn("[gateway] Local gateway unreachable, using cloud backend");
    }
  }

  // Read JWT from localStorage (same source as ApiClientBase) for Authorization header.
  // The httpOnly cookie alone is unreliable through Vercel Edge proxy.
  // Token expiry is validated before use to avoid sending stale tokens.
  const authHeaders: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const authToken = getValidToken("auth_token", localStorage);
    if (authToken) {
      authHeaders["Authorization"] = `Bearer ${authToken}`;
    }
  }

  return fetch(`${CLOUD_BACKEND}/api/agentic-rag/workspace-stream`, {
    method: "POST",
    headers: authHeaders,
    credentials: "include",
    body: JSON.stringify({
      query: req.query,
      session_id: req.session_id,
      enable_vision: false,
      conversation_history: req.conversation_history,
      workspace_page: req.workspace_page,
    }),
  });
}
