"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Users, Plus, X, Shield, ShieldAlert, ChevronDown } from "lucide-react";
import { toast } from "sonner";
import * as hrApi from "@/lib/api/hr/hr";
import { useTeamMembers } from "@/hooks/useTeamMembers";
import type { HREmployee, EmployeeCreatePayload, PTKPStatus } from "@/types/hr";

const PTKP_OPTIONS: PTKPStatus[] = [
  "TK/0",
  "TK/1",
  "TK/2",
  "TK/3",
  "K/0",
  "K/1",
  "K/2",
  "K/3",
];

function formatIDR(amount: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("id-ID", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const INITIAL_FORM: EmployeeCreatePayload = {
  team_member_id: "",
  hire_date: "",
  base_salary_idr: 0,
  bank_name: "",
  bank_account: "",
  bank_account_holder: "",
  npwp: "",
  ptkp_status: "TK/0",
  bpjs_kesehatan_number: "",
  bpjs_ketenagakerjaan_number: "",
  notes: "",
};

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<HREmployee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState<EmployeeCreatePayload>({ ...INITIAL_FORM });
  const { data: teamMembers = [], isLoading: loadingTeam } = useTeamMembers();

  const fetchEmployees = useCallback(async () => {
    try {
      setError(null);
      const data = await hrApi.listEmployees();
      setEmployees(data.employees || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load employees");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEmployees();
  }, [fetchEmployees]);

  const handleFieldChange = (
    field: keyof EmployeeCreatePayload,
    value: string | number,
  ) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      !form.team_member_id.trim() ||
      !form.hire_date ||
      !form.base_salary_idr
    ) {
      setFormError("Team member ID, hire date, and base salary are required.");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const payload: EmployeeCreatePayload = {
        ...form,
        base_salary_idr: Number(form.base_salary_idr),
      };
      const result = await hrApi.upsertEmployee(payload);
      if (result.employee) {
        setEmployees((prev) => {
          const idx = prev.findIndex((e) => e.id === result.employee.id);
          if (idx >= 0) {
            const updated = [...prev];
            updated[idx] = result.employee;
            return updated;
          }
          return [...prev, result.employee];
        });
      }
      toast.success("Employee saved successfully");
      setForm({ ...INITIAL_FORM });
      setShowForm(false);
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : "Failed to save employee",
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-100">Employees</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-zinc-900 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-100">Employees</h1>
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-red-400">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-100">Employees</h1>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <Users size={16} />
            {employees.length} total
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bz-accent)]/10 text-[var(--bz-accent)] hover:bg-[var(--bz-accent)]/20 text-sm transition-colors"
          >
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? "Cancel" : "Add Employee"}
          </button>
        </div>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="bg-zinc-900 border border-[var(--bz-accent)]/30 rounded-xl p-5 space-y-4"
        >
          <h2 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">
            New Employee
          </h2>

          {formError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-red-400">
              {formError}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                Team Member *
              </label>
              <div className="relative">
                <select
                  value={form.team_member_id}
                  onChange={(e) =>
                    handleFieldChange("team_member_id", e.target.value)
                  }
                  disabled={loadingTeam}
                  className="w-full appearance-none bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-[var(--bz-accent)]/50"
                  required
                >
                  <option value="">
                    {loadingTeam ? "Loading..." : "Select team member"}
                  </option>
                  {teamMembers.map((m) => (
                    <option key={m.id ?? m.email} value={m.id ?? ""}>
                      {m.full_name ?? m.email} ({m.role ?? "member"})
                    </option>
                  ))}
                </select>
                <ChevronDown
                  size={14}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                Hire Date *
              </label>
              <input
                type="date"
                value={form.hire_date}
                onChange={(e) => handleFieldChange("hire_date", e.target.value)}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-[var(--bz-accent)]/50"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                Base Salary (IDR) *
              </label>
              <input
                type="number"
                value={form.base_salary_idr || ""}
                onChange={(e) =>
                  handleFieldChange("base_salary_idr", Number(e.target.value))
                }
                placeholder="5000000"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
                min={0}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                Bank Name
              </label>
              <input
                type="text"
                value={form.bank_name || ""}
                onChange={(e) => handleFieldChange("bank_name", e.target.value)}
                placeholder="e.g. BCA, Mandiri"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                Bank Account
              </label>
              <input
                type="text"
                value={form.bank_account || ""}
                onChange={(e) =>
                  handleFieldChange("bank_account", e.target.value)
                }
                placeholder="Account number"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                Account Holder
              </label>
              <input
                type="text"
                value={form.bank_account_holder || ""}
                onChange={(e) =>
                  handleFieldChange("bank_account_holder", e.target.value)
                }
                placeholder="Name on account"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">NPWP</label>
              <input
                type="text"
                value={form.npwp || ""}
                onChange={(e) => handleFieldChange("npwp", e.target.value)}
                placeholder="Tax ID number"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
              />
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                PTKP Status
              </label>
              <div className="relative">
                <select
                  value={form.ptkp_status || "TK/0"}
                  onChange={(e) =>
                    handleFieldChange("ptkp_status", e.target.value)
                  }
                  className="w-full appearance-none bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-[var(--bz-accent)]/50"
                >
                  {PTKP_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
                <ChevronDown
                  size={14}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 pointer-events-none"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                BPJS Kesehatan
              </label>
              <input
                type="text"
                value={form.bpjs_kesehatan_number || ""}
                onChange={(e) =>
                  handleFieldChange("bpjs_kesehatan_number", e.target.value)
                }
                placeholder="BPJS health number"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-zinc-400 mb-1">
                BPJS Ketenagakerjaan
              </label>
              <input
                type="text"
                value={form.bpjs_ketenagakerjaan_number || ""}
                onChange={(e) =>
                  handleFieldChange(
                    "bpjs_ketenagakerjaan_number",
                    e.target.value,
                  )
                }
                placeholder="BPJS employment number"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
              />
            </div>
            <div className="md:col-span-2">
              <label className="block text-xs text-zinc-400 mb-1">Notes</label>
              <input
                type="text"
                value={form.notes || ""}
                onChange={(e) => handleFieldChange("notes", e.target.value)}
                placeholder="Optional notes"
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-[var(--bz-accent)]/50"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-[var(--bz-accent)] text-zinc-950 text-sm font-medium hover:bg-[var(--bz-accent)]/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? "Saving..." : "Save Employee"}
            </button>
          </div>
        </form>
      )}

      {employees.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
          No employees registered yet. Click &quot;Add Employee&quot; to get
          started.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-500 uppercase tracking-wider border-b border-zinc-800">
                <th className="text-left px-4 py-3">Name</th>
                <th className="text-left px-4 py-3">Email</th>
                <th className="text-left px-4 py-3">Role</th>
                <th className="text-right px-4 py-3">Base Salary</th>
                <th className="text-left px-4 py-3">Hire Date</th>
                <th className="text-center px-4 py-3">BPJS</th>
                <th className="text-center px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => {
                const hasBpjs = !!(
                  emp.bpjs_kesehatan_number && emp.bpjs_ketenagakerjaan_number
                );
                return (
                  <tr
                    key={emp.id}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="px-4 py-3 text-zinc-200 font-medium">
                      {emp.full_name}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{emp.email}</td>
                    <td className="px-4 py-3 text-zinc-400 capitalize">
                      {emp.role}
                    </td>
                    <td className="px-4 py-3 text-right text-[var(--bz-accent)] font-medium tabular-nums">
                      {formatIDR(emp.base_salary_idr)}
                    </td>
                    <td className="px-4 py-3 text-zinc-400 tabular-nums">
                      {formatDate(emp.hire_date)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div
                        className="flex items-center justify-center gap-1.5"
                        title={hasBpjs ? "BPJS complete" : "BPJS missing"}
                      >
                        {hasBpjs ? (
                          <Shield size={16} className="text-emerald-400" />
                        ) : (
                          <ShieldAlert size={16} className="text-red-400" />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`inline-block text-xs px-2 py-0.5 rounded-full border ${
                          emp.is_active
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                            : "bg-zinc-500/10 text-zinc-400 border-zinc-500/30"
                        }`}
                      >
                        {emp.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
