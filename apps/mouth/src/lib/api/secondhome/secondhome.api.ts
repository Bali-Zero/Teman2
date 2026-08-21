import type { IApiClient } from "../types/api-client.types";
import type {
  AddEvidenceParams,
  AdvanceCaseParams,
  CaseDetail,
  CaseListResponse,
  CreateCaseParams,
  ListCasesParams,
  SecondHomeSummary,
} from "./secondhome.types";

/**
 * E33 Second Home internal-console API module.
 *
 * Constructor-injection mirror of `CrmApi` (see `crm/crm.api.ts`). Endpoints
 * are the FIXED contracts from SPEC-e33-internal-console.md PR-1 —
 * `apps/backend-rag/backend/app/routers/e33_cases.py`.
 */
export class SecondHomeApi {
  constructor(private client: IApiClient) {}

  /** POST /api/e33/cases → 201 CaseDetail */
  async createCase(data: CreateCaseParams): Promise<CaseDetail> {
    return this.client.request<CaseDetail>(
      "/api/e33/cases",
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      60000, // creation — same timeout budget as CrmApi.createPractice
    );
  }

  /** GET /api/e33/cases → {cases, total} */
  async listCases(params: ListCasesParams = {}): Promise<CaseListResponse> {
    const queryParams = new URLSearchParams();
    if (params.stage) queryParams.append("stage", params.stage);
    if (params.client_id !== undefined) {
      queryParams.append("client_id", params.client_id.toString());
    }
    if (params.basis) queryParams.append("basis", params.basis);
    if (params.active_only !== undefined) {
      queryParams.append("active_only", String(params.active_only));
    }

    const queryString = queryParams.toString();
    const url = `/api/e33/cases${queryString ? `?${queryString}` : ""}`;

    return this.client.request<CaseListResponse>(url);
  }

  /** GET /api/e33/cases/{case_id} → CaseDetail */
  async getCase(caseId: string): Promise<CaseDetail> {
    return this.client.request<CaseDetail>(
      `/api/e33/cases/${encodeURIComponent(caseId)}`,
    );
  }

  /** POST /api/e33/cases/{case_id}/advance → 200 CaseDetail (409 on invalid transition) */
  async advanceCase(
    caseId: string,
    data: AdvanceCaseParams,
  ): Promise<CaseDetail> {
    return this.client.request<CaseDetail>(
      `/api/e33/cases/${encodeURIComponent(caseId)}/advance`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      30000,
    );
  }

  /** POST /api/e33/cases/{case_id}/evidence → 200 CaseDetail (422 on custody violation) */
  async addEvidence(
    caseId: string,
    data: AddEvidenceParams,
  ): Promise<CaseDetail> {
    return this.client.request<CaseDetail>(
      `/api/e33/cases/${encodeURIComponent(caseId)}/evidence`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      30000,
    );
  }

  /** GET /api/e33/summary → {by_stage, active_total, guarantee_due_30d, scan_switch} */
  async getSummary(): Promise<SecondHomeSummary> {
    return this.client.request<SecondHomeSummary>("/api/e33/summary");
  }
}
