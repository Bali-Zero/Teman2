/**
 * HR/Payroll API client module
 * Uses the centralized api client for auth token management.
 */

import { api } from '@/lib/api';
import type {
  AdminDashboard,
  Bonus,
  BonusRate,
  BonusRatePayload,
  EmployeeCreatePayload,
  HREmployee,
  LeaveBalance,
  LeaveRequest,
  LeaveRequestPayload,
  LeaveType,
  PayrollPeriod,
  Payslip,
  PayslipDetail,
  PersonalDashboard,
  TeamLeaveSummaryRow,
} from '@/types/hr';

const BASE = '/api/hr';

function qs(params?: Record<string, string | number | null | undefined>): string {
  if (!params) return '';
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string | number] => entry[1] != null
  );
  return entries.length
    ? '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()
    : '';
}

// Dashboard
export const getDashboard = () => api.get<AdminDashboard>(`${BASE}/dashboard`);
export const getMyDashboard = () => api.get<PersonalDashboard>(`${BASE}/my-dashboard`);

// Employees
export const listEmployees = () =>
  api.get<{ employees: HREmployee[]; count: number }>(`${BASE}/employees`);
export const getEmployee = (id: number) => api.get<HREmployee>(`${BASE}/employees/${id}`);
export const upsertEmployee = (data: EmployeeCreatePayload) =>
  api.post<{ success: boolean; employee: HREmployee }>(`${BASE}/employees`, data);

// Bonus Rates
export const listBonusRates = () =>
  api.get<{ rates: BonusRate[]; count: number }>(`${BASE}/bonus-rates`);
export const upsertBonusRate = (data: BonusRatePayload) =>
  api.post<{ success: boolean; rate: BonusRate }>(`${BASE}/bonus-rates`, data);

// Bonuses
export const listBonuses = (params?: Record<string, string | number | null | undefined>) =>
  api.get<{ bonuses: Bonus[]; count: number }>(`${BASE}/bonuses${qs(params)}`);
export const approveBonus = (id: number) =>
  api.post<{ success: boolean; bonus: Bonus }>(`${BASE}/bonuses/${id}/approve`, {});

// Payroll
export const calculatePayroll = (month: number, year: number) =>
  api.post<{ success: boolean; period_id: number; employee_count: number }>(
    `${BASE}/payroll/calculate`,
    { month, year }
  );
export const listPayrollPeriods = () =>
  api.get<{ periods: PayrollPeriod[]; count: number }>(`${BASE}/payroll/periods`);
export const listPayslips = (params?: Record<string, string | number | null | undefined>) =>
  api.get<{ payslips: Payslip[]; count: number }>(`${BASE}/payslips${qs(params)}`);
export const getPayslipDetail = (id: number) => api.get<PayslipDetail>(`${BASE}/payslips/${id}`);
export const approvePayroll = (periodId: number) =>
  api.post<{ success: boolean; period: PayrollPeriod }>(`${BASE}/payroll/${periodId}/approve`, {});
export const markPayrollPaid = (periodId: number) =>
  api.post<{ success: boolean; period: PayrollPeriod }>(
    `${BASE}/payroll/${periodId}/mark-paid`,
    {}
  );

// Leave Types — backend /leave/types returns active rows only,
// projected to the columns the dropdown needs.
export type LeaveTypeOption = Pick<
  LeaveType,
  'id' | 'code' | 'name' | 'default_days' | 'is_paid' | 'requires_document'
>;

export const getLeaveTypes = () =>
  api.get<{ leave_types: LeaveTypeOption[] }>(`${BASE}/leave/types`);

// Leave
export const requestLeave = (data: LeaveRequestPayload) =>
  api.post<{ success: boolean; request: LeaveRequest }>(`${BASE}/leave/request`, data);
export const listLeaveRequests = (params?: Record<string, string | number | null | undefined>) =>
  api.get<{ requests: LeaveRequest[]; count: number }>(`${BASE}/leave/requests${qs(params)}`);
export const getLeaveBalance = (params?: Record<string, string | number | null | undefined>) =>
  api.get<{ balances: LeaveBalance[] }>(`${BASE}/leave/balance${qs(params)}`);
export const getTeamLeaveSummary = (params?: Record<string, string | number | null | undefined>) =>
  api.get<{ summary: TeamLeaveSummaryRow[] }>(`${BASE}/leave/team-summary${qs(params)}`);
export const approveLeave = (id: number) =>
  api.post<{ success: boolean; request: LeaveRequest }>(`${BASE}/leave/${id}/approve`, {});
export const rejectLeave = (id: number, reason?: string) =>
  api.post<{ success: boolean; request: LeaveRequest }>(`${BASE}/leave/${id}/reject`, { reason });
