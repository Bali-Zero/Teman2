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

import { ApiClient } from "./api-client";
import type {
  ComplianceAlertItem,
  ComplianceAlertOutcome,
  ComplianceAlertPage,
  GateStatus,
  GateSection,
} from "./api-client";
import type { UserProfile } from "@/types";
import type { LoginResponse } from "./auth/auth.types";
import type {
  ConversationHistoryResponse,
  ConversationListItem,
  ConversationListResponse,
  SingleConversationResponse,
} from "./conversations/conversations.types";
import type {
  KnowledgeChunkMetadata,
  KnowledgeSearchResult,
  KnowledgeSearchResponse,
} from "./knowledge/knowledge.types";
import { TierLevel } from "./knowledge/knowledge.types";
import type {
  Practice,
  Interaction,
  PracticeStats,
  InteractionStats,
} from "./crm/crm.types";

// ApiError — the CLASS from ./error-handler, which is what the client actually
// throws. This used to be a separate structural interface declared right here
// with `detail`/`code` and no status field, so `catch` blocks that imported it
// could not branch on 401/403/404 and resorted to `error.message.includes("401")`
// — a substring test that also fires on "Practice 4012 not found". Read
// `statusCode` instead. Exported as a value too, so `instanceof ApiError` works.
export { ApiError } from "./error-handler";

// Export API client interface for type-safe dependency injection
export type { IApiClient, ApiRequestOptions } from "./types/api-client.types";

// In local dev, proxy `/api/*` through Next to avoid CORS and keep auth headers same-origin.

// In local dev, proxy `/api/*` through Next to avoid CORS and keep auth headers same-origin.
// Always use relative path so requests go to Next.js API routes first.
// This allows specific routes (like /api/crm/clients) to be intercepted by mocks,
// while others fall through to the [...path] proxy to reach the real backend.
const API_BASE_URL = "";

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
  GateStatus,
  GateSection,
  ComplianceAlertItem,
  ComplianceAlertOutcome,
  ComplianceAlertPage,
};

export { TierLevel };
