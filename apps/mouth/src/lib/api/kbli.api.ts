import { ApiClientBase } from "./client";

export interface KBLILicense {
  type: string;
  scale: string[];
  risk_level: string;
  sla: string;
  requirements: string[];
}

export interface KBLISource {
  chunk_id: string;
  content: string;
  metadata: {
    kode_kbli?: string;
    judul?: string;
    source?: string;
  };
  score: number;
}

export interface KBLIDetail {
  code: string;
  title: string;
  description: string;
  pma_status: string;
  licensing_status: string;
  sector: string;
  risk_profile: string;
  licenses: KBLILicense[];
  related_codes: string[];
  intel?: {
    whatItMeans: string;
    whatYouNeed: string;
    whatChanged: string;
    baliContext: string;
    zantaraOpener: string;
    youllAlsoNeed?: string;
  };
}

export interface KBLISearchResult {
  code: string;
  title: string;
  description: string;
  score: number;
  pma_status: string;
  risk_category: string;
}

export class KBLIApi extends ApiClientBase {
  constructor(baseUrl: string) {
    super(baseUrl);
  }

  async search(query: string): Promise<KBLISearchResult[]> {
    return this.request<KBLISearchResult[]>(
      `/api/v1/kbli-notebook/search?query=${encodeURIComponent(query)}`,
    );
  }

  async inspect(code: string): Promise<KBLIDetail> {
    return this.request<KBLIDetail>(`/api/v1/kbli-notebook/inspect/${code}`);
  }

  async chat(
    query: string,
    sessionId?: string,
  ): Promise<{
    answer: string;
    detected_kbli: string[];
    results: KBLISearchResult[];
    sources: KBLISource[];
    suggested_queries: string[];
  }> {
    return this.post<{
      answer: string;
      detected_kbli: string[];
      results: KBLISearchResult[];
      sources: KBLISource[];
      suggested_queries: string[];
    }>("/api/v1/kbli-notebook/chat", {
      query,
      session_id: sessionId,
    });
  }
}

// Export a singleton instance if we are in the browser
const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";
export const kbliApi = new KBLIApi(baseUrl);
