import { ApiClientBase } from "./client";
import { AuthApi } from "./auth/auth.api";
import { ChatApi } from "./chat/chat.api";
import { KnowledgeApi } from "./knowledge/knowledge.api";
import { ConversationsApi } from "./conversations/conversations.api";
import { TeamApi } from "./team/team.api";
import { AdminApi } from "./admin/admin.api";
import { UploadApi } from "./media/upload.api";
import { AudioApi } from "./media/audio.api";
import { ImageApi } from "./media/image.api";
import { CrmApi } from "./crm/crm.api";
import { DriveApi } from "./drive/drive.api";
import { PortalApi } from "./portal/portal.api";
import { WhatsAppApi } from "./whatsapp/whatsapp.api";
import { TelegramApi } from "./telegram/telegram.api";
import { InstagramApi } from "./instagram/instagram.api";
import { TwitterApi } from "./twitter/twitter.api";
import { WorkflowApi } from "./workflow";
import { WebSocketUtils } from "./websocket/websocket.utils";
import { AnalyticsApi } from "./analytics/analytics.api";
import { OmnichannelApi } from "./omnichannel/omnichannel.api";
import { BlogApi } from "./blog/blog.api";
import { PrimeApi } from "./prime/prime.api";
import { UserProfile, UserMemoryContext, AgentStep } from "@/types";
import type { LoginResponse } from "./auth/auth.types";
import type {
  KnowledgeSearchResponse,
  KnowledgeSearchResult,
  TierLevel,
} from "./knowledge/knowledge.types";
import type {
  ConversationHistoryResponse,
  ConversationListItem,
  ConversationListResponse,
  SingleConversationResponse,
} from "./conversations/conversations.types";
import type { ClockResponse } from "./team/team.types";

/**
 * INTAKE login-gate clearance status (GET /api/intake/gate/status).
 * Count-only probe — never returns the items themselves (PII stays server-side).
 * Identity is derived from the JWT server-side, NOT from the frontend profile.
 * Spec: research/operations/2026-06-06-intake-login-gate-spec.md §3.1.
 */
export interface GateSection {
  count: number;
  blocking: boolean;
}

export interface GateStatus {
  /** true if ANY blocking section has count > 0 */
  blocked: boolean;
  sections: {
    documents: GateSection;
    late_note: GateSection;
    deadlines: GateSection;
  };
  /** ISO timestamp the probe was computed at */
  as_of: string;
  /** true when the backend served a degraded/best-effort answer (fail-open, §8 Q4) */
  degraded?: boolean;
}

/**
 * A compliance deadline alert as returned by GET /api/compliance/alerts.
 * Team members are auto-scoped server-side to alerts on clients assigned to
 * them (clients.assigned_to = their email). Fields mirror migration 114.
 */
export interface ComplianceAlertItem {
  alert_id: string;
  client_id: number;
  category: string;
  severity: "info" | "warning" | "urgent" | "critical";
  status: "pending" | "sent" | "acknowledged" | "resolved" | "expired";
  /** ISO date (YYYY-MM-DD) of the statutory deadline */
  deadline: string;
  days_until: number;
  message_it?: string | null;
  message_en?: string | null;
  message_id?: string | null;
  suggested_action?: string | null;
  estimated_cost_idr?: number | null;
}

export interface ComplianceAlertPage {
  items: ComplianceAlertItem[];
  limit: number;
  offset: number;
}

export interface ComplianceAlertOutcome {
  alert_id: string;
  outcome: "acknowledged";
  status: "acknowledged";
}

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
  public adminApi: AdminApi;
  private uploadApi: UploadApi;
  private audioApi: AudioApi;
  private imageApi: ImageApi;
  private crmApi: CrmApi;
  private driveApi: DriveApi;
  private portalApi: PortalApi;
  private whatsappApi: WhatsAppApi;
  private telegramApi: TelegramApi;
  private instagramApi: InstagramApi;
  private twitterApi: TwitterApi;
  private workflowApi: WorkflowApi;
  private wsUtils: WebSocketUtils;
  private analyticsApi: AnalyticsApi;
  private omnichannelApi: OmnichannelApi;
  private blogApi: BlogApi;
  private primeApi: PrimeApi;

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
    this.portalApi = new PortalApi(this);
    this.whatsappApi = new WhatsAppApi(this);
    this.telegramApi = new TelegramApi(this);
    this.instagramApi = new InstagramApi(this);
    this.twitterApi = new TwitterApi(this);
    this.workflowApi = new WorkflowApi(this);
    this.wsUtils = new WebSocketUtils(this);
    this.analyticsApi = new AnalyticsApi(baseUrl, () => this.token);
    this.omnichannelApi = new OmnichannelApi(this);
    this.blogApi = new BlogApi(this);
    this.primeApi = new PrimeApi(this);
  }

  // ============================================================================
  // Generic HTTP Methods (for simple endpoints)
  // ============================================================================

  /**
   * Simple GET request for endpoints that don't need domain-specific logic.
   */
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "GET" });
  }

  /**
   * Simple POST request for endpoints that don't need domain-specific logic.
   */
  async post<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * Simple PATCH request for endpoints that don't need domain-specific logic.
   */
  async patch<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * Simple PUT request for endpoints that don't need domain-specific logic.
   */
  async put<T>(endpoint: string, data?: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  /**
   * Simple DELETE request for endpoints that don't need domain-specific logic.
   */
  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: "DELETE" });
  }

  // ============================================================================
  // INTAKE Login Gate (mandatory pre-workspace clearance — spec §3)
  // ============================================================================

  /**
   * Fetch the current user's gate clearance status. Cheap count-only probe;
   * called on every workspace mount + route change (spec §3.1, fix F5).
   */
  async getGateStatus(): Promise<GateStatus> {
    return this.get<GateStatus>("/api/intake/gate/status");
  }

  /**
   * Resolve today's late-clock-in incident for the authenticated user by
   * submitting a reason (spec §3.3, §4.2). Idempotent server-side.
   */
  async resolveMyLateIncident(
    reason: string,
  ): Promise<{ success: boolean; state: string }> {
    return this.post<{ success: boolean; state: string }>(
      "/api/hr/my-late-incident/resolve",
      { reason },
    );
  }

  /**
   * Acknowledge a compliance deadline alert (outcome="acknowledged"), clearing
   * it from the deadlines gate section (spec §3.3).
   */
  async acknowledgeComplianceAlert(
    alertId: string,
    note?: string,
  ): Promise<ComplianceAlertOutcome> {
    return this.post<ComplianceAlertOutcome>(
      `/api/compliance/alerts/${alertId}/outcome`,
      { outcome: "acknowledged", note },
    );
  }

  /**
   * List compliance deadline alerts visible to the current user (team members
   * are auto-scoped server-side to their assigned clients). Used by the
   * login-gate Deadlines section so it can be cleared inline. The backend
   * `status` filter is single-valued — call once per status and merge.
   */
  async listMyComplianceAlerts(options?: {
    status?: ComplianceAlertItem["status"];
    deadlineWithinDays?: number;
    limit?: number;
    offset?: number;
  }): Promise<ComplianceAlertPage> {
    const params = new URLSearchParams();
    if (options?.status) params.set("status", options.status);
    if (options?.deadlineWithinDays !== undefined) {
      params.set("deadline_within_days", String(options.deadlineWithinDays));
    }
    params.set("limit", String(options?.limit ?? 500));
    params.set("offset", String(options?.offset ?? 0));
    return this.get<ComplianceAlertPage>(
      `/api/compliance/alerts?${params.toString()}`,
    );
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
  // Portal (Client-facing portal)
  // ============================================================================

  public get portal(): PortalApi {
    return this.portalApi;
  }

  // ============================================================================
  // WhatsApp (Business messaging)
  // ============================================================================

  public get whatsapp(): WhatsAppApi {
    return this.whatsappApi;
  }

  // ============================================================================
  // Telegram (Business messaging)
  // ============================================================================

  public get telegram(): TelegramApi {
    return this.telegramApi;
  }

  // ============================================================================
  // Instagram (Business messaging)
  // ============================================================================

  public get instagram(): InstagramApi {
    return this.instagramApi;
  }

  // ============================================================================
  // Twitter/X (Business messaging)
  // ============================================================================

  public get twitter(): TwitterApi {
    return this.twitterApi;
  }

  // ============================================================================
  // Omnichannel (Unified Inbox)
  // ============================================================================

  public get omnichannel(): OmnichannelApi {
    return this.omnichannelApi;
  }

  public get workflow(): WorkflowApi {
    return this.workflowApi;
  }

  // ============================================================================
  // Blog (Articles, News)
  // ============================================================================

  public get blog(): BlogApi {
    return this.blogApi;
  }

  // ============================================================================
  // Prime Intelligence (Zone analysis, investment data)
  // ============================================================================

  public get prime(): PrimeApi {
    return this.primeApi;
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

  async verifyMagicLink(token: string): Promise<LoginResponse> {
    return this.authApi.verifyMagicLink(token);
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
    userId?: string,
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
      },
    ) => void,
    onError: (error: Error) => void,
    onStep?: (step: AgentStep) => void,
    timeoutMs: number = 120000,
    conversationHistory?: Array<{ role: string; content: string }>,
    abortSignal?: AbortSignal,
    correlationId?: string,
    idleTimeoutMs: number = 60000,
    maxTotalTimeMs: number = 600000,
    images?: Array<{ base64: string; name: string }>, // Vision images
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
      maxTotalTimeMs,
      images,
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

  async getConversationHistory(
    sessionId?: string,
  ): Promise<ConversationHistoryResponse> {
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
    metadata?: Record<string, unknown>,
  ): Promise<{
    success: boolean;
    conversation_id: number;
    messages_saved: number;
  }> {
    return this.conversationsApi.saveConversation(
      messages,
      sessionId,
      metadata,
    );
  }

  async clearConversations(
    sessionId?: string,
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
    offset: number = 0,
  ): Promise<ConversationListResponse> {
    return this.conversationsApi.listConversations(limit, offset);
  }

  async getConversation(
    conversationId: number,
  ): Promise<SingleConversationResponse> {
    return this.conversationsApi.getConversation(conversationId);
  }

  async deleteConversation(
    conversationId: number,
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

  async getSystemHealth(): Promise<
    import("./admin/admin.types").SystemHealthReport
  > {
    return this.adminApi.getSystemHealth();
  }

  async getPostgresTables(): Promise<string[]> {
    return this.adminApi.getPostgresTables();
  }

  async getTableData(
    table: string,
    limit = 50,
    offset = 0,
  ): Promise<import("./admin/admin.types").TableDataResponse> {
    return this.adminApi.getTableData(table, limit, offset);
  }

  async getQdrantCollections(): Promise<
    import("./admin/admin.types").QdrantCollectionsResponse
  > {
    return this.adminApi.getQdrantCollections();
  }

  async getQdrantPoints(
    collection: string,
    limit = 20,
    offset?: string,
  ): Promise<import("./admin/admin.types").QdrantPointsResponse> {
    return this.adminApi.getQdrantPoints(collection, limit, offset);
  }

  // ============================================================================
  // Media Services (delegated to UploadApi, AudioApi, ImageApi)
  // ============================================================================

  async uploadFile(file: File): Promise<{
    success: boolean;
    url: string;
    filename: string;
    type: string;
  }> {
    return this.uploadApi.uploadFile(file);
  }

  async transcribeAudio(
    audioBlob: Blob,
    mimeType: string = "audio/webm",
  ): Promise<string> {
    return this.audioApi.transcribeAudio(audioBlob, mimeType);
  }

  async generateSpeech(
    text: string,
    voice: "alloy" | "echo" | "fable" | "onyx" | "nova" | "shimmer" = "alloy",
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
