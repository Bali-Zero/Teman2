"use client";

import React, { useEffect, useState } from "react";
import {
  Loader2,
  FileText,
  Calendar,
  CheckCircle,
  AlertTriangle,
  Clock,
  ArrowRight,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";
import type {
  LKPMDraftSummary,
  LKPMDeadline,
  LKPMReceipt,
} from "@/lib/api/portal/portal.types";

export default function LKPMPage() {
  const { error } = useToast();
  const [history, setHistory] = useState<LKPMDraftSummary[]>([]);
  const [deadlines, setDeadlines] = useState<LKPMDeadline[]>([]);
  const [receipts, setReceipts] = useState<LKPMReceipt[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      // Portal context — clientId comes from the authenticated session.
      // All three endpoints cascade via client_company_links server-side.
      const [historyData, deadlineData, receiptData] = await Promise.all([
        api.get<{ success: boolean; items: LKPMDraftSummary[] }>(
          "/api/v1/lkpm/history/me",
        ),
        api.get<{ success: boolean; deadlines: LKPMDeadline[] }>(
          "/api/v1/lkpm/deadlines",
        ),
        api
          .get<{
            success: boolean;
            items: LKPMReceipt[];
          }>("/api/v1/lkpm/receipts/me")
          .catch(() => ({ success: false, items: [] as LKPMReceipt[] })),
      ]);
      setHistory(historyData.items ?? []);
      setDeadlines(deadlineData.deadlines ?? []);
      setReceipts(receiptData.items ?? []);
    } catch (err) {
      error("Failed to load LKPM data", "Please try again later");
      logger.error("Failed to load portal LKPM data", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        {/* Header */}
        <section className="flex items-center justify-between">
          <div className="space-y-1.5">
            <div
              className="h-7 w-36 rounded animate-pulse"
              style={{ background: "var(--bz-border)" }}
            />
            <div
              className="h-4 w-52 rounded animate-pulse"
              style={{ background: "var(--bz-border)", opacity: 0.5 }}
            />
          </div>
          <div
            className="h-9 w-28 rounded-lg animate-pulse"
            style={{ background: "var(--bz-border)" }}
          />
        </section>
        {/* Deadline card skeleton */}
        <div
          className="rounded-xl border p-6 space-y-3 animate-pulse"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
          }}
        >
          <div
            className="h-5 w-32 rounded"
            style={{ background: "var(--bz-border)" }}
          />
          <div
            className="h-14 rounded-lg"
            style={{ background: "var(--bz-border)", opacity: 0.4 }}
          />
        </div>
        {/* History section skeleton */}
        <div
          className="rounded-xl border p-6 space-y-4 animate-pulse"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
          }}
        >
          <div
            className="h-5 w-36 rounded"
            style={{ background: "var(--bz-border)" }}
          />
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-lg border p-4 flex items-center justify-between"
              style={{ borderColor: "rgba(255,255,255,0.05)" }}
            >
              <div className="space-y-1.5">
                <div
                  className="h-4 w-24 rounded"
                  style={{ background: "var(--bz-border)" }}
                />
                <div
                  className="h-3 w-40 rounded"
                  style={{ background: "var(--bz-border)", opacity: 0.4 }}
                />
              </div>
              <div
                className="h-6 w-20 rounded-full"
                style={{ background: "var(--bz-border)", opacity: 0.4 }}
              />
            </div>
          ))}
        </div>
      </div>
    );
  }

  const formatIDR = (amount: number) =>
    new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      minimumFractionDigits: 0,
    }).format(amount);

  const nextDeadline = deadlines.find((d) => !d.is_overdue);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">LKPM Reports</h1>
          <p style={{ color: "var(--bz-text-2)" }}>
            Quarterly investment activity reports
          </p>
        </div>
        <Link
          href="/portal/lkpm/submit"
          className="px-4 py-2 rounded-lg text-sm font-medium text-white flex items-center gap-2"
          style={{ background: "var(--bz-accent-warm)" }}
        >
          <FileText className="w-4 h-4" />
          Submit Data
        </Link>
      </section>

      {/* Deadline Card */}
      {nextDeadline && (
        <section
          className="rounded-xl border p-6"
          style={{
            background: "rgba(30,30,35,0.7)",
            borderColor: "rgba(255,255,255,0.05)",
            backdropFilter: "blur(24px)",
          }}
        >
          <div className="flex items-center gap-2 mb-4">
            <Calendar
              className="w-5 h-5"
              style={{ color: "var(--bz-accent-warm)" }}
            />
            <h2 className="text-lg font-semibold">Next Deadline</h2>
          </div>

          <div
            className="p-4 rounded-lg flex items-center gap-3 border"
            style={
              nextDeadline.days_remaining <= 7
                ? {
                    background: "rgba(239,68,68,0.08)",
                    borderColor: "rgba(239,68,68,0.3)",
                  }
                : nextDeadline.days_remaining <= 30
                  ? {
                      background: "rgba(245,158,11,0.08)",
                      borderColor: "rgba(245,158,11,0.3)",
                    }
                  : {
                      background: "rgba(16,185,129,0.06)",
                      borderColor: "rgba(16,185,129,0.25)",
                    }
            }
          >
            <Calendar
              className="w-5 h-5"
              style={{
                color:
                  nextDeadline.days_remaining <= 7
                    ? "#f87171"
                    : nextDeadline.days_remaining <= 30
                      ? "#fbbf24"
                      : "#34d399",
              }}
            />
            <div className="flex-1">
              <p className="text-sm font-semibold">
                {nextDeadline.quarter} {nextDeadline.year} —{" "}
                {nextDeadline.days_remaining} days remaining
              </p>
              <p className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                Deadline:{" "}
                {new Date(nextDeadline.deadline).toLocaleDateString("en-US", {
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                })}
              </p>
            </div>
          </div>
        </section>
      )}

      {/* Report History */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(24px)",
        }}
      >
        <div className="flex items-center gap-2">
          <Clock
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">Report History</h2>
        </div>

        {history.length === 0 ? (
          <p className="text-sm py-4" style={{ color: "var(--bz-text-2)" }}>
            No LKPM reports yet. Submit your first quarterly data to get
            started.
          </p>
        ) : (
          <div className="space-y-3">
            {history.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                formatIDR={formatIDR}
              />
            ))}
          </div>
        )}
      </section>

      {/* OSS Tanda Terima (receipts per kegiatan usaha) — shareholder cascade */}
      {receipts.length > 0 && <ReceiptsSection receipts={receipts} />}

      {/* Help Notice */}
      <section
        className="rounded-lg border p-4"
        style={{
          background: "rgba(201,169,110,0.06)",
          borderColor: "rgba(201,169,110,0.3)",
        }}
      >
        <p className="text-sm" style={{ color: "var(--bz-accent-warm)" }}>
          LKPM reports must be submitted quarterly to OSS. Contact your account
          manager for assistance.
        </p>
      </section>
    </div>
  );
}

function ReceiptsSection({ receipts }: { receipts: LKPMReceipt[] }) {
  // Group by "Q{year}" so a shareholder sees the most recent quarter first,
  // then break out each PT inside.
  const byPeriod = receipts.reduce<Record<string, LKPMReceipt[]>>((acc, r) => {
    const key = r.quarter && r.year ? `${r.quarter} ${r.year}` : "Other";
    if (!acc[key]) acc[key] = [];
    acc[key].push(r);
    return acc;
  }, {});

  // Sort keys newest first — `Q2 2026` > `Q1 2026` > `Q4 2025`
  const orderedPeriods = Object.keys(byPeriod).sort((a, b) => {
    const parse = (s: string): [number, number] => {
      const m = s.match(/^Q(\d)\s+(\d{4})$/);
      return m ? [Number(m[2]), Number(m[1])] : [0, 0];
    };
    const [yA, qA] = parse(a);
    const [yB, qB] = parse(b);
    return yB - yA || qB - qA;
  });

  const totalApproved = receipts.filter(
    (r) => r.oss_status === "Disetujui",
  ).length;

  return (
    <section
      className="rounded-xl border p-6 space-y-4"
      style={{
        background: "rgba(30,30,35,0.7)",
        borderColor: "rgba(255,255,255,0.05)",
        backdropFilter: "blur(24px)",
      }}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">OSS Tanda Terima</h2>
        </div>
        <p className="text-xs" style={{ color: "var(--bz-text-2)" }}>
          {receipts.length} receipt{receipts.length === 1 ? "" : "s"}
          {totalApproved > 0 && (
            <>
              {" · "}
              <span style={{ color: "#34d399" }}>{totalApproved} approved</span>
            </>
          )}
        </p>
      </div>

      <div className="space-y-5">
        {orderedPeriods.map((period) => {
          const list = byPeriod[period];
          // Sub-group by company
          const byCompany = list.reduce<Record<string, LKPMReceipt[]>>(
            (acc, r) => {
              const key =
                r.company_name ?? r.nama_perusahaan_oss ?? "Unknown PT";
              if (!acc[key]) acc[key] = [];
              acc[key].push(r);
              return acc;
            },
            {},
          );
          return (
            <div key={period} className="space-y-3">
              <p
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--bz-accent-warm)" }}
              >
                {period}
              </p>
              {Object.entries(byCompany).map(([company, items]) => (
                <div key={company} className="space-y-1.5">
                  <p
                    className="text-xs font-medium"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    {company}
                  </p>
                  <div
                    className="rounded-lg border overflow-hidden"
                    style={{ borderColor: "rgba(255,255,255,0.05)" }}
                  >
                    <table className="w-full text-xs">
                      <thead
                        style={{
                          background: "rgba(255,255,255,0.03)",
                          color: "var(--bz-text-2)",
                        }}
                      >
                        <tr>
                          <th className="text-left px-3 py-2 font-normal">
                            KBLI
                          </th>
                          <th className="text-left px-3 py-2 font-normal">
                            Nomor Laporan
                          </th>
                          <th className="text-left px-3 py-2 font-normal">
                            Stage
                          </th>
                          <th className="text-left px-3 py-2 font-normal">
                            Status
                          </th>
                          <th className="text-left px-3 py-2 font-normal">
                            Date
                          </th>
                          <th className="text-left px-3 py-2 font-normal">
                            PDF
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((r) => {
                          const approved = r.oss_status === "Disetujui";
                          return (
                            <tr
                              key={r.id}
                              className="border-t"
                              style={{
                                borderColor: "rgba(255,255,255,0.05)",
                              }}
                            >
                              <td
                                className="px-3 py-2 font-mono"
                                style={{ color: "var(--bz-text-1)" }}
                              >
                                {r.kbli_code ?? "—"}
                              </td>
                              <td
                                className="px-3 py-2 font-mono"
                                style={{ color: "var(--bz-text-2)" }}
                                title={r.nomor_kegiatan_usaha}
                              >
                                {r.nomor_laporan}
                              </td>
                              <td
                                className="px-3 py-2"
                                style={{ color: "var(--bz-text-2)" }}
                              >
                                {r.stage ?? "—"}
                              </td>
                              <td className="px-3 py-2">
                                <span
                                  style={{
                                    color: approved ? "#34d399" : "#fbbf24",
                                  }}
                                >
                                  {r.oss_status ?? "—"}
                                  {approved ? " \u2705" : ""}
                                </span>
                              </td>
                              <td
                                className="px-3 py-2"
                                style={{ color: "var(--bz-text-2)" }}
                              >
                                {r.tanggal_diterima ?? "—"}
                              </td>
                              <td className="px-3 py-2">
                                {r.file_drive_url ? (
                                  <a
                                    href={r.file_drive_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                      color: "var(--bz-accent-warm)",
                                    }}
                                    className="hover:underline"
                                  >
                                    Open
                                  </a>
                                ) : (
                                  <span style={{ color: "var(--bz-text-2)" }}>
                                    —
                                  </span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ReportCard({
  report,
  formatIDR,
}: {
  report: LKPMDraftSummary;
  formatIDR: (amount: number) => string;
}) {
  // 3-state indicator
  const isGreen = report.oss_submitted === true;
  const isOrange = report.status === "validated" && !report.client_approved;
  // Gray = everything else (draft, approved without OSS, etc.)

  const accentBorder = isGreen
    ? "rgba(16,185,129,0.4)"
    : isOrange
      ? "rgba(245,158,11,0.4)"
      : "rgba(255,255,255,0.05)";

  const statusLabel = isGreen
    ? "Sudah dilapor ke OSS"
    : isOrange
      ? "Perlu persetujuan Anda"
      : "Sedang diproses oleh tim Bali Zero";

  const StatusIcon = isGreen ? CheckCircle : isOrange ? AlertTriangle : Clock;

  const statusColor = isGreen
    ? "#34d399"
    : isOrange
      ? "#fbbf24"
      : "var(--bz-text-2)";

  // Deadline formatting helper
  const QUARTER_DEADLINES: Record<string, [number, number]> = {
    Q1: [4, 15],
    Q2: [7, 15],
    Q3: [10, 15],
    Q4: [1, 15],
  };
  const deadlineEntry = QUARTER_DEADLINES[report.quarter];
  let deadlineStr = "";
  if (deadlineEntry) {
    const [m, d] = deadlineEntry;
    const dYear = report.quarter === "Q4" ? report.year + 1 : report.year;
    deadlineStr = `${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}/${dYear}`;
  }

  const daysColor =
    report.days_to_deadline != null && report.days_to_deadline <= 3
      ? "#f87171"
      : report.days_to_deadline != null && report.days_to_deadline <= 7
        ? "#fbbf24"
        : "#34d399";

  const cardContent = (
    <div
      className="rounded-lg border p-4 transition-colors hover:border-[var(--bz-accent-warm)]"
      style={{
        background: "rgba(30,30,35,0.7)",
        borderColor: accentBorder,
        backdropFilter: "blur(24px)",
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">
            {report.quarter} {report.year}
          </p>
          {/* Status line */}
          <div className="flex items-center gap-1.5 mt-1">
            <StatusIcon
              className="w-3.5 h-3.5"
              style={{ color: statusColor }}
            />
            <span
              className="text-xs font-medium"
              style={{ color: statusColor }}
            >
              {statusLabel}
            </span>
          </div>
          {/* Receipt number for green */}
          {isGreen && report.oss_receipt_number && (
            <p
              className="text-[10px] mt-0.5"
              style={{ color: "var(--bz-text-2)" }}
            >
              No. {report.oss_receipt_number}
            </p>
          )}
        </div>
        <ArrowRight
          className="w-4 h-4 flex-shrink-0"
          style={{ color: "var(--bz-text-2)" }}
        />
      </div>

      {/* Deadline — only when NOT green */}
      {!isGreen && deadlineStr && report.days_to_deadline != null && (
        <p className="text-xs mt-1" style={{ color: daysColor }}>
          Deadline: {deadlineStr} ({report.days_to_deadline} hari)
        </p>
      )}

      {/* Realized total — secondary */}
      <p className="text-[10px] mt-1.5" style={{ color: "var(--bz-text-2)" }}>
        Total Realized: {formatIDR(report.realized_total)}
      </p>
    </div>
  );

  if (isOrange) {
    return (
      <Link href={`/portal/lkpm/${report.quarter}?year=${report.year}`}>
        {cardContent}
      </Link>
    );
  }

  return (
    <Link href={`/portal/lkpm/${report.quarter}?year=${report.year}`}>
      {cardContent}
    </Link>
  );
}
