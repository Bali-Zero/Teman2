// apps/mouth/src/lib/gateway.ts
/**
 * Local Gateway Client — dual-path: localhost gateway first, cloud fallback.
 */

const GATEWAY_URL_KEY = "zantara_gateway_url";
const GATEWAY_TOKEN_KEY = "zantara_gateway_token";
const DEFAULT_GATEWAY_URL = "https://127.0.0.1:8090";

// Cloud requests go through the Next.js API proxy (/api/[...path]) so httpOnly
// cookies are forwarded to the backend automatically (same-origin request).
const CLOUD_BACKEND = "";

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
  const authHeaders: Record<string, string> = { "Content-Type": "application/json" };
  if (typeof window !== "undefined") {
    const authToken = localStorage.getItem("auth_token");
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
