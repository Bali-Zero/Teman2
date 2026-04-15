/**
 * Workspace LKPM API
 * Team-side endpoints for batch management, alerts, ready packs
 *
 * NOTE: Backend LKPM endpoints return flat responses like {success, items, ...}
 * NOT wrapped in PortalApiResponse {success, data: {...}}
 */

import { api } from "@/lib/api";
import type {
  LKPMBatchItem,
  LKPMValidationAlert,
  LKPMDeadline,
  LKPMReadyPack,
  LKPMOSSCredentials,
  LKPMReceipt,
} from "../portal/portal.types";

export const lkpmApi = {
  async getBatch(
    quarter: string,
    year: number,
  ): Promise<{ count: number; items: LKPMBatchItem[] }> {
    const r = await api.get<{
      success: boolean;
      count: number;
      items: LKPMBatchItem[];
    }>(`/api/v1/lkpm/batch/${quarter}?year=${year}`);
    return { count: r.count ?? 0, items: r.items ?? [] };
  },

  async getClientHistory(
    clientId: number,
  ): Promise<{ count: number; items: LKPMBatchItem[] }> {
    const r = await api.get<{
      success: boolean;
      count: number;
      items: LKPMBatchItem[];
    }>(`/api/v1/lkpm/history/${clientId}`);
    return { count: r.count ?? 0, items: r.items ?? [] };
  },

  /**
   * Workspace TaxTab: fetch OSS tanda terima for every company where the
   * client is a shareholder/director/commissioner. Cascade happens server-side
   * via `client_company_links`. Mirrors `/receipts/me` on the portal side.
   */
  async getClientReceipts(
    clientId: number,
  ): Promise<{ count: number; items: LKPMReceipt[] }> {
    const r = await api.get<{
      success: boolean;
      count: number;
      items: LKPMReceipt[];
    }>(`/api/v1/lkpm/receipts/by-client/${clientId}`);
    return { count: r.count ?? 0, items: r.items ?? [] };
  },

  /**
   * Workspace LKPM detail: receipts attached to a single lkpm_reports row.
   */
  async getReportReceipts(
    lkpmReportId: number,
  ): Promise<{ count: number; items: LKPMReceipt[] }> {
    const r = await api.get<{
      success: boolean;
      count: number;
      items: LKPMReceipt[];
    }>(`/api/v1/lkpm/receipts/${lkpmReportId}`);
    return { count: r.count ?? 0, items: r.items ?? [] };
  },

  async getAlerts(): Promise<LKPMValidationAlert[]> {
    const r = await api.get<{
      success: boolean;
      alerts: LKPMValidationAlert[];
    }>("/api/v1/lkpm/alerts");
    return r.alerts ?? [];
  },

  async getDeadlines(daysAhead: number = 30): Promise<LKPMDeadline[]> {
    const r = await api.get<{ success: boolean; deadlines: LKPMDeadline[] }>(
      `/api/v1/lkpm/deadlines?days_ahead=${daysAhead}`,
    );
    return r.deadlines ?? [];
  },

  async getReadyPack(draftId: number): Promise<LKPMReadyPack> {
    const r = await api.get<{ success: boolean; ready_pack: LKPMReadyPack }>(
      `/api/v1/lkpm/ready-pack/${draftId}`,
    );
    return r.ready_pack;
  },

  async validateDraft(draftId: number): Promise<{
    is_valid: boolean;
    red_count: number;
    yellow_count: number;
    green_count: number;
    alerts: LKPMValidationAlert[];
  }> {
    return api.post<{
      success: boolean;
      is_valid: boolean;
      red_count: number;
      yellow_count: number;
      green_count: number;
      alerts: LKPMValidationAlert[];
    }>(`/api/v1/lkpm/validate/${draftId}`);
  },

  async markSubmitted(draftId: number): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>(
      `/api/v1/lkpm/mark-submitted/${draftId}`,
    );
  },

  async uploadReceipt(
    draftId: number,
    receiptNumber: string,
  ): Promise<{ success: boolean }> {
    return api.post<{ success: boolean }>(
      `/api/v1/lkpm/upload-receipt/${draftId}`,
      { receipt_number: receiptNumber },
    );
  },

  async syncJurnal(
    clientId: number,
    quarter: string,
    year: number,
  ): Promise<{ draft_id: number; realized_total: number }> {
    return api.post<{
      success: boolean;
      draft_id: number;
      realized_total: number;
    }>(`/api/v1/lkpm/sync-jurnal/${clientId}`, { quarter, year });
  },

  /**
   * Assign (or clear) an LKPM report to a tax consultant.
   * Pass null to clear the assignment.
   * Backend: PUT /api/v1/lkpm/reports/{draft_id}/assign  (admin-only RBAC)
   */
  async assignReport(
    draftId: number,
    lkpmAssignedTo: string | null,
  ): Promise<{ draft_id: number; lkpm_assigned_to: string | null }> {
    const r = await api.put<{
      success: boolean;
      draft_id: number;
      lkpm_assigned_to: string | null;
    }>(`/api/v1/lkpm/reports/${draftId}/assign`, {
      lkpm_assigned_to: lkpmAssignedTo,
    });
    return { draft_id: r.draft_id, lkpm_assigned_to: r.lkpm_assigned_to };
  },

  /**
   * Fetch OSS credentials (plaintext) for a company.
   * Backend: GET /api/v1/lkpm/credentials/{client_id}
   * RBAC: admin OR the tax consultant assigned to a LKPM report for this client.
   */
  async getCredentials(clientId: number): Promise<LKPMOSSCredentials> {
    const r = await api.get<LKPMOSSCredentials & { success: boolean }>(
      `/api/v1/lkpm/credentials/${clientId}`,
    );
    return {
      client_id: r.client_id,
      company_name: r.company_name,
      oss_username: r.oss_username,
      oss_password: r.oss_password,
      oss_creds_updated_at: r.oss_creds_updated_at,
      oss_creds_updated_by: r.oss_creds_updated_by,
    };
  },
};
