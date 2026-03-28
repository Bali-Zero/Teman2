/**
 * HR/Payroll API client module
 */

const BASE = "/api/hr";

async function fetchHR<T>(path: string, options?: RequestInit): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("nz_token") : null;
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HR API error ${res.status}`);
  }
  return res.json();
}

// Dashboard
export const getDashboard = () => fetchHR<any>("/dashboard");
export const getMyDashboard = () => fetchHR<any>("/my-dashboard");

// Employees
export const listEmployees = () => fetchHR<any>("/employees");
export const getEmployee = (id: number) => fetchHR<any>(`/employees/${id}`);
export const upsertEmployee = (data: any) =>
  fetchHR<any>("/employees", { method: "POST", body: JSON.stringify(data) });

// Bonus Rates
export const listBonusRates = () => fetchHR<any>("/bonus-rates");
export const upsertBonusRate = (data: any) =>
  fetchHR<any>("/bonus-rates", { method: "POST", body: JSON.stringify(data) });

// Bonuses
export const listBonuses = (params?: Record<string, any>) => {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  return fetchHR<any>(`/bonuses${qs}`);
};
export const approveBonus = (id: number) =>
  fetchHR<any>(`/bonuses/${id}/approve`, { method: "POST" });

// Payroll
export const calculatePayroll = (month: number, year: number) =>
  fetchHR<any>("/payroll/calculate", {
    method: "POST",
    body: JSON.stringify({ month, year }),
  });
export const listPayrollPeriods = () => fetchHR<any>("/payroll/periods");
export const listPayslips = (params?: Record<string, any>) => {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  return fetchHR<any>(`/payslips${qs}`);
};
export const getPayslipDetail = (id: number) => fetchHR<any>(`/payslips/${id}`);
export const approvePayroll = (periodId: number) =>
  fetchHR<any>(`/payroll/${periodId}/approve`, { method: "POST" });
export const markPayrollPaid = (periodId: number) =>
  fetchHR<any>(`/payroll/${periodId}/mark-paid`, { method: "POST" });

// Leave
export const requestLeave = (data: any) =>
  fetchHR<any>("/leave/request", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const listLeaveRequests = (params?: Record<string, any>) => {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  return fetchHR<any>(`/leave/requests${qs}`);
};
export const getLeaveBalance = (params?: Record<string, any>) => {
  const qs = params
    ? "?" +
      new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v != null)
          .map(([k, v]) => [k, String(v)]),
      ).toString()
    : "";
  return fetchHR<any>(`/leave/balance${qs}`);
};
export const approveLeave = (id: number) =>
  fetchHR<any>(`/leave/${id}/approve`, { method: "POST" });
export const rejectLeave = (id: number, reason?: string) =>
  fetchHR<any>(`/leave/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
