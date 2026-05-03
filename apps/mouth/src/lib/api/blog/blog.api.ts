/**
 * Blog API Client
 * Handles blog article listing, detail fetching, and pending news count.
 */

import type { IApiClient } from "../types/api-client.types";

// --- Types ---

export interface BlogArticleSummary {
  slug: string;
  title: string;
  category: string;
  publishedAt: string;
  excerpt?: string;
  cover_image?: string;
}

export interface BlogArticlesResponse {
  articles: BlogArticleSummary[];
  total?: number;
}

export interface BlogArticleDetail {
  slug: string;
  title: string;
  category: string;
  content: string;
  publishedAt: string;
  excerpt?: string;
  cover_image?: string;
  author?: string;
  relatedArticles?: BlogArticleSummary[];
  [key: string]: unknown;
}

export interface PendingNewsResponse {
  success: boolean;
  data?: Array<{ id: number; title: string; [key: string]: unknown }>;
}

// --- API Class ---

export class BlogApi {
  constructor(private client: IApiClient) {}

  /**
   * List blog articles with pagination.
   */
  async listArticles(
    limit: number = 8,
    offset: number = 0,
  ): Promise<BlogArticlesResponse> {
    return this.client.request<BlogArticlesResponse>(
      `/api/blog/articles?limit=${limit}&offset=${offset}`,
    );
  }

  /**
   * Get a single article by category and slug.
   * Returns a generic record -- the consumer should cast to its own Article type
   * since article schemas vary by context (MDX, SSR, client).
   */
  async getArticle<T = BlogArticleDetail>(
    category: string,
    slug: string,
  ): Promise<T> {
    return this.client.request<T>(
      `/api/blog/articles/${encodeURIComponent(category)}/${encodeURIComponent(slug)}`,
    );
  }

  /**
   * Get pending news count (admin only).
   */
  async getPendingNews(): Promise<PendingNewsResponse> {
    return this.client.request<PendingNewsResponse>(
      "/api/news?status=pending",
    );
  }
}
