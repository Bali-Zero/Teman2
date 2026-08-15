import { ApiClientBase } from "./client";
import { knownPmaRawStatus } from "../kbli-provenance";

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

export type KBLIRelatedRequirements = Record<string, string[]>;

export interface KBLIPmaDisclosure {
  pma_status: string;
  pma_max_asing: number | string | null;
  pma_verification_status: string;
  pma_official_basis: string | null;
  pma_source_vintage: string | null;
}

export function isApiPmaVerdictVerified(record: KBLIPmaDisclosure): boolean {
  const basis = record.pma_official_basis;
  const vintage = record.pma_source_vintage;
  return (
    record.pma_verification_status === "located" &&
    !!knownPmaRawStatus(record.pma_status) &&
    typeof basis === "string" &&
    !!basis.trim() &&
    typeof vintage === "string" &&
    !!vintage.trim()
  );
}

export function apiPmaStatusLabel(record: KBLIPmaDisclosure): string {
  return isApiPmaVerdictVerified(record)
    ? record.pma_status
    : "PMA not verified";
}

export interface KBLIDetail extends KBLIPmaDisclosure {
  code: string;
  title: string;
  description: string;
  licensing_status: string;
  sector: string;
  risk_profile: string;
  licenses: KBLILicense[];
  related_requirements: KBLIRelatedRequirements;
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

export interface KBLISearchResult extends KBLIPmaDisclosure {
  code: string;
  title: string;
  description: string;
  score: number;
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
