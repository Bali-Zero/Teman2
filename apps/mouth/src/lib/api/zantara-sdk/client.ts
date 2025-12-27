/**
 * Zantara SDK - Main Client
 * Unified client for all Zantara capabilities
 */

import type {
  AgenticRAGQueryRequest,
  AgenticRAGQueryResponse,
  ApiError,
  UserMemory,
  CollectiveMemory,
  EpisodicEvent,
  EpisodicTimelineRequest,
  SpeechRequest,
  TranscribeResponse,
  ClientJourney,
  CreateJourneyRequest,
  JourneyProgress,
  ComplianceItem,
  ComplianceAlert,
  ComplianceDeadlinesRequest,
  PricingResult,
  BurnoutSignal,
  TeamInsights,
  GraphEntity,
  GraphRelation,
  GraphTraversalResult,
  ImageGenerationRequest,
  ImageGenerationResponse,
  TranscribeRequest,
} from './types';

export interface ZantaraSDKConfig {
  baseUrl: string;
  apiKey?: string;
  timeout?: number;
}

export class ZantaraSDK {
  private baseUrl: string;
  private apiKey?: string;
  private timeout: number;

  constructor(config: ZantaraSDKConfig) {
    this.baseUrl = config.baseUrl.replace(/\/$/, '');
    this.apiKey = config.apiKey;
    this.timeout = config.timeout || 30000;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error: ApiError = await response.json().catch(() => ({
          message: `HTTP ${response.status}: ${response.statusText}`,
          code: `HTTP_${response.status}`,
        }));
        throw error;
      }

      return await response.json();
    } catch (error) {
      clearTimeout(timeoutId);
      if (error instanceof Error && error.name === 'AbortError') {
        throw {
          message: 'Request timeout',
          code: 'TIMEOUT',
        } as ApiError;
      }
      throw error;
    }
  }

  // ============================================================================
  // Agentic RAG
  // ============================================================================

  async queryAgenticRAG(
    request: AgenticRAGQueryRequest
  ): Promise<AgenticRAGQueryResponse> {
    return this.request<AgenticRAGQueryResponse>('/api/agentic-rag/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // ============================================================================
  // Memory Systems
  // ============================================================================

  async getUserMemory(userId: string): Promise<UserMemory> {
    return this.request<UserMemory>(`/api/memory/facts?user_id=${userId}`);
  }

  async addUserFact(userId: string, fact: string): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>('/api/memory/facts', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, fact }),
    });
  }

  async getCollectiveMemory(
    category?: string,
    limit = 10
  ): Promise<CollectiveMemory[]> {
    const params = new URLSearchParams();
    if (category) params.set('category', category);
    params.set('limit', limit.toString());
    return this.request<CollectiveMemory[]>(
      `/api/collective-memory?${params.toString()}`
    );
  }

  async getEpisodicTimeline(
    request: EpisodicTimelineRequest
  ): Promise<EpisodicEvent[]> {
    const params = new URLSearchParams();
    params.set('user_id', request.user_id);
    if (request.start_date) params.set('start_date', request.start_date);
    if (request.end_date) params.set('end_date', request.end_date);
    if (request.event_type) params.set('event_type', request.event_type);
    if (request.emotion) params.set('emotion', request.emotion);
    if (request.limit) params.set('limit', request.limit.toString());
    if (request.offset) params.set('offset', request.offset.toString());

    return this.request<EpisodicEvent[]>(
      `/api/episodic-memory/timeline?${params.toString()}`
    );
  }

  // ============================================================================
  // Audio
  // ============================================================================

  async transcribeAudio(request: TranscribeRequest): Promise<TranscribeResponse> {
    const formData = new FormData();
    formData.append('file', request.file);
    if (request.language) {
      formData.append('language', request.language);
    }

    const response = await fetch(`${this.baseUrl}/audio/transcribe`, {
      method: 'POST',
      body: formData,
      headers: this.apiKey
        ? { Authorization: `Bearer ${this.apiKey}` }
        : {},
    });

    if (!response.ok) {
      throw {
        message: `HTTP ${response.status}: ${response.statusText}`,
        code: `HTTP_${response.status}`,
      } as ApiError;
    }

    return response.json();
  }

  async generateSpeech(request: SpeechRequest): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/audio/speech`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw {
        message: `HTTP ${response.status}: ${response.statusText}`,
        code: `HTTP_${response.status}`,
      } as ApiError;
    }

    return response.blob();
  }

  // ============================================================================
  // Client Journeys
  // ============================================================================

  async createJourney(request: CreateJourneyRequest): Promise<ClientJourney> {
    return this.request<ClientJourney>('/api/journeys', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getJourney(journeyId: string): Promise<ClientJourney> {
    return this.request<ClientJourney>(`/api/journeys/${journeyId}`);
  }

  async getJourneyProgress(journeyId: string): Promise<JourneyProgress> {
    return this.request<JourneyProgress>(`/api/journeys/${journeyId}/progress`);
  }

  async completeStep(
    journeyId: string,
    stepId: string,
    notes?: string
  ): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(
      `/api/journeys/${journeyId}/steps/${stepId}/complete`,
      {
        method: 'POST',
        body: JSON.stringify({ notes }),
      }
    );
  }

  // ============================================================================
  // Compliance Monitor
  // ============================================================================

  async getComplianceDeadlines(
    request: ComplianceDeadlinesRequest = {}
  ): Promise<ComplianceItem[]> {
    const params = new URLSearchParams();
    if (request.client_id) params.set('client_id', request.client_id);
    if (request.days_ahead) params.set('days_ahead', request.days_ahead.toString());

    return this.request<ComplianceItem[]>(
      `/api/compliance/deadlines?${params.toString()}`
    );
  }

  async getComplianceAlerts(
    clientId?: string,
    status?: string
  ): Promise<ComplianceAlert[]> {
    const params = new URLSearchParams();
    if (clientId) params.set('client_id', clientId);
    if (status) params.set('status', status);

    return this.request<ComplianceAlert[]>(
      `/api/compliance/alerts?${params.toString()}`
    );
  }

  async acknowledgeAlert(alertId: string): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(
      `/api/compliance/alerts/${alertId}/acknowledge`,
      {
        method: 'POST',
      }
    );
  }

  // ============================================================================
  // Dynamic Pricing
  // ============================================================================

  async calculatePricing(
    scenario: string,
    userLevel = 3
  ): Promise<PricingResult> {
    return this.request<PricingResult>('/api/pricing/calculate', {
      method: 'POST',
      body: JSON.stringify({ scenario, user_level: userLevel }),
    });
  }

  // ============================================================================
  // Team Analytics
  // ============================================================================

  async getBurnoutSignals(userEmail?: string): Promise<BurnoutSignal[]> {
    const params = userEmail ? `?user_email=${userEmail}` : '';
    return this.request<BurnoutSignal[]>(
      `/api/team-analytics/burnout${params}`
    );
  }

  async getTeamInsights(): Promise<TeamInsights> {
    return this.request<TeamInsights>('/api/team-analytics/insights');
  }

  // ============================================================================
  // Knowledge Graph
  // ============================================================================

  async addGraphEntity(entity: GraphEntity): Promise<{ id: string }> {
    return this.request<{ id: string }>('/api/graph/entities', {
      method: 'POST',
      body: JSON.stringify(entity),
    });
  }

  async addGraphRelation(relation: GraphRelation): Promise<{ id: number }> {
    return this.request<{ id: number }>('/api/graph/relations', {
      method: 'POST',
      body: JSON.stringify(relation),
    });
  }

  async getGraphNeighbors(
    entityId: string,
    relationType?: string
  ): Promise<Array<{ target_id: string; target_name: string; relationship_type: string }>> {
    const params = relationType ? `?relation_type=${relationType}` : '';
    return this.request(
      `/api/graph/entities/${entityId}/neighbors${params}`
    );
  }

  async traverseGraph(
    startId: string,
    maxDepth = 2
  ): Promise<GraphTraversalResult> {
    return this.request<GraphTraversalResult>(
      `/api/graph/traverse?start_id=${startId}&max_depth=${maxDepth}`
    );
  }

  // ============================================================================
  // Image Generation
  // ============================================================================

  async generateImage(
    request: ImageGenerationRequest
  ): Promise<ImageGenerationResponse> {
    return this.request<ImageGenerationResponse>('/api/image/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
}

// Export singleton instance creator
export function createZantaraSDK(config: ZantaraSDKConfig): ZantaraSDK {
  return new ZantaraSDK(config);
}


