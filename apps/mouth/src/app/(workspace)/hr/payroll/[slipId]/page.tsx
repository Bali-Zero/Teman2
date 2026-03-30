'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, FileText } from 'lucide-react';
import { getPayslipDetail } from '@/lib/api/hr/hr';
import type { PayslipDetail, Deduction } from '@/types/hr';

function formatIDR(amount: number): string {
  return new Intl.NumberFormat('id-ID', {
    style: 'currency',
    currency: 'IDR',
    maximumFractionDigits: 0,
  }).format(amount);
}

const statusColors: Record<string, string> = {
  draft: 'bg-zinc-500/10 text-zinc-400 border-zinc-700',
  calculated: 'bg-blue-500/10 text-blue-400 border-blue-800',
  approved: 'bg-amber-500/10 text-amber-400 border-amber-800',
  paid: 'bg-emerald-500/10 text-emerald-400 border-emerald-800',
};

function PayslipSkeleton() {
  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-pulse">
      <div className="h-5 w-28 bg-zinc-800 rounded" />
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-5">
        <div className="space-y-2">
          <div className="h-6 w-48 bg-zinc-800 rounded" />
          <div className="h-4 w-32 bg-zinc-800 rounded" />
        </div>
        <div className="border-t border-zinc-800" />
        <div className="space-y-3">
          <div className="h-4 w-24 bg-zinc-800 rounded" />
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-36 bg-zinc-800 rounded" />
              <div className="h-4 w-24 bg-zinc-800 rounded" />
            </div>
          ))}
          <div className="h-5 w-full bg-zinc-800 rounded" />
        </div>
        <div className="border-t border-zinc-800" />
        <div className="space-y-3">
          <div className="h-4 w-40 bg-zinc-800 rounded" />
          {[...Array(2)].map((_, i) => (
            <div key={i} className="flex justify-between">
              <div className="h-4 w-36 bg-zinc-800 rounded" />
              <div className="h-4 w-24 bg-zinc-800 rounded" />
            </div>
          ))}
          <div className="h-5 w-full bg-zinc-800 rounded" />
        </div>
        <div className="border-t border-zinc-800" />
        <div className="flex justify-between">
          <div className="h-7 w-32 bg-zinc-800 rounded" />
          <div className="h-7 w-36 bg-zinc-800 rounded" />
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
          setError('Invalid payslip ID');
          return;
        }
        const data = await getPayslipDetail(id);
        setSlip(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load payslip');
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
          className="inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <ArrowLeft size={16} />
          Payroll
        </Link>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
          <FileText size={40} className="mx-auto text-zinc-600 mb-3" />
          <p className="text-zinc-400 text-lg font-medium">
            {error || 'Payslip not found'}
          </p>
          <p className="text-zinc-600 text-sm mt-1">
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

  const periodLabel = `${String(slip.payroll_month).padStart(2, '0')}/${slip.payroll_year}`;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back link */}
      <Link
        href="/hr/payroll"
        className="inline-flex items-center gap-1.5 text-sm text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        <ArrowLeft size={16} />
        Payroll
      </Link>

      {/* Payslip receipt */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-zinc-800">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-xl font-bold text-zinc-100">
                {slip.full_name || slip.employee_name}
              </h1>
              <p className="text-sm text-zinc-500 mt-0.5">
                {slip.email || slip.employee_email}
              </p>
            </div>
            <div className="text-right">
              <p className="text-lg font-semibold text-zinc-200 tabular-nums">
                {periodLabel}
              </p>
              <span
                className={`inline-block text-xs px-2 py-0.5 rounded-full border mt-1 ${statusColors[slip.period_status] || 'bg-zinc-500/10 text-zinc-400 border-zinc-700'}`}
              >
                {slip.period_status}
              </span>
            </div>
          </div>
        </div>

        {/* PENDAPATAN (Income) */}
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">
            Pendapatan
          </h2>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-zinc-300">Gaji Pokok</span>
              <span className="text-zinc-200 tabular-nums">
                {formatIDR(slip.base_salary_idr)}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-300">Bonus</span>
              <span className="text-zinc-200 tabular-nums">
                {formatIDR(slip.bonus_total_idr)}
              </span>
            </div>
            {slip.allowance_total_idr > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-zinc-300">Tunjangan</span>
                <span className="text-zinc-200 tabular-nums">
                  {formatIDR(slip.allowance_total_idr)}
                </span>
              </div>
            )}
            {slip.thr_idr > 0 && (
              <div className="flex justify-between text-sm">
                <span className="text-zinc-300">THR</span>
                <span className="text-zinc-200 tabular-nums">
                  {formatIDR(slip.thr_idr)}
                </span>
              </div>
            )}
            <div className="flex justify-between pt-2 border-t border-zinc-800">
              <span className="text-sm font-semibold text-zinc-200">
                Total Bruto
              </span>
              <span className="text-sm font-semibold text-zinc-100 tabular-nums">
                {formatIDR(totalBruto)}
              </span>
            </div>
          </div>
        </div>

        {/* POTONGAN KARYAWAN (Employee Deductions) */}
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3">
            Potongan Karyawan
          </h2>
          {employeeDeductions.length === 0 ? (
            <p className="text-sm text-zinc-600">Tidak ada potongan</p>
          ) : (
            <div className="space-y-2">
              {employeeDeductions.map((d) => (
                <div key={d.id} className="flex justify-between text-sm">
                  <span className="text-zinc-300">{d.label}</span>
                  <span className="text-red-400 tabular-nums">
                    -{formatIDR(d.amount_idr)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between pt-2 border-t border-zinc-800">
                <span className="text-sm font-semibold text-zinc-200">
                  Total Potongan
                </span>
                <span className="text-sm font-semibold text-red-400 tabular-nums">
                  -{formatIDR(totalEmployeeDeductions)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* KONTRIBUSI PERUSAHAAN (Employer Contributions) */}
        {employerContributions.length > 0 && (
          <div className="px-6 py-4 border-b border-zinc-800">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-600 mb-3">
              Kontribusi Perusahaan
            </h2>
            <div className="space-y-2">
              {employerContributions.map((d) => (
                <div key={d.id} className="flex justify-between text-sm">
                  <span className="text-zinc-500">{d.label}</span>
                  <span className="text-zinc-500 tabular-nums">
                    {formatIDR(d.amount_idr)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between pt-2 border-t border-zinc-800/50">
                <span className="text-sm text-zinc-500">
                  Total Kontribusi
                </span>
                <span className="text-sm text-zinc-500 tabular-nums">
                  {formatIDR(totalEmployerContributions)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* GAJI BERSIH (Net Salary) Footer */}
        <div className="px-6 py-5 bg-zinc-950/50">
          <div className="flex items-center justify-between">
            <span className="text-base font-bold text-zinc-200 uppercase tracking-wide">
              Gaji Bersih
            </span>
            <span className="text-2xl font-bold text-emerald-400 tabular-nums">
              {formatIDR(slip.net_salary_idr)}
            </span>
          </div>
        </div>
      </div>

      {/* Notes */}
      {slip.notes && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg px-5 py-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-1">
            Catatan
          </p>
          <p className="text-sm text-zinc-400">{slip.notes}</p>
        </div>
      )}
    </div>
  );
}
