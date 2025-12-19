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
import type { KnowledgeChunkMetadata, KnowledgeSearchResult, KnowledgeSearchResponse, TierLevel } from './knowledge/knowledge.types';

// Re-export ApiError type
export interface ApiError extends Error {
  detail?: string;
  code?: string;
  message: string;
}

// Normalize API base URL
function normalizeApiBaseUrl(url: string): string {
  // Accept either https://host or https://host/api and normalize to https://host
  return url.replace(/\/+$/, '').replace(/\/api$/, '');
}

const ENV_API_BASE_URL = normalizeApiBaseUrl(
  process.env.NEXT_PUBLIC_API_URL || 'https://nuzantara-rag.fly.dev'
);

// In local dev, proxy `/api/*` through Next to avoid CORS and keep auth headers same-origin.
const API_BASE_URL =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname.endsWith('.local'))
    ? ''
    : ENV_API_BASE_URL;

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
  TierLevel,
};

