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
import type { KnowledgeChunkMetadata, KnowledgeSearchResult, KnowledgeSearchResponse } from './knowledge/knowledge.types';
import { TierLevel } from './knowledge/knowledge.types';
import type { Practice, Interaction, PracticeStats, InteractionStats } from './crm/crm.types';

// Re-export ApiError type
export interface ApiError extends Error {
  detail?: string;
  code?: string;
  message: string;
}

// In local dev, proxy `/api/*` through Next to avoid CORS and keep auth headers same-origin.

// In local dev, proxy `/api/*` through Next to avoid CORS and keep auth headers same-origin.
// Always use relative path so requests go to Next.js API routes first.
// This allows specific routes (like /api/crm/clients) to be intercepted by mocks,
// while others fall through to the [...path] proxy to reach the real backend.
const API_BASE_URL = '';

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
