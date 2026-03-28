/**
 * HR/Payroll API client module
 * Uses the centralized api client for auth token management.
 */

import { api } from "@/lib/api";

const BASE = "/api/hr";

function qs(params?: Record<string, any>): string {
  if (!params) return "";
  const entries = Object.entries(params).filter(([, v]) => v != null);
  return entries.length
    ? "?" +
        new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()
    : "";
}

// Dashboard
export const getDashboard = () => api.get<any>(`${BASE}/dashboard`);
export const getMyDashboard = () => api.get<any>(`${BASE}/my-dashboard`);

// Employees
export const listEmployees = () => api.get<any>(`${BASE}/employees`);
export const getEmployee = (id: number) =>
  api.get<any>(`${BASE}/employees/${id}`);
export const upsertEmployee = (data: any) =>
  api.post<any>(`${BASE}/employees`, data);

// Bonus Rates
export const listBonusRates = () => api.get<any>(`${BASE}/bonus-rates`);
export const upsertBonusRate = (data: any) =>
  api.post<any>(`${BASE}/bonus-rates`, data);

// Bonuses
export const listBonuses = (params?: Record<string, any>) =>
  api.get<any>(`${BASE}/bonuses${qs(params)}`);
export const approveBonus = (id: number) =>
  api.post<any>(`${BASE}/bonuses/${id}/approve`, {});

// Payroll
export const calculatePayroll = (month: number, year: number) =>
  api.post<any>(`${BASE}/payroll/calculate`, { month, year });
export const listPayrollPeriods = () => api.get<any>(`${BASE}/payroll/periods`);
export const listPayslips = (params?: Record<string, any>) =>
  api.get<any>(`${BASE}/payslips${qs(params)}`);
export const getPayslipDetail = (id: number) =>
  api.get<any>(`${BASE}/payslips/${id}`);
export const approvePayroll = (periodId: number) =>
  api.post<any>(`${BASE}/payroll/${periodId}/approve`, {});
export const markPayrollPaid = (periodId: number) =>
  api.post<any>(`${BASE}/payroll/${periodId}/mark-paid`, {});

// Leave
export const requestLeave = (data: any) =>
  api.post<any>(`${BASE}/leave/request`, data);
export const listLeaveRequests = (params?: Record<string, any>) =>
  api.get<any>(`${BASE}/leave/requests${qs(params)}`);
export const getLeaveBalance = (params?: Record<string, any>) =>
  api.get<any>(`${BASE}/leave/balance${qs(params)}`);
export const approveLeave = (id: number) =>
  api.post<any>(`${BASE}/leave/${id}/approve`, {});
export const rejectLeave = (id: number, reason?: string) =>
  api.post<any>(`${BASE}/leave/${id}/reject`, { reason });
