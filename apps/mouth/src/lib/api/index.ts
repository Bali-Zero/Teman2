/**
 * API Client Module - Refactored for maintainability
 *
 * This module maintains backward compatibility with the original api.ts file.
 * All exports remain identical to ensure zero breaking changes.
 *
 * Internal structure:
 * - client.ts: Base API client with token management
 * - api-client.ts: Unified client that composes domain-specific APIs
 * - auth/, chat/, knowledge/, conversations/, team/, admin/, media/, websocket/: Domain-specific modules
 */

import { ApiClient } from './api-client';
import type { UserProfile } from '@/types';
import type { LoginResponse } from './auth/auth.types';
import type {
  ConversationHistoryResponse,
  ConversationListItem,
  ConversationListResponse,
  SingleConversationResponse,
} from './conversations/conversations.types';
import type {
  KnowledgeChunkMetadata,
  KnowledgeSearchResult,
  KnowledgeSearchResponse,
} from './knowledge/knowledge.types';
import { TierLevel } from './knowledge/knowledge.types';
import type { Practice, Interaction, PracticeStats, InteractionStats } from './crm/crm.types';

// Re-export ApiError type
export interface ApiError extends Error {
  detail?: string;
  code?: string;
  message: string;
}

// Export API client interface for type-safe dependency injection
export type { IApiClient, ApiRequestOptions } from './types/api-client.types';

// In local dev, proxy `/api/*` through Next to avoid CORS and keep auth headers same-origin.

// Use direct backend URL in production to avoid proxy issues, fallback to relative in dev
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://nuzantara-rag.fly.dev';

// Create and export the API client instance (backward compatible)
export const api = new ApiClient(API_BASE_URL);

// Re-export all types for backward compatibility
export type {
  LoginResponse,
  UserProfile,
  ConversationHistoryResponse,
  ConversationListItem,
  ConversationListResponse,
  SingleConversationResponse,
  KnowledgeChunkMetadata,
  KnowledgeSearchResult,
  KnowledgeSearchResponse,
  Practice,
  Interaction,
  PracticeStats,
  InteractionStats,
};

export { TierLevel };
