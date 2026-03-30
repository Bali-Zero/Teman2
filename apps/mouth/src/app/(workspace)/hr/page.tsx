"use client";

import React, { useEffect, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { Gift, Banknote, Calendar, Users } from "lucide-react";
import * as hrApi from "@/lib/api/hr/hr";
import type { AdminDashboard, PersonalDashboard } from "@/types/hr";

function formatIDR(amount: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
  color: string;
}) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
      <div className="flex items-center gap-3 mb-3">
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon size={20} />
        </div>
        <span className="text-sm text-zinc-400">{label}</span>
      </div>
      <div className="text-2xl font-bold text-zinc-100">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

function AdminDashboardView({ data }: { data: AdminDashboard }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-100">HR Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Users}
          label="Active Employees"
          value={String(data.employee_count || 0)}
          color="bg-blue-500/10 text-blue-400"
        />
        <StatCard
          icon={Gift}
          label="Pending Bonuses"
          value={String(data.pending_bonuses?.count || 0)}
          sub={
            data.pending_bonuses?.total
              ? formatIDR(data.pending_bonuses.total)
              : undefined
          }
          color="bg-amber-500/10 text-amber-400"
        />
        <StatCard
          icon={Calendar}
          label="Leave Requests"
          value={String(data.pending_leave_requests || 0)}
          sub="pending approval"
          color="bg-purple-500/10 text-purple-400"
        />
        <StatCard
          icon={Banknote}
          label="Current Period"
          value={data.current_period?.status || "No period"}
          sub={
            data.current_period
              ? `${data.current_period.payroll_month}/${data.current_period.payroll_year}`
              : "Not calculated yet"
          }
          color="bg-emerald-500/10 text-emerald-400"
        />
      </div>
    </div>
  );
}

function PersonalDashboardView({ data }: { data: PersonalDashboard }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-zinc-100">My HR Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <StatCard
          icon={Gift}
          label="This Month Bonuses"
          value={String(data.month_bonuses?.count || 0)}
          sub={
            data.month_bonuses?.total
              ? formatIDR(data.month_bonuses.total)
              : "No bonuses yet"
          }
          color="bg-amber-500/10 text-amber-400"
        />
        <StatCard
          icon={Banknote}
          label="Latest Payslip"
          value={
            data.latest_payslip
              ? formatIDR(data.latest_payslip.net_salary_idr)
              : "N/A"
          }
          sub={
            data.latest_payslip
              ? `${data.latest_payslip.payroll_month}/${data.latest_payslip.payroll_year}`
              : "No payslip yet"
          }
          color="bg-emerald-500/10 text-emerald-400"
        />
        <StatCard
          icon={Calendar}
          label="Leave Balance"
          value={
            data.leave_balances?.[0]
              ? `${data.leave_balances[0].allocated_days - data.leave_balances[0].used_days - data.leave_balances[0].pending_days} days`
              : "N/A"
          }
          sub="annual leave remaining"
          color="bg-purple-500/10 text-purple-400"
        />
      </div>
    </div>
  );
}

export default function HRDashboardPage() {
  const [adminData, setAdminData] = useState<AdminDashboard | null>(null);
  const [personalData, setPersonalData] = useState<PersonalDashboard | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await hrApi.getDashboard();
        setAdminData(data);
      } catch {
        try {
          const data = await hrApi.getMyDashboard();
          setPersonalData(data);
        } catch (err) {
          setError(
            err instanceof Error ? err.message : "Failed to load dashboard",
          );
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-zinc-100">HR Dashboard</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 animate-pulse"
            >
              <div className="h-4 bg-zinc-800 rounded w-24 mb-4" />
              <div className="h-8 bg-zinc-800 rounded w-32" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-red-400">
        <h2 className="font-semibold mb-2">Error</h2>
        <p>{error}</p>
      </div>
    );
  }

  if (adminData) return <AdminDashboardView data={adminData} />;
  if (personalData) return <PersonalDashboardView data={personalData} />;
  return null;
}
