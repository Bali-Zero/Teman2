/**
 * Article Composer API Client
 * Handles manual article creation with Bali Zero style enrichment
 */

import { ApiClientBase } from "./client";

// Use the base API URL from environment or default
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";
const apiClient = new ApiClientBase(API_BASE_URL);

// --- Types ---

export interface ComposeRequest {
  title: string;
  content: string;
  category: string;
  source_url?: string;
  author: string;
}

export interface TLDRSection {
  should_worry: string;
  what: string;
  who: string;
  when: string;
  risk_level: string;
}

export interface BaliZeroTake {
  hidden_insight: string;
  our_analysis: string;
  our_advice: string;
}

export interface NextSteps {
  expat: string[];
  investor: string[];
}

export interface EnrichedArticle {
  title: string;
  headline: string;
  tldr: TLDRSection;
  facts: string;
  bali_zero_take: BaliZeroTake;
  next_steps: NextSteps;
  category: string;
  priority: string;
  relevance_score: number;
  ai_summary: string;
  ai_tags: string[];
  suggested_components: string[];
  cover_image: string | null;
  image_prompt: string | null;
  source: string;
  source_url: string | null;
  enriched_at: string;
}

export interface ComposeResponse {
  success: boolean;
  article: EnrichedArticle | null;
  error: string | null;
  api_cost_cents: number;
}

export interface ComposerStatus {
  configured: boolean;
  api_key_set: boolean;
  model: string;
  estimated_cost_per_article: string;
}

export interface PublishRequest {
  article: EnrichedArticle;
  cover_image_base64?: string;
  cover_image_filename?: string;
  position: "main_featured" | "secondary" | "normal";
  slug?: string;
}

export interface PublishResponse {
  success: boolean;
  message: string;
  article_url?: string;
  mdx_path?: string;
  image_path?: string;
  commit_sha?: string;
  error?: string;
}

export interface PublishStatus {
  configured: boolean;
  github_token_set: boolean;
  github_owner: string;
  github_repo: string;
  target_branch: string;
}

// --- API Functions ---

export const articlesApi = {
  /**
   * Compose/enrich an article with Bali Zero style
   */
  async compose(request: ComposeRequest): Promise<ComposeResponse> {
    const response = await apiClient.request<ComposeResponse>(
      "/api/articles/compose",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
      120000, // 2 minutes timeout for Claude API processing
    );
    return response;
  },

  /**
   * Check if article composer is configured
   */
  async getStatus(): Promise<ComposerStatus> {
    const response = await apiClient.request<ComposerStatus>(
      "/api/articles/compose/status",
      {
        method: "GET",
      },
    );
    return response;
  },

  /**
   * Publish an enriched article to the site
   */
  async publish(request: PublishRequest): Promise<PublishResponse> {
    const response = await apiClient.request<PublishResponse>(
      "/api/articles/publish",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
      120000, // 2 minutes timeout for GitHub commit and image upload
    );
    return response;
  },

  /**
   * Check if article publishing is configured
   */
  async getPublishStatus(): Promise<PublishStatus> {
    const response = await apiClient.request<PublishStatus>(
      "/api/articles/publish/status",
      {
        method: "GET",
      },
    );
    return response;
  },
};
