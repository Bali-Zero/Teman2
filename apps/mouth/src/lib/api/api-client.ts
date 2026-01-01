import { ApiClientBase } from './client';
import { AuthApi } from './auth/auth.api';
import { ChatApi } from './chat/chat.api';
import { KnowledgeApi } from './knowledge/knowledge.api';
import { ConversationsApi } from './conversations/conversations.api';
import { TeamApi } from './team/team.api';
import { AdminApi } from './admin/admin.api';
import { UploadApi } from './media/upload.api';
import { AudioApi } from './media/audio.api';
import { ImageApi } from './media/image.api';
import { CrmApi } from './crm/crm.api';
import { DriveApi } from './drive/drive.api';
import { EmailApi } from './email/email.api';
import { PortalApi } from './portal/portal.api';
import { WebSocketUtils } from './websocket/websocket.utils';
import { AnalyticsApi } from './analytics/analytics.api';
import { UserProfile, UserMemoryContext, AgentStep } from '@/types';
import type { LoginResponse } from './auth/auth.types';
import type { KnowledgeSearchResponse, KnowledgeSearchResult, TierLevel } from './knowledge/knowledge.types';
import type {
  ConversationHistoryResponse,
  ConversationListItem,
  ConversationListResponse,
  SingleConversationResponse,
} from './conversations/conversations.types';
import type { ClockResponse } from './team/team.types';

/**
 * Unified API Client that composes all domain-specific API modules.
 * This maintains backward compatibility with the original ApiClient interface.
 */
export class ApiClient extends ApiClientBase {
  // Domain-specific API modules
  private authApi: AuthApi;
  private chatApi: ChatApi;
  private knowledgeApi: KnowledgeApi;
  private conversationsApi: ConversationsApi;
  private teamApi: TeamApi;
  private adminApi: AdminApi;
  private uploadApi: UploadApi;
  private audioApi: AudioApi;
  private imageApi: ImageApi;
  private crmApi: CrmApi;
  private driveApi: DriveApi;
  private emailApi: EmailApi;
  private portalApi: PortalApi;
  private wsUtils: WebSocketUtils;
  private analyticsApi: AnalyticsApi;

  constructor(baseUrl: string) {
    super(baseUrl);
    this.authApi = new AuthApi(this);
    this.chatApi = new ChatApi(this);
    this.knowledgeApi = new KnowledgeApi(this);
    this.conversationsApi = new ConversationsApi(this);
    this.teamApi = new TeamApi(this);
    this.adminApi = new AdminApi(this);
    this.uploadApi = new UploadApi(this);
    this.audioApi = new AudioApi(this);
    this.imageApi = new ImageApi(this);
    this.crmApi = new CrmApi(this);
    this.driveApi = new DriveApi(this);
    this.emailApi = new EmailApi(this);
    this.portalApi = new PortalApi(this);
    this.wsUtils = new WebSocketUtils(this);
    this.analyticsApi = new AnalyticsApi(baseUrl, () => this.token);
  }

  // ============================================================================
  // Generic HTTP Methods (for simple endpoints)
  // ============================================================================

  /**
   * Simple GET request for endpoints that don't need domain-specific logic.
   */
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  /**
   * Simple POST request for endpoints that don't need domain-specific logic.
   */
  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  // ============================================================================
  // CRM (exposed directly)
  // ============================================================================

  public get crm(): CrmApi {
    return this.crmApi;
  }

  // ============================================================================
  // Google Drive (Document storage integration)
  // ============================================================================

  public get drive(): DriveApi {
    return this.driveApi;
  }

  // ============================================================================
  // Email (Zoho Mail integration)
  // ============================================================================

  public get email(): EmailApi {
    return this.emailApi;
  }

  // ============================================================================
  // Portal (Client-facing portal)
  // ============================================================================

  public get portal(): PortalApi {
    return this.portalApi;
  }

  // ============================================================================
  // Analytics (Founder-only dashboard)
  // ============================================================================

  public get analytics(): AnalyticsApi {
    return this.analyticsApi;
  }

  // ============================================================================
  // Knowledge + Conversations (backward compatibility)
  // ============================================================================

  public get knowledge(): KnowledgeApi {
    return this.knowledgeApi;
  }

  public get conversations(): ConversationsApi {
    return this.conversationsApi;
  }

  // ============================================================================
  // Auth endpoints (delegated to AuthApi)
  // ============================================================================

  async login(email: string, pin: string): Promise<LoginResponse> {
    return this.authApi.login(email, pin);
  }

  async logout(): Promise<void> {
    return this.authApi.logout();
  }

  async getProfile(): Promise<UserProfile> {
    return this.authApi.getProfile();
  }

  // ============================================================================
  // Chat endpoints (delegated to ChatApi)
  // ============================================================================

  async sendMessage(
    message: string,
    userId?: string
  ): Promise<{
    response: string;
    sources: Array<{ title?: string; content?: string }>;
  }> {
    return this.chatApi.sendMessage(message, userId);
  }

  async sendMessageStreaming(
    message: string,
    conversationId: string | undefined,
    onChunk: (chunk: string) => void,
    onDone: (
      fullResponse: string,
      sources: Array<{ title?: string; content?: string }>,
      metadata?: {
        execution_time?: number;
        route_used?: string;
        context_length?: number;
        emotional_state?: string;
        status?: string;
      }
    ) => void,
    onError: (error: Error) => void,
    onStep?: (step: AgentStep) => void,
    timeoutMs: number = 120000,
    conversationHistory?: Array<{ role: string; content: string }>,
    abortSignal?: AbortSignal,
    correlationId?: string,
    idleTimeoutMs: number = 60000,
    maxTotalTimeMs: number = 600000
  ): Promise<void> {
    return this.chatApi.sendMessageStreaming(
      message,
      conversationId,
      onChunk,
      onDone,
      onError,
      onStep,
      timeoutMs,
      conversationHistory,
      abortSignal,
      correlationId,
      idleTimeoutMs,
      maxTotalTimeMs
    );
  }

  // ============================================================================
  // Knowledge Search (delegated to KnowledgeApi)
  // ============================================================================

  async searchDocs(params: {
    query: string;
    level?: number;
    limit?: number;
    collection?: string | null;
    tier_filter?: TierLevel[] | null;
  }): Promise<KnowledgeSearchResponse> {
    return this.knowledgeApi.searchDocs(params);
  }

  // ============================================================================
  // Conversations (delegated to ConversationsApi)
  // ============================================================================

  async getConversationHistory(sessionId?: string): Promise<ConversationHistoryResponse> {
    return this.conversationsApi.getConversationHistory(sessionId);
  }

  async saveConversation(
    messages: Array<{
      role: string;
      content: string;
      sources?: Array<{ title?: string; content?: string }>;
      imageUrl?: string;
    }>,
    sessionId?: string,
    metadata?: Record<string, unknown>
  ): Promise<{ success: boolean; conversation_id: number; messages_saved: number }> {
    return this.conversationsApi.saveConversation(messages, sessionId, metadata);
  }

  async clearConversations(
    sessionId?: string
  ): Promise<{ success: boolean; deleted_count: number }> {
    return this.conversationsApi.clearConversations(sessionId);
  }

  async getConversationStats(): Promise<{
    success: boolean;
    user_email: string;
    total_conversations: number;
    total_messages: number;
    last_conversation: string | null;
  }> {
    return this.conversationsApi.getConversationStats();
  }

  async listConversations(
    limit: number = 20,
    offset: number = 0
  ): Promise<ConversationListResponse> {
    return this.conversationsApi.listConversations(limit, offset);
  }

  async getConversation(conversationId: number): Promise<SingleConversationResponse> {
    return this.conversationsApi.getConversation(conversationId);
  }

  async deleteConversation(
    conversationId: number
  ): Promise<{ success: boolean; deleted_id: number }> {
    return this.conversationsApi.deleteConversation(conversationId);
  }

  async getUserMemoryContext(): Promise<UserMemoryContext> {
    return this.conversationsApi.getUserMemoryContext();
  }

  // ============================================================================
  // Team Activity (delegated to TeamApi)
  // ============================================================================

  async clockIn(): Promise<ClockResponse> {
    return this.teamApi.clockIn();
  }

  async clockOut(): Promise<ClockResponse> {
    return this.teamApi.clockOut();
  }

  async getClockStatus(): Promise<{
    is_clocked_in: boolean;
    today_hours: number;
    week_hours: number;
  }> {
    return this.teamApi.getClockStatus();
  }

  // ============================================================================
  // Admin-Only Endpoints (delegated to AdminApi)
  // ============================================================================

  async getTeamStatus(): Promise<
    Array<{
      user_id: string;
      email: string;
      is_online: boolean;
      last_action: string;
      last_action_type: string;
    }>
  > {
    return this.adminApi.getTeamStatus();
  }

  async getDailyHours(date?: string): Promise<
    Array<{
      user_id: string;
      email: string;
      date: string;
      clock_in: string;
      clock_out: string;
      hours_worked: number;
    }>
  > {
    return this.adminApi.getDailyHours(date);
  }

  async getWeeklySummary(weekStart?: string): Promise<
    Array<{
      user_id: string;
      email: string;
      week_start: string;
      days_worked: number;
      total_hours: number;
      avg_hours_per_day: number;
    }>
  > {
    return this.adminApi.getWeeklySummary(weekStart);
  }

  async getMonthlySummary(monthStart?: string): Promise<
    Array<{
      user_id: string;
      email: string;
      month_start: string;
      days_worked: number;
      total_hours: number;
      avg_hours_per_day: number;
    }>
  > {
    return this.adminApi.getMonthlySummary(monthStart);
  }

  async exportTimesheet(startDate: string, endDate: string): Promise<Blob> {
    return this.adminApi.exportTimesheet(startDate, endDate);
  }

  async getSystemHealth(): Promise<import('./admin/admin.types').SystemHealthReport> {
    return this.adminApi.getSystemHealth();
  }

  async getPostgresTables(): Promise<string[]> {
    return this.adminApi.getPostgresTables();
  }

  async getTableData(table: string, limit = 50, offset = 0): Promise<import('./admin/admin.types').TableDataResponse> {
    return this.adminApi.getTableData(table, limit, offset);
  }

  async getQdrantCollections(): Promise<import('./admin/admin.types').QdrantCollectionsResponse> {
    return this.adminApi.getQdrantCollections();
  }

  async getQdrantPoints(collection: string, limit = 20, offset?: string): Promise<import('./admin/admin.types').QdrantPointsResponse> {
    return this.adminApi.getQdrantPoints(collection, limit, offset);
  }

  // ============================================================================
  // Media Services (delegated to UploadApi, AudioApi, ImageApi)
  // ============================================================================

  async uploadFile(
    file: File
  ): Promise<{ success: boolean; url: string; filename: string; type: string }> {
    return this.uploadApi.uploadFile(file);
  }

  async transcribeAudio(audioBlob: Blob, mimeType: string = 'audio/webm'): Promise<string> {
    return this.audioApi.transcribeAudio(audioBlob, mimeType);
  }

  async generateSpeech(
    text: string,
    voice: 'alloy' | 'echo' | 'fable' | 'onyx' | 'nova' | 'shimmer' = 'alloy'
  ): Promise<Blob> {
    return this.audioApi.generateSpeech(text, voice);
  }

  async generateImage(prompt: string): Promise<{ image_url: string }> {
    return this.imageApi.generateImage(prompt);
  }

  // ============================================================================
  // WebSocket (delegated to WebSocketUtils)
  // ============================================================================

  getWebSocketUrl(): string {
    return this.wsUtils.getWebSocketUrl();
  }

  getWebSocketSubprotocol(): string | null {
    return this.wsUtils.getWebSocketSubprotocol();
  }
}
