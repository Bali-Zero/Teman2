/**
 * NUZANTARA Frontend Configuration Constants
 *
 * Centralized magic numbers and configuration values.
 * Organized by category for easy maintenance.
 */

// ============================================================================
// TIMEOUTS & DELAYS (milliseconds)
// ============================================================================

export const TIMEOUTS = {
  /** Toast notification auto-dismiss */
  TOAST_AUTO_DISMISS: 3000,

  /** Copy button feedback display */
  COPY_FEEDBACK: 2000,

  /** Reload delay after agent execution */
  AGENT_RELOAD_DELAY: 2000,

  /** Default API request timeout */
  API_REQUEST_DEFAULT: 30000,

  /** Streaming message timeout (2 minutes) */
  STREAMING_TIMEOUT: 120000,

  /** Focus input delay (next tick) */
  FOCUS_DELAY: 0,

  /** Search result copy feedback */
  SEARCH_COPY_FEEDBACK: 1200,
} as const;

// ============================================================================
// POLLING & REFRESH INTERVALS (milliseconds)
// ============================================================================

export const INTERVALS = {
  /** Agents dashboard auto-refresh */
  AGENTS_REFRESH: 30000,

  /** Monitoring widget stats update */
  MONITORING_STATS: 5000,

  /** WebSocket ping interval */
  WEBSOCKET_PING: 30000,

  /** WebSocket reconnect delay */
  WEBSOCKET_RECONNECT: 3000,
} as const;

// ============================================================================
// FILE & UPLOAD LIMITS
// ============================================================================

export const FILE_LIMITS = {
  /** Maximum file size in bytes (2MB) */
  MAX_FILE_SIZE: 2 * 1024 * 1024,

  /** Maximum file size in MB (for display) */
  MAX_FILE_SIZE_MB: 2,

  /** Maximum image dimension (width/height) */
  MAX_IMAGE_DIMENSION: 2048,
} as const;

/** PNG file signature bytes */
export const PNG_SIGNATURE = [137, 80, 78, 71, 13, 10, 26, 10] as const;

// ============================================================================
// PAGINATION & LIMITS
// ============================================================================

export const PAGINATION = {
  /** Default search results limit */
  DEFAULT_SEARCH_LIMIT: 8,

  /** Available search limit options */
  SEARCH_LIMIT_OPTIONS: [5, 8, 10, 20] as const,

  /** Maximum sources to insert in chat */
  MAX_SOURCES_INSERT: 5,

  /** Maximum topics to display */
  MAX_TOPICS_DISPLAY: 6,

  /** Last N messages for context */
  CONTEXT_MESSAGES_COUNT: 10,

  /** Last N alerts to display */
  ALERTS_DISPLAY_COUNT: 10,

  /** Conversation trainer days back */
  TRAINER_DAYS_BACK: 7,

  /** Knowledge graph builder days back */
  KG_BUILDER_DAYS_BACK: 30,
} as const;

// ============================================================================
// WEBSOCKET CONFIGURATION
// ============================================================================

export const WEBSOCKET = {
  /** Default reconnect interval */
  RECONNECT_INTERVAL: 3000,

  /** Maximum reconnect attempts */
  MAX_RECONNECT_ATTEMPTS: 5,

  /** Ping interval */
  PING_INTERVAL: 30000,
} as const;

// ============================================================================
// UI CONSTANTS
// ============================================================================

export const UI = {
  /** Text preview truncation length */
  TEXT_PREVIEW_LENGTH: 220,

  /** Session ID display truncation */
  SESSION_ID_DISPLAY_LENGTH: 8,

  /** Maximum textarea height (px) */
  MAX_TEXTAREA_HEIGHT: 120,

  /** Modal max width */
  MODAL_MAX_WIDTH: '980px',

  /** Modal content max height */
  MODAL_CONTENT_MAX_HEIGHT: '60vh',
} as const;

// ============================================================================
// Z-INDEX LAYERS
// ============================================================================

export const Z_INDEX = {
  /** Dropdown menus */
  DROPDOWN: 50,

  /** Modal overlay */
  MODAL_OVERLAY: 100,

  /** Modal content */
  MODAL_CONTENT: 100,

  /** Toast notifications */
  TOAST: 100,

  /** Tooltips */
  TOOLTIP: 150,
} as const;

// ============================================================================
// ANIMATION DURATIONS (milliseconds / framer-motion seconds)
// ============================================================================

export const ANIMATION = {
  /** Fast transition (ms) */
  FAST: 200,

  /** Normal transition (ms) */
  NORMAL: 300,

  /** Slow transition (ms) */
  SLOW: 500,

  /** Logo hover effect (ms) */
  LOGO_HOVER: 1000,

  /** Framer motion default (seconds) */
  FRAMER_DEFAULT: 0.3,
} as const;

// ============================================================================
// STRING OPERATIONS
// ============================================================================

export const STRING_OPS = {
  /** Session ID substring start */
  SESSION_ID_START: 2,

  /** Session ID substring end */
  SESSION_ID_END: 9,
} as const;

// ============================================================================
// SCORING & PERCENTAGES
// ============================================================================

export const SCORING = {
  /** Base for percentage calculation */
  PERCENTAGE_BASE: 100,

  /** Decimal places for score display */
  SCORE_DECIMALS: 10,
} as const;

// ============================================================================
// API CONFIGURATION
// ============================================================================

export const API_CONFIG = {
  /** Default request timeout */
  DEFAULT_TIMEOUT: 30000,

  /** Streaming timeout */
  STREAMING_TIMEOUT: 120000,
} as const;

// ============================================================================
// TYPE EXPORTS
// ============================================================================

export type SearchLimitOption = (typeof PAGINATION.SEARCH_LIMIT_OPTIONS)[number];
