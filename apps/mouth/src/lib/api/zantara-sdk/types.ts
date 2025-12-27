/**
 * Zantara SDK - Type Definitions
 * Complete type definitions for all Zantara capabilities
 */

// ============================================================================
// Legacy Types (DEPRECATED - kept for backward compatibility)
// ============================================================================

/** @deprecated Use AgenticRAGQueryRequest/Response instead */
export type CellGiantPhase = 'giant' | 'cell' | 'zantara';

export type PhaseStatus = 'started' | 'complete';

export interface CellGiantPhaseEvent {
  type: 'phase';
  data: {
    name: CellGiantPhase;
    status: PhaseStatus;
  };
}

export interface CellGiantKeepaliveEvent {
  type: 'keepalive';
  data: {
    phase: CellGiantPhase;
    elapsed: number;
  };
}

export interface CellGiantMetadataEvent {
  type: 'metadata';
  data: {
    giant_quality_score: number;
    giant_domain: string;
    corrections_count: number;
    enhancements_count: number;
    calibrations_count: number;
  };
}

export interface CellGiantTokenEvent {
  type: 'token';
  data: string;
}

export interface CellGiantDoneEvent {
  type: 'done';
  data: {
    execution_time: number;
    route_used: string;
    tokens: number;
  };
}

export interface CellGiantErrorEvent {
  type: 'error';
  data: {
    message: string;
    code?: string;
  };
}

export type CellGiantSSEEvent =
  | CellGiantPhaseEvent
  | CellGiantKeepaliveEvent
  | CellGiantMetadataEvent
  | CellGiantTokenEvent
  | CellGiantDoneEvent
  | CellGiantErrorEvent;

export interface CellGiantQueryRequest {
  query: string;
  user_id?: string;
  enable_vision?: boolean;
  session_id?: string;
  conversation_id?: number;
  conversation_history?: ConversationMessage[];
}

export interface CellGiantQueryResponse {
  answer: string;
  sources: Source[];
  context_length: number;
  execution_time: number;
  route_used: string;
  tools_called: number;
  total_steps: number;
  debug_info?: Record<string, unknown>;
}

// ============================================================================
// Agentic RAG Types
// ============================================================================

export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface Source {
  id: number;
  title: string;
  url?: string;
  score: number;
  collection: string;
  snippet: string;
  content: string;
  doc_id?: string;
  download_url?: string;
}

export interface AgenticRAGQueryRequest {
  query: string;
  user_id?: string;
  enable_vision?: boolean;
  session_id?: string;
  conversation_id?: number;
  conversation_history?: ConversationMessage[];
}

export interface AgenticRAGQueryResponse {
  answer: string;
  sources: Source[];
  context_length: number;
  execution_time: number;
  route_used: string;
  tools_called: number;
  total_steps: number;
  debug_info?: Record<string, unknown>;
}

// ============================================================================
// Memory System Types
// ============================================================================

export interface UserMemory {
  user_id: string;
  profile_facts: string[];
  summary: string;
  counters: {
    conversations: number;
    searches: number;
    tasks: number;
  };
  updated_at: string;
}

export interface CollectiveMemory {
  id: number;
  content: string;
  category: string;
  confidence: number;
  source_count: number;
  is_promoted: boolean;
  first_learned_at: string;
  last_confirmed_at: string;
}

export type EpisodicEventType =
  | 'milestone'
  | 'problem'
  | 'resolution'
  | 'decision'
  | 'meeting'
  | 'deadline'
  | 'discovery'
  | 'general';

export type EpisodicEmotion =
  | 'positive'
  | 'negative'
  | 'neutral'
  | 'urgent'
  | 'frustrated'
  | 'excited'
  | 'worried';

export interface EpisodicEvent {
  id: number;
  event_type: EpisodicEventType;
  title: string;
  description?: string;
  emotion: EpisodicEmotion;
  occurred_at: string;
  related_entities?: Record<string, unknown>[];
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface EpisodicTimelineRequest {
  user_id: string;
  start_date?: string;
  end_date?: string;
  event_type?: EpisodicEventType;
  emotion?: EpisodicEmotion;
  limit?: number;
  offset?: number;
}

// ============================================================================
// Audio Types
// ============================================================================

export type AudioVoice = 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer';

export interface SpeechRequest {
  text: string;
  voice?: AudioVoice;
  model?: string;
}

export interface TranscribeRequest {
  file: File;
  language?: string;
}

export interface TranscribeResponse {
  text: string;
}

// ============================================================================
// Client Journey Types
// ============================================================================

export type JourneyStatus = 'not_started' | 'in_progress' | 'completed' | 'blocked' | 'cancelled';

export type StepStatus = 'pending' | 'in_progress' | 'completed' | 'blocked' | 'skipped';

export interface JourneyStep {
  step_id: string;
  step_number: number;
  title: string;
  description: string;
  prerequisites: string[];
  required_documents: string[];
  estimated_duration_days: number;
  status: StepStatus;
  started_at?: string;
  completed_at?: string;
  blocked_reason?: string;
  notes: string[];
}

export interface ClientJourney {
  journey_id: string;
  journey_type: string;
  client_id: string;
  title: string;
  description: string;
  steps: JourneyStep[];
  status: JourneyStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  estimated_completion?: string;
  actual_completion?: string;
  metadata: Record<string, unknown>;
}

export interface JourneyProgress {
  journey_id: string;
  status: JourneyStatus;
  progress_percentage: number;
  completed_steps: number;
  in_progress_steps: number;
  blocked_steps: number;
  total_steps: number;
  estimated_days_remaining: number;
  started_at?: string;
  estimated_completion?: string;
  next_steps: string[];
}

export type JourneyTemplate = 'pt_pma_setup' | 'kitas_application' | 'property_purchase';

export interface CreateJourneyRequest {
  journey_type: JourneyTemplate;
  client_id: string;
  custom_metadata?: Record<string, unknown>;
  custom_steps?: Array<{
    step_id: string;
    title: string;
    description: string;
    prerequisites?: string[];
    required_documents?: string[];
    estimated_duration_days?: number;
  }>;
}

// ============================================================================
// Compliance Monitor Types
// ============================================================================

export type ComplianceType =
  | 'visa_expiry'
  | 'tax_deadline'
  | 'license_renewal'
  | 'annual_filing'
  | 'other';

export type AlertSeverity = 'info' | 'warning' | 'urgent' | 'critical';

export type AlertStatus = 'active' | 'acknowledged' | 'resolved' | 'expired';

export interface ComplianceItem {
  item_id: string;
  client_id: string;
  compliance_type: ComplianceType;
  title: string;
  description: string;
  deadline: string;
  estimated_cost?: number;
  required_documents: string[];
  metadata?: Record<string, unknown>;
}

export interface ComplianceAlert {
  alert_id: string;
  client_id: string;
  compliance_type: ComplianceType;
  title: string;
  description: string;
  deadline: string;
  days_until: number;
  severity: AlertSeverity;
  status: AlertStatus;
  created_at: string;
}

export interface ComplianceDeadlinesRequest {
  client_id?: string;
  days_ahead?: number;
}

// ============================================================================
// Dynamic Pricing Types
// ============================================================================

export interface CostItem {
  category: string;
  description: string;
  amount: number;
  currency: string;
  source_oracle: string;
  is_recurring: boolean;
  frequency?: string;
}

export interface PricingResult {
  scenario: string;
  total_setup_cost: number;
  total_recurring_cost: number;
  currency: string;
  cost_items: CostItem[];
  timeline_estimate: string;
  breakdown_by_category: Record<string, number>;
  key_assumptions: string[];
  confidence: number;
}

// ============================================================================
// WebSocket Types
// ============================================================================

export type WebSocketChannel =
  | 'USER_NOTIFICATIONS'
  | 'AI_RESULTS'
  | 'CHAT_MESSAGES'
  | 'SYSTEM_EVENTS';

export interface WebSocketMessage {
  type: 'notification' | 'ai-result' | 'chat-message' | 'system-event' | 'ping' | 'pong';
  data: Record<string, unknown>;
}

// ============================================================================
// Team Analytics Types
// ============================================================================

export interface BurnoutSignal {
  user: string;
  email: string;
  burnout_risk_score: number;
  risk_level: 'High Risk' | 'Medium Risk' | 'Low Risk';
  warning_signals: string[];
  warning_count: number;
  total_sessions_analyzed: number;
}

export interface TeamInsights {
  total_members: number;
  active_members: number;
  productivity_score: number;
  workload_distribution: Record<string, number>;
  optimal_hours: {
    start: string;
    end: string;
  };
}

// ============================================================================
// Knowledge Graph Types
// ============================================================================

export interface GraphEntity {
  id: string;
  type: string;
  name: string;
  description?: string;
  properties: Record<string, unknown>;
}

export interface GraphRelation {
  source_id: string;
  target_id: string;
  type: string;
  properties: Record<string, unknown>;
  strength: number;
}

export interface GraphTraversalResult {
  nodes: Array<{
    id: string;
    type: string;
    name: string;
    description?: string;
  }>;
  edges: Array<{
    source: string;
    target: string;
    type: string;
    strength: number;
  }>;
}

// ============================================================================
// Image Generation Types
// ============================================================================

export interface ImageGenerationRequest {
  prompt: string;
}

export interface ImageGenerationResponse {
  success: boolean;
  url?: string;
  prompt: string;
  service: string;
  error?: string;
  details?: string;
}

// ============================================================================
// Common Types
// ============================================================================

export interface ApiError {
  message: string;
  code?: string;
  details?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}


