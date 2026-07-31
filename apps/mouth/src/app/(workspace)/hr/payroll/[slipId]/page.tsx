"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { getPayslipDetail } from "@/lib/api/hr/hr";
import type { PayslipDetail, Deduction } from "@/types/hr";
import { Money } from "@balizero/core";

/** Dashboard panel recipe — mirrors the day/dark-aware Kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
};

/** Period-status chip, honestly mapped to --state-* (12% tint + 30% rim). */
const statusStyles: Record<string, React.CSSProperties> = {
  draft: {
    background: "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
    color: "var(--bz-text-2)",
    borderColor: "var(--bz-border)",
  },
  calculated: {
    background: "color-mix(in srgb, var(--state-info) 12%, transparent)",
    color: "var(--state-info)",
    borderColor: "color-mix(in srgb, var(--state-info) 30%, transparent)",
  },
  approved: {
    background: "color-mix(in srgb, var(--state-warning) 12%, transparent)",
    color: "var(--state-warning)",
    borderColor: "color-mix(in srgb, var(--state-warning) 30%, transparent)",
  },
  paid: {
    background: "color-mix(in srgb, var(--state-success) 12%, transparent)",
    color: "var(--state-success)",
    borderColor: "color-mix(in srgb, var(--state-success) 30%, transparent)",
  },
};

function PayslipSkeleton() {
  const bar = "rounded";
  const barStyle: React.CSSProperties = {
    background: "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
  };
  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-pulse">
      <div className={`h-5 w-28 ${bar}`} style={barStyle} />
      <div className="border rounded-xl p-6 space-y-5" style={PANEL}>
        <div className="space-y-2">
          <div className={`h-6 w-48 ${bar}`} style={barStyle} />
          <div className={`h-4 w-32 ${bar}`} style={barStyle} />
        </div>
        <div className="border-t" style={{ borderColor: "var(--bz-border)" }} />
        <div className="space-y-3">
          <div className={`h-4 w-24 ${bar}`} style={barStyle} />
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className={`h-4 w-36 ${bar}`} style={barStyle} />
              <div className={`h-4 w-24 ${bar}`} style={barStyle} />
            </div>
          ))}
          <div className={`h-5 w-full ${bar}`} style={barStyle} />
        </div>
        <div className="border-t" style={{ borderColor: "var(--bz-border)" }} />
        <div className="space-y-3">
          <div className={`h-4 w-40 ${bar}`} style={barStyle} />
          {[...Array(2)].map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className={`h-4 w-36 ${bar}`} style={barStyle} />
              <div className={`h-4 w-24 ${bar}`} style={barStyle} />
            </div>
          ))}
          <div className={`h-5 w-full ${bar}`} style={barStyle} />
        </div>
        <div className="border-t" style={{ borderColor: "var(--bz-border)" }} />
        <div className="flex justify-between">
          <div className={`h-7 w-32 ${bar}`} style={barStyle} />
          <div className={`h-7 w-36 ${bar}`} style={barStyle} />
        </div>
      </div>
    </div>
  );
}

export default function PayslipDetailPage({
  params,
}: {
  params: Promise<{ slipId: string }>;
}) {
  const { slipId } = React.use(params);
  const [slip, setSlip] = useState<PayslipDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const id = parseInt(slipId, 10);
        if (isNaN(id)) {
          setError("Invalid payslip ID");
          return;
        }
        const data = await getPayslipDetail(id);
        setSlip(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load payslip");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [slipId]);

  if (loading) {
    return <PayslipSkeleton />;
  }

  if (error || !slip) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <Link
          href="/hr/payroll"
          className="inline-flex items-center gap-1.5 text-sm text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors"
        >
          <ArrowLeft size={16} />
          Payroll
        </Link>
        <div className="border rounded-xl p-8 text-center" style={PANEL}>
          <FileText
            size={40}
            className="mx-auto mb-3"
            style={{ color: "var(--bz-text-3)" }}
          />
          <p
            className="text-lg font-medium"
            style={{ color: "var(--bz-text-2)" }}
          >
            {error || "Payslip not found"}
          </p>
          <p className="text-sm mt-1" style={{ color: "var(--bz-text-3)" }}>
            The requested payslip could not be loaded.
          </p>
        </div>
      </div>
    );
  }

  const employeeDeductions: Deduction[] = slip.deductions.filter(
    (d) => !d.is_employer,
  );
  const employerContributions: Deduction[] = slip.deductions.filter(
    (d) => d.is_employer,
  );

  const totalEmployeeDeductions = employeeDeductions.reduce(
    (sum, d) => sum + d.amount_idr,
    0,
  );
  const totalEmployerContributions = employerContributions.reduce(
    (sum, d) => sum + d.amount_idr,
    0,
  );

  const totalBruto =
    slip.base_salary_idr +
    slip.bonus_total_idr +
    slip.allowance_total_idr +
    slip.thr_idr;

  const periodLabel = `${String(slip.payroll_month).padStart(2, "0")}/${slip.payroll_year}`;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back link */}
      <Link
        href="/hr/payroll"
        className="inline-flex items-center gap-1.5 text-sm text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors"
      >
        <ArrowLeft size={16} />
        Payroll
      </Link>

      {/* Payslip receipt */}
      <div className="border rounded-xl overflow-hidden" style={PANEL}>
        {/* Header */}
        <div
          className="px-6 py-5 border-b"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <div className="flex items-start justify-between">
            <div>
              <h1
                className="text-xl font-bold"
                style={{ color: "var(--bz-text-1)" }}
              >
                {slip.full_name || slip.employee_name}
              </h1>
              <p
                className="text-sm mt-0.5"
                style={{ color: "var(--bz-text-2)" }}
              >
                {slip.email || slip.employee_email}
              </p>
            </div>
            <div className="text-right">
              <p
                className="text-lg font-semibold tabular-nums"
                style={{ color: "var(--bz-text-1)" }}
              >
                {periodLabel}
              </p>
              <span
                className="inline-block text-xs px-2 py-0.5 rounded-full border mt-1"
                style={statusStyles[slip.period_status] ?? statusStyles.draft}
              >
                {slip.period_status}
              </span>
            </div>
          </div>
        </div>

        {/* PENDAPATAN (Income) */}
        <div
          className="px-6 py-4 border-b"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <h2
            className="text-xs font-semibold uppercase tracking-wider mb-3"
            style={{ color: "var(--bz-text-2)" }}
          >
            Pendapatan
          </h2>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span style={{ color: "var(--bz-text-1)" }}>Gaji Pokok</span>
              <Money
                value={slip.base_salary_idr}
                style={{ color: "var(--bz-text-1)" }}
              />
            </div>
            <div className="flex justify-between text-sm">
              <span style={{ color: "var(--bz-text-1)" }}>Bonus</span>
              <Money
                value={slip.bonus_total_idr}
                style={{ color: "var(--bz-text-1)" }}
              />
            </div>
            {slip.allowance_total_idr > 0 && (
              <div className="flex justify-between text-sm">
                <span style={{ color: "var(--bz-text-1)" }}>Tunjangan</span>
                <Money
                  value={slip.allowance_total_idr}
                  style={{ color: "var(--bz-text-1)" }}
                />
              </div>
            )}
            {slip.thr_idr > 0 && (
              <div className="flex justify-between text-sm">
                <span style={{ color: "var(--bz-text-1)" }}>THR</span>
                <Money
                  value={slip.thr_idr}
                  style={{ color: "var(--bz-text-1)" }}
                />
              </div>
            )}
            <div
              className="flex justify-between pt-2 border-t"
              style={{ borderColor: "var(--bz-border)" }}
            >
              <span
                className="text-sm font-semibold"
                style={{ color: "var(--bz-text-1)" }}
              >
                Total Bruto
              </span>
              <Money
                value={totalBruto}
                className="text-sm font-semibold"
                style={{ color: "var(--bz-text-pure)" }}
              />
            </div>
          </div>
        </div>

        {/* POTONGAN KARYAWAN (Employee Deductions) */}
        <div
          className="px-6 py-4 border-b"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <h2
            className="text-xs font-semibold uppercase tracking-wider mb-3"
            style={{ color: "var(--bz-text-2)" }}
          >
            Potongan Karyawan
          </h2>
          {employeeDeductions.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--bz-text-3)" }}>
              Tidak ada potongan
            </p>
          ) : (
            <div className="space-y-2">
              {employeeDeductions.map((d) => (
                <div key={d.id} className="flex justify-between text-sm">
                  <span style={{ color: "var(--bz-text-1)" }}>{d.label}</span>
                  <span style={{ color: "var(--state-danger)" }}>
                    -
                    <Money value={d.amount_idr} />
                  </span>
                </div>
              ))}
              <div
                className="flex justify-between pt-2 border-t"
                style={{ borderColor: "var(--bz-border)" }}
              >
                <span
                  className="text-sm font-semibold"
                  style={{ color: "var(--bz-text-1)" }}
                >
                  Total Potongan
                </span>
                <span
                  className="text-sm font-semibold"
                  style={{ color: "var(--state-danger)" }}
                >
                  -
                  <Money value={totalEmployeeDeductions} />
                </span>
              </div>
            </div>
          )}
        </div>

        {/* KONTRIBUSI PERUSAHAAN (Employer Contributions) */}
        {employerContributions.length > 0 && (
          <div
            className="px-6 py-4 border-b"
            style={{ borderColor: "var(--bz-border)" }}
          >
            <h2
              className="text-xs font-semibold uppercase tracking-wider mb-3"
              style={{ color: "var(--bz-text-3)" }}
            >
              Kontribusi Perusahaan
            </h2>
            <div className="space-y-2">
              {employerContributions.map((d) => (
                <div key={d.id} className="flex justify-between text-sm">
                  <span style={{ color: "var(--bz-text-2)" }}>{d.label}</span>
                  <Money
                    value={d.amount_idr}
                    style={{ color: "var(--bz-text-2)" }}
                  />
                </div>
              ))}
              <div
                className="flex justify-between pt-2 border-t"
                style={{
                  borderColor:
                    "color-mix(in srgb, var(--bz-border) 50%, transparent)",
                }}
              >
                <span className="text-sm" style={{ color: "var(--bz-text-2)" }}>
                  Total Kontribusi
                </span>
                <Money
                  value={totalEmployerContributions}
                  className="text-sm"
                  style={{ color: "var(--bz-text-2)" }}
                />
              </div>
            </div>
          </div>
        )}

        {/* GAJI BERSIH (Net Salary) Footer */}
        <div
          className="px-6 py-5"
          style={{
            background:
              "color-mix(in srgb, var(--surface-deep) 50%, transparent)",
          }}
        >
          <div className="flex items-center justify-between">
            <span
              className="text-base font-bold uppercase tracking-wide"
              style={{ color: "var(--bz-text-1)" }}
            >
              Gaji Bersih
            </span>
            <Money
              value={slip.net_salary_idr}
              className="text-2xl font-bold"
              style={{ color: "var(--state-success)" }}
            />
          </div>
        </div>
      </div>

      {/* Notes */}
      {slip.notes && (
        <div
          className="border rounded-lg px-5 py-3"
          style={{
            background: "var(--bz-glass-rim)",
            borderColor: "var(--bz-border)",
          }}
        >
          <p
            className="text-xs font-semibold uppercase tracking-wider mb-1"
            style={{ color: "var(--bz-text-2)" }}
          >
            Catatan
          </p>
          <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
            {slip.notes}
          </p>
        </div>
      )}
    </div>
  );
}
