import { api } from "@/lib/api";
import type {
  OwnerCashoutOverview,
  OwnerCashoutVisaType,
  OwnerCashoutWeek,
  OwnerCashoutWeekDetail,
  OwnerCashoutSyncLog,
} from "@/types/owner-cashout";

const BASE = "/api/hr/owner/cashout";

export const getOverview = () =>
  api.get<OwnerCashoutOverview>(`${BASE}/overview`);

export const listWeeks = () =>
  api.get<{ weeks: OwnerCashoutWeek[] }>(`${BASE}/weeks`);

export const getWeekDetail = (weekId: number) =>
  api.get<OwnerCashoutWeekDetail>(`${BASE}/weeks/${weekId}`);

export const getVisaTypes = () =>
  api.get<{ top: OwnerCashoutVisaType[] }>(`${BASE}/visa-types`);

export const triggerSync = () =>
  api.post<{ status: string }>(`${BASE}/sync`);

export const getSyncStatus = () =>
  api.get<{ last_sync: OwnerCashoutSyncLog | null }>(`${BASE}/sync-status`);
