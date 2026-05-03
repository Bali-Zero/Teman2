/**
 * Dream Room API Client
 * Handles state persistence, AI generation, and tools.
 */

import { ApiClientBase } from "./client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";
const apiClient = new ApiClientBase(API_BASE_URL);

// --- Types ---

export interface ArticleVersion {
  id: number;
  timestamp: string;
  content: string;
}

export interface Article {
  id: number;
  title: string;
  content: string;
  outline: string[];
  wordCount: number;
  seoScore: number;
  createdAt: string;
  versions: ArticleVersion[];
}

export interface Inspiration {
  id: number;
  type: "color" | "quote" | "prompt";
  value?: string;
  name?: string;
  source?: string;
  content?: string;
  author?: string;
}

export interface DreamState {
  articles: Article[];
  inspirations: Inspiration[];
  activeZone: string;
  // Add other state properties
}

export interface GenerateRequest {
  prompt: string;
  context?: string;
  mode: "expand" | "rewrite" | "shorten" | "tone-shift";
}

export interface GenerateResponse {
  text: string;
  success: boolean;
}

export interface ScrapeRequest {
  url: string;
}

export interface ScrapeResponse {
  title: string;
  keyPoints: string[];
  quotes: { text: string; author: string }[];
  success: boolean;
}

// --- API Functions ---

export const dreamApi = {
  /**
   * Persist Dream Room state
   */
  async saveState(
    userId: string,
    state: DreamState,
  ): Promise<{ success: boolean; timestamp: string }> {
    return apiClient.request("/api/dream/state", {
      method: "POST",
      // Mock user_id logic if auth not fully integrated in this view yet
      body: JSON.stringify({ state }),
      // Query param for user_id to match backend expectation for now,
      // or backend should take it from token.
      // For this implementation, I'll pass it in URL or body.
      // Let's assume body wrapper.
    });
  },

  /**
   * Load Dream Room state
   */
  async loadState(
    userId: string,
  ): Promise<{ success: boolean; state: DreamState }> {
    return apiClient.request(`/api/dream/state/${userId}`, {
      method: "GET",
    });
  },

  /**
   * Generate content with AI
   */
  async generate(request: GenerateRequest): Promise<GenerateResponse> {
    return apiClient.request<GenerateResponse>(
      "/api/dream/ai/generate",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
      60000, // 60s timeout
    );
  },

  /**
   * Scrape URL
   */
  async scrape(url: string): Promise<ScrapeResponse> {
    return apiClient.request<ScrapeResponse>(
      "/api/dream/scrape",
      {
        method: "POST",
        body: JSON.stringify({ url }),
      },
      30000, // 30s timeout
    );
  },
};
