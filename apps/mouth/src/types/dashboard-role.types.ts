import type { RoleAlert } from "./dashboard-role-alert.types";

export type { RoleAlert };

export interface ZeroMetrics {
  revenue_mtd: number;
  visti_scadenza: number;
  fatture_overdue: number;
  agenti_count: number;
  fly_uptime: number;
}

export interface TeamMetrics {
  assigned_cases: number;
  prossima_scadenza: string | null;
  doc_mancanti: number;
  clienti_assegnati: number;
  stalled_count: number;
}

export interface TaxMetrics {
  clienti_compliant: number;
  scadenze_7gg: number;
  dichiarazioni_pending: number;
  alert_pajak: number;
  prossima_scadenza: string | null;
}

export interface MarketingMetrics {
  articoli_pubblicati: number;
  articoli_in_review: number;
  subscriber_delta: number;
  lead_nuovi: number;
}

export interface AccountingMetrics {
  fatture_pagate_mtd: number;
  fatture_overdue: number;
  fatture_pending: number;
  ricavi_mtd: number;
  overdue_total: number;
}

export type RoleWidgetData =
  | { role: "zero"; metrics: ZeroMetrics; alerts: RoleAlert[] }
  | { role: "team"; metrics: TeamMetrics; alerts: RoleAlert[] }
  | { role: "tax"; metrics: TaxMetrics; alerts: RoleAlert[] }
  | { role: "marketing"; metrics: MarketingMetrics; alerts: RoleAlert[] }
  | { role: "accounting"; metrics: AccountingMetrics; alerts: RoleAlert[] };

export interface LiveActivityEvent {
  id: string;
  type: "critical" | "ok" | "warning" | "info" | "live";
  icon: string;
  text: string;
  tag?: string;
  timestamp: string;
  userId?: string;
}

export interface DashboardStatConfig {
  icon: string;
  value: number | string;
  label: string;
  trend: string;
  colorVariant: "green" | "red" | "yellow" | "blue";
}

export interface UseRoleMetricsResult {
  data: RoleWidgetData | undefined;
  isLoading: boolean;
  isError: boolean;
}
