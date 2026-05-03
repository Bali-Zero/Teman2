"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Banknote,
  Calculator,
  CheckCircle,
  ChevronRight,
  CreditCard,
} from "lucide-react";
import { toast } from "sonner";
import * as hrApi from "@/lib/api/hr/hr";
import type { PayrollPeriod, Payslip } from "@/types/hr";

function formatIDR(amount: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

const statusColors: Record<string, string> = {
  draft: "bg-zinc-500/10 text-zinc-400",
  calculated: "bg-blue-500/10 text-blue-400",
  approved: "bg-amber-500/10 text-amber-400",
  paid: "bg-emerald-500/10 text-emerald-400",
};

export default function PayrollPage() {
  const [periods, setPeriods] = useState<PayrollPeriod[]>([]);
  const [payslips, setPayslips] = useState<Payslip[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await hrApi.listPayrollPeriods();
        setPeriods(data.periods || []);
        setIsAdmin(true);
      } catch {
        try {
          const data = await hrApi.listPayslips();
          setPayslips(data.payslips || []);
        } catch {
          /* empty */
        }
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleCalculate = async () => {
    const now = new Date();
    setCalculating(true);
    try {
      await hrApi.calculatePayroll(now.getMonth() + 1, now.getFullYear());
      const data = await hrApi.listPayrollPeriods();
      setPeriods(data.periods || []);
      toast.success("Payroll calculated");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to calculate payroll",
      );
    } finally {
      setCalculating(false);
    }
  };

  const handleApprove = async (id: number) => {
    try {
      await hrApi.approvePayroll(id);
      setPeriods((prev) =>
        prev.map((p) => (p.id === id ? { ...p, status: "approved" } : p)),
      );
      toast.success("Payroll approved");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to approve payroll",
      );
    }
  };

  const handleMarkPaid = async (id: number) => {
    try {
      await hrApi.markPayrollPaid(id);
      setPeriods((prev) =>
        prev.map((p) => (p.id === id ? { ...p, status: "paid" } : p)),
      );
      toast.success("Payroll marked as paid");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-100">Payroll</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-20 bg-zinc-900 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (isAdmin) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-zinc-100">Payroll Periods</h1>
          <button
            onClick={handleCalculate}
            disabled={calculating}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bz-accent)]/10 text-[var(--bz-accent)] hover:bg-[var(--bz-accent)]/20 text-sm transition-colors disabled:opacity-50"
          >
            <Calculator size={16} />
            {calculating ? "Calculating..." : "Calculate Current Month"}
          </button>
        </div>

        {periods.length === 0 ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
            No payroll periods yet. Click &quot;Calculate Current Month&quot; to
            start.
          </div>
        ) : (
          <div className="space-y-2">
            {periods.map((period) => (
              <div
                key={period.id}
                className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex items-center justify-between"
              >
                <div>
                  <div className="flex items-center gap-3">
                    <Banknote size={18} className="text-zinc-500" />
                    <span className="font-medium text-zinc-200">
                      {String(period.payroll_month).padStart(2, "0")}/
                      {period.payroll_year}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full ${statusColors[period.status] || ""}`}
                    >
                      {period.status}
                    </span>
                  </div>
                  <div className="text-sm text-zinc-500 mt-1">
                    {period.payslip_count} payslips · Total:{" "}
                    {formatIDR(period.total_net || 0)}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {period.status === "calculated" && (
                    <button
                      onClick={() => handleApprove(period.id)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 text-sm"
                    >
                      <CheckCircle size={14} />
                      Approve
                    </button>
                  )}
                  {period.status === "approved" && (
                    <button
                      onClick={() => handleMarkPaid(period.id)}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-sm"
                    >
                      <CreditCard size={14} />
                      Mark Paid
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-zinc-100">My Payslips</h1>
      {payslips.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
          No payslips available yet.
        </div>
      ) : (
        <div className="space-y-2">
          {payslips.map((slip) => (
            <Link
              key={slip.id}
              href={`/hr/payroll/${slip.id}`}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex items-center justify-between group hover:bg-zinc-800/60 hover:border-zinc-700 transition-colors"
            >
              <div>
                <span className="font-medium text-zinc-200">
                  {String(slip.payroll_month).padStart(2, "0")}/
                  {slip.payroll_year}
                </span>
                <div className="text-sm text-zinc-500 mt-1">
                  Base: {formatIDR(slip.base_salary_idr)} + Bonus:{" "}
                  {formatIDR(slip.bonus_total_idr)} - Deductions:{" "}
                  {formatIDR(slip.deduction_total_idr)}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-lg font-semibold text-emerald-400">
                    {formatIDR(slip.net_salary_idr)}
                  </div>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${statusColors[slip.period_status] || ""}`}
                  >
                    {slip.period_status}
                  </span>
                </div>
                <ChevronRight
                  size={16}
                  className="text-zinc-600 group-hover:text-zinc-400 transition-colors"
                />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
