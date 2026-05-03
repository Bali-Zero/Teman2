/**
 * Prime Intelligence API Client
 * Handles zone analysis, intelligence data, and investment analysis
 * for the Prime 3D map interface.
 */

import type { IApiClient } from "../types/api-client.types";

// --- Types ---

export interface AnalyzeRequest {
  lat: number;
  lng: number;
  kbli_code?: string;
  is_pma?: boolean;
}

export interface AnalysisResult {
  can_invest: boolean;
  risk_level: string;
  score: number;
  label: "GREEN" | "YELLOW" | "RED";
  breakdown: Record<string, Record<string, unknown>>;
  modifiers: string[];
  hard_blocks: string[];
  [key: string]: unknown;
}

export interface IntelligenceFeature {
  type: string;
  geometry: { type: string; coordinates: [number, number] };
  properties: {
    id: number;
    name: string;
    entity_type: "company" | "client";
    zone_code: string | null;
    zone_name: string | null;
    kbli_code: string | null;
    [key: string]: unknown;
  };
}

export interface IntelligenceData {
  type: string;
  features: IntelligenceFeature[];
  stats: Record<string, number>;
}

// --- API Class ---

export class PrimeApi {
  constructor(private client: IApiClient) {}

  /**
   * Analyze a point on the map for investment viability.
   * Generic T allows consumer to provide its own result type.
   */
  async analyze<T = AnalysisResult>(request: AnalyzeRequest): Promise<T> {
    return this.client.request<T>("/api/prime/v2/analyze", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  /**
   * Fetch intelligence data (companies/clients) within map bounds.
   * Generic T allows consumer to provide its own data type.
   */
  async getIntelligence<T = IntelligenceData>(bounds: {
    sw_lat: number;
    sw_lng: number;
    ne_lat: number;
    ne_lng: number;
  }): Promise<T> {
    const params = new URLSearchParams({
      sw_lat: String(bounds.sw_lat),
      sw_lng: String(bounds.sw_lng),
      ne_lat: String(bounds.ne_lat),
      ne_lng: String(bounds.ne_lng),
    });
    return this.client.request<T>(
      `/api/prime/v2/intelligence?${params.toString()}`,
    );
  }
}
