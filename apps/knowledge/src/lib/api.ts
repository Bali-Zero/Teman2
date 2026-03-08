/**
 * Slim API client for knowledge.balizero.com
 * Reads auth token from .balizero.com domain cookie
 * All API calls go to nuzantara-rag.fly.dev
 */

import type {
  KnowledgeSearchResponse,
  TierLevel,
} from "./api/knowledge/knowledge.types";
import { logger } from "./logger";

const BACKEND_URL = "https://nuzantara-rag.fly.dev";

function getAuthToken(): string | null {
  if (typeof document === "undefined") return null;
  const cookies = document.cookie.split(";");
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split("=");
    if (name === "auth_token" || name === "access_token" || name === "token") {
      return decodeURIComponent(value);
    }
  }
  // Also check localStorage as fallback
  try {
    return localStorage.getItem("auth_token") || localStorage.getItem("token");
  } catch {
    return null;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  timeoutMs = 30000,
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BACKEND_URL}${endpoint}`, {
      ...options,
      headers,
      signal: controller.signal,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } finally {
    clearTimeout(timeout);
  }
}

export class KnowledgeApi {
  async searchDocs(params: {
    query: string;
    level?: number;
    limit?: number;
    collection?: string | null;
    tier_filter?: TierLevel[] | null;
  }): Promise<KnowledgeSearchResponse> {
    const {
      query,
      level = 1,
      limit = 8,
      collection = null,
      tier_filter,
    } = params;

    return request<KnowledgeSearchResponse>("/api/search/", {
      method: "POST",
      body: JSON.stringify({
        query,
        level: Math.min(3, Math.max(0, level)),
        limit: Math.max(1, Math.min(50, limit)),
        collection,
        tier_filter: tier_filter ?? null,
      }),
    });
  }
}

export type KBActionType = "view" | "download";

interface KBActivityPayload {
  action_type: KBActionType;
  resource_type: string;
  resource_id?: string;
  resource_title?: string;
  resource_category?: string;
}

export class KnowledgeActivityApi {
  async logActivity(payload: KBActivityPayload): Promise<void> {
    try {
      await request("/api/knowledge/activity/log", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    } catch (error) {
      logger.debug("KB activity log failed (non-critical)", {
        action: "logActivity",
      });
    }
  }

  logView(
    resourceType: string,
    resourceId?: string,
    resourceTitle?: string,
    resourceCategory?: string,
  ): void {
    this.logActivity({
      action_type: "view",
      resource_type: resourceType,
      resource_id: resourceId,
      resource_title: resourceTitle,
      resource_category: resourceCategory,
    });
  }

  logDownload(
    resourceType: string,
    resourceId?: string,
    resourceTitle?: string,
    resourceCategory?: string,
  ): void {
    this.logActivity({
      action_type: "download",
      resource_type: resourceType,
      resource_id: resourceId,
      resource_title: resourceTitle,
      resource_category: resourceCategory,
    });
  }
}

export const knowledgeApi = new KnowledgeApi();
export const kbActivityApi = new KnowledgeActivityApi();

const api = {
  knowledge: knowledgeApi,
  kbActivity: kbActivityApi,

  async get<T>(endpoint: string): Promise<T> {
    return request<T>(endpoint, { method: "GET" });
  },

  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return request<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  },
};

export default api;
