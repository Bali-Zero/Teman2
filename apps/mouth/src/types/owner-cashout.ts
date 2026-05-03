export interface OwnerCashoutKpi {
  margin_bz_total_idr: number;
  margin_bz_last_week_idr: number;
  margin_bs_total_idr: number;
  practices_total: number;
  practices_last_week: number;
}

export interface OwnerCashoutTrendPoint {
  week_start: string; // ISO date
  margin_bz: number;
  margin_bs: number;
  practices: number;
}

export interface OwnerCashoutOverview {
  total_weeks: number;
  first_week: string | null;
  last_week: string | null;
  kpi: OwnerCashoutKpi;
  trend: OwnerCashoutTrendPoint[];
}

export interface OwnerCashoutWeek {
  id: number;
  week_start: string;
  tab_name_bz: string | null;
  tab_name_bs: string | null;
  total_practices: number;
  total_income_idr: number;
  total_margin_bz_idr: number;
  total_margin_bs_idr: number;
  last_synced_at: string;
}

export interface OwnerCashoutRow {
  entity: "BZ" | "BS";
  row_index: number;
  client_name: string;
  process: string | null;
  pnbp_idr: number;
  urgent_idr: number;
  rptka_imta_idr: number;
  total_income_idr: number;
  margin_bs_idr: number;
  margin_bz_idr: number;
  final_price_idr: number;
  note: string | null;
}

export interface OwnerCashoutSubtotal {
  process: string;
  count: number;
  margin_bz_idr: number;
}

export interface OwnerCashoutWeekDetail {
  week: OwnerCashoutWeek;
  rows_bz: OwnerCashoutRow[];
  rows_bs: OwnerCashoutRow[];
  subtotals_by_process: OwnerCashoutSubtotal[];
}

export interface OwnerCashoutVisaType {
  process: string;
  count: number;
  margin_bz_total_idr: number;
}

export interface OwnerCashoutSyncLog {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: "running" | "success" | "partial" | "failed";
  weeks_processed: number;
  weeks_skipped: number;
  rows_upserted: number;
  unknown_tabs: string | null;
  error: string | null;
  triggered_by: string;
}
