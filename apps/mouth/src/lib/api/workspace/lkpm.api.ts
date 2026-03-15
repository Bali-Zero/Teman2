/**
 * Workspace LKPM API
 * Team-side endpoints for batch management, alerts, ready packs
 */

import { api } from "@/lib/api";
import type {
  LKPMBatchItem,
  LKPMValidationAlert,
  LKPMDeadline,
  LKPMReadyPack,
  PortalApiResponse,
} from "../portal/portal.types";

export const lkpmApi = {
  async getBatch(
    quarter: string,
    year: number,
  ): Promise<{ count: number; items: LKPMBatchItem[] }> {
    return api.get<PortalApiResponse<{ count: number; items: LKPMBatchItem[] }>>(
      `/api/v1/lkpm/batch/${quarter}?year=${year}`,
    ).then((r) => r.data!);
  },

  async getAlerts(): Promise<LKPMValidationAlert[]> {
    return api.get<PortalApiResponse<{ alerts: LKPMValidationAlert[] }>>(
      "/api/v1/lkpm/alerts",
    ).then((r) => r.data?.alerts ?? []);
  },

  async getDeadlines(daysAhead: number = 30): Promise<LKPMDeadline[]> {
    return api.get<PortalApiResponse<{ deadlines: LKPMDeadline[] }>>(
      `/api/v1/lkpm/deadlines?days_ahead=${daysAhead}`,
    ).then((r) => r.data?.deadlines ?? []);
  },

  async getReadyPack(draftId: number): Promise<LKPMReadyPack> {
    return api.get<PortalApiResponse<{ ready_pack: LKPMReadyPack }>>(
      `/api/v1/lkpm/ready-pack/${draftId}`,
    ).then((r) => r.data!.ready_pack);
  },

  async validateDraft(draftId: number): Promise<{
    is_valid: boolean;
    red_count: number;
    yellow_count: number;
    green_count: number;
    alerts: LKPMValidationAlert[];
  }> {
    return api.post<PortalApiResponse<{
      is_valid: boolean;
      red_count: number;
      yellow_count: number;
      green_count: number;
      alerts: LKPMValidationAlert[];
    }>>(`/api/v1/lkpm/validate/${draftId}`).then((r) => r.data!);
  },

  async markSubmitted(draftId: number): Promise<{ success: boolean }> {
    return api.post<PortalApiResponse<void>>(
      `/api/v1/lkpm/mark-submitted/${draftId}`,
    ).then((r) => ({ success: r.success }));
  },

  async uploadReceipt(
    draftId: number,
    receiptNumber: string,
  ): Promise<{ success: boolean }> {
    return api.post<PortalApiResponse<void>>(
      `/api/v1/lkpm/upload-receipt/${draftId}`,
      { receipt_number: receiptNumber },
    ).then((r) => ({ success: r.success }));
  },

  async syncJurnal(
    clientId: number,
    quarter: string,
    year: number,
  ): Promise<{ draft_id: number; realized_total: number }> {
    return api.post<PortalApiResponse<{ draft_id: number; realized_total: number }>>(
      `/api/v1/lkpm/sync-jurnal/${clientId}`,
      { quarter, year },
    ).then((r) => r.data!);
  },
};
