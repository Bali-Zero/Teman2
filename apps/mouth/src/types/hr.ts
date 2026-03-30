/**
 * HR/Payroll TypeScript types.
 * Maps to backend Pydantic models and DB schema (migration_068).
 */

// ─── Enums ────────────────────────────────────────────────────────────

export type BonusStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "paid"
  | "reversed";
export type PayrollStatus = "draft" | "calculated" | "approved" | "paid";
export type LeaveStatus = "pending" | "approved" | "rejected" | "cancelled";
export type PTKPStatus =
  | "TK/0"
  | "TK/1"
  | "TK/2"
  | "TK/3"
  | "K/0"
  | "K/1"
  | "K/2"
  | "K/3";

// ─── Employees ────────────────────────────────────────────────────────

export interface HREmployee {
  id: number;
  team_member_id: string;
  full_name: string;
  email: string;
  role: string;
  hire_date: string;
  base_salary_idr: number;
  bank_name: string | null;
  bank_account: string | null;
  bank_account_holder: string | null;
  npwp: string | null;
  ptkp_status: PTKPStatus;
  bpjs_kesehatan_number: string | null;
  bpjs_ketenagakerjaan_number: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmployeeCreatePayload {
  team_member_id: string;
  hire_date: string;
  base_salary_idr: number;
  bank_name?: string;
  bank_account?: string;
  bank_account_holder?: string;
  npwp?: string;
  ptkp_status?: PTKPStatus;
  bpjs_kesehatan_number?: string;
  bpjs_ketenagakerjaan_number?: string;
  notes?: string;
}

// ─── Bonus Rates ──────────────────────────────────────────────────────

export interface BonusRate {
  id: number;
  practice_type_code: string;
  practice_type_name: string | null;
  amount_idr: number;
  effective_from: string;
  effective_to: string | null;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface BonusRatePayload {
  practice_type_code: string;
  amount_idr: number;
  effective_from?: string;
  effective_to?: string;
  is_active?: boolean;
  notes?: string;
}

// ─── Bonuses ──────────────────────────────────────────────────────────

export interface Bonus {
  id: number;
  practice_id: number;
  employee_id: number;
  payroll_period_id: number | null;
  bonus_rate_id: number | null;
  practice_type_code: string;
  amount_idr: number;
  status: BonusStatus;
  awarded_at: string;
  awarded_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  employee_name: string;
  employee_email: string;
  practice_status: string;
  client_name: string | null;
  notes: string | null;
}

// ─── Payroll ──────────────────────────────────────────────────────────

export interface PayrollPeriod {
  id: number;
  payroll_month: number;
  payroll_year: number;
  period_start: string;
  period_end: string;
  status: PayrollStatus;
  locked_at: string | null;
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  paid_at: string | null;
  notes: string | null;
  payslip_count: number;
  total_net: number;
}

export interface Payslip {
  id: number;
  payroll_period_id: number;
  employee_id: number;
  base_salary_idr: number;
  bonus_total_idr: number;
  allowance_total_idr: number;
  deduction_total_idr: number;
  thr_idr: number;
  net_salary_idr: number;
  employee_name: string;
  employee_email: string;
  payroll_month: number;
  payroll_year: number;
  period_status: PayrollStatus;
  notes: string | null;
}

export interface PayslipDetail extends Payslip {
  full_name: string;
  email: string;
  deductions: Deduction[];
}

export interface Deduction {
  id: number;
  payslip_id: number;
  deduction_type: string;
  label: string;
  amount_idr: number;
  is_employer: boolean;
}

// ─── Leave ────────────────────────────────────────────────────────────

export interface LeaveType {
  id: number;
  code: string;
  name: string;
  description: string | null;
  default_days: number;
  is_paid: boolean;
  requires_document: boolean;
  is_active: boolean;
}

export interface LeaveBalance {
  id: number;
  employee_id: number;
  leave_type_id: number;
  leave_type_name: string;
  code: string;
  is_paid: boolean;
  balance_year: number;
  allocated_days: number;
  carried_over: number;
  used_days: number;
  pending_days: number;
  name?: string; // alias from query
}

export interface LeaveRequest {
  id: number;
  employee_id: number;
  leave_type_id: number;
  leave_type_name: string;
  start_date: string;
  end_date: string;
  total_days: number;
  reason: string | null;
  status: LeaveStatus;
  requested_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  rejection_reason: string | null;
  employee_name: string;
  employee_email: string;
}

export interface LeaveRequestPayload {
  leave_type_id: number;
  start_date: string;
  end_date: string;
  total_days: number;
  reason?: string;
}

// ─── Dashboard ────────────────────────────────────────────────────────

export interface AdminDashboard {
  employee_count: number;
  pending_bonuses: { count: number; total: number };
  pending_leave_requests: number;
  current_period: {
    id: number;
    status: PayrollStatus;
    payroll_month: number;
    payroll_year: number;
  } | null;
  month: number;
  year: number;
}

export interface PersonalDashboard {
  month_bonuses: { count: number; total: number };
  latest_payslip: {
    net_salary_idr: number;
    payroll_month: number;
    payroll_year: number;
  } | null;
  leave_balances: LeaveBalance[];
}

// ─── API Response Wrappers ────────────────────────────────────────────

export interface ListResponse<T> {
  count: number;
  [key: string]: T[] | number;
}

export interface MutationResponse<T = unknown> {
  success: boolean;
  [key: string]: T | boolean;
}
