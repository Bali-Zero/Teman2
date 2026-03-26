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
};
