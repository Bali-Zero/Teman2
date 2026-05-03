"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

// Article type definition
interface Article {
  id: number;
  title: string;
  content: string;
  summary?: string;
  source: string;
  status: "draft" | "published" | "archived";
  created_at: string;
  updated_at: string;
  published_at?: string;
  author?: string;
  tags?: string[];
  url?: string;
  image_url?: string;
}

// API response type
interface ApiResponse<T> {
  data?: T;
  error?: string;
}

// Query keys for articles
export const articleKeys = {
  all: ["articles"] as const,
  lists: () => [...articleKeys.all, "list"] as const,
  list: (filters: ArticleFilters) => [...articleKeys.lists(), filters] as const,
  details: () => [...articleKeys.all, "detail"] as const,
  detail: (id: number) => [...articleKeys.details(), id] as const,
  feeds: () => [...articleKeys.all, "feed"] as const,
  feed: (type: string) => [...articleKeys.feeds(), type] as const,
};

interface ArticleFilters {
  status?: string;
  source?: string;
  search?: string;
  from_date?: string;
  to_date?: string;
  page?: number;
  limit?: number;
}

interface PaginatedArticles {
  items: Article[];
  total: number;
  page: number;
  pages: number;
}

// Mock fetch - replace with actual API client
const fetchApi = async <T>(
  url: string,
  options?: RequestInit,
): Promise<ApiResponse<T>> => {
  try {
    const response = await fetch(url, options);
    if (!response.ok) {
      return { error: `HTTP ${response.status}` };
    }
    const data = (await response.json()) as T;
    return { data };
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Unknown error" };
  }
};

/**
 * Hook for fetching articles with filtering and pagination
 * Optimized for news feed with infinite scroll support
 */
export function useArticlesQuery(filters: ArticleFilters = {}) {
  return useQuery({
    queryKey: articleKeys.list(filters),
    queryFn: async () => {
      const queryString = new URLSearchParams(
        filters as Record<string, string>,
      ).toString();
      const response = await fetchApi<PaginatedArticles>(
        `/api/articles?${queryString}`,
      );
      return response.data ?? { items: [], total: 0, page: 1, pages: 1 };
    },
    placeholderData: (previousData) => previousData,
  });
}

/**
 * Hook for fetching a single article
 */
export function useArticleQuery(id: number) {
  return useQuery({
    queryKey: articleKeys.detail(id),
    queryFn: async () => {
      const response = await fetchApi<Article>(`/api/articles/${id}`);
      return response.data ?? null;
    },
    enabled: !!id,
  });
}

/**
 * Hook for intelligence/news feed
 * Specialized for real-time news updates
 */
export function useNewsFeedQuery(
  type: "latest" | "trending" | "verified" = "latest",
) {
  return useQuery({
    queryKey: articleKeys.feed(type),
    queryFn: async () => {
      const response = await fetchApi<Article[]>(
        `/api/intelligence/feed?type=${type}`,
      );
      return response.data ?? [];
    },
    // News gets stale quickly - refetch every minute
    staleTime: 1000 * 60 * 1, // 1 minute
    // Refetch automatically in background
    refetchInterval: 1000 * 60 * 2, // 2 minutes
  });
}

/**
 * Hook for creating/updating articles
 */
export function useArticleMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (article: Partial<Article>) => {
      const method = article.id ? "PUT" : "POST";
      const url = article.id ? `/api/articles/${article.id}` : "/api/articles";

      const response = await fetchApi<Article>(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(article),
      });

      if (!response.data)
        throw new Error(response.error || "Failed to save article");
      return response.data;
    },
    onSuccess: (data) => {
      // Invalidate all article lists
      queryClient.invalidateQueries({ queryKey: articleKeys.lists() });
      // Update or add the specific article
      queryClient.setQueryData(articleKeys.detail(data.id), data);
    },
  });
}

/**
 * Hook for publishing articles
 * Optimistic update for immediate status change
 */
export function usePublishArticleMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, publish }: { id: number; publish: boolean }) => {
      const response = await fetchApi<Article>(`/api/articles/${id}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ publish }),
      });

      if (!response.data)
        throw new Error(response.error || "Failed to publish article");
      return response.data;
    },
    // Optimistic update
    onMutate: async ({ id, publish }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: articleKeys.detail(id) });

      // Snapshot previous value
      const previousArticle = queryClient.getQueryData<Article>(
        articleKeys.detail(id),
      );

      // Optimistically update
      if (previousArticle) {
        queryClient.setQueryData(articleKeys.detail(id), {
          ...previousArticle,
          status: publish ? "published" : "draft",
          published_at: publish ? new Date().toISOString() : undefined,
        });
      }

      return { previousArticle };
    },
    // Rollback on error
    onError: (err, variables, context) => {
      if (context?.previousArticle) {
        queryClient.setQueryData(
          articleKeys.detail(variables.id),
          context.previousArticle,
        );
      }
    },
    // Always refetch after error or success
    onSettled: (data, error, variables) => {
      queryClient.invalidateQueries({
        queryKey: articleKeys.detail(variables.id),
      });
      queryClient.invalidateQueries({ queryKey: articleKeys.lists() });
    },
  });
}

/**
 * Prefetch articles for instant navigation
 */
export function usePrefetchArticles() {
  const queryClient = useQueryClient();

  return (filters?: ArticleFilters) => {
    queryClient.prefetchQuery({
      queryKey: articleKeys.list(filters || {}),
      queryFn: async () => {
        const queryString = new URLSearchParams(
          filters as Record<string, string>,
        ).toString();
        const response = await fetchApi<PaginatedArticles>(
          `/api/articles?${queryString}`,
        );
        return response.data ?? { items: [], total: 0, page: 1, pages: 1 };
      },
      staleTime: 1000 * 60 * 1, // 1 minute
    });
  };
}
