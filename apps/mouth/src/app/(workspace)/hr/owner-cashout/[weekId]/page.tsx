"use client";

import React, { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";

import * as api from "@/lib/api/hr/owner-cashout";
import type {
  OwnerCashoutRow,
  OwnerCashoutWeekDetail,
} from "@/types/owner-cashout";

const SHEET_URL =
  "https://docs.google.com/spreadsheets/d/1OZzgvDLgf3yd9eUh5CyADjHCHLoXmE5nIRoJlut_jBE/edit";

function formatIDR(v: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(v);
}

function EntityTable({
  title,
  rows,
  showTotalIncome,
  showFinalPrice,
}: {
  title: string;
  rows: OwnerCashoutRow[];
  showTotalIncome: boolean;
  showFinalPrice: boolean;
}) {
  if (rows.length === 0) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
      <h3 className="text-sm font-semibold text-zinc-200 p-5 border-b border-zinc-800">
        {title}
      </h3>
      <table className="w-full text-sm">
        <thead className="text-xs text-zinc-500 uppercase border-b border-zinc-800">
          <tr>
            <th className="text-left px-4 py-3">Client</th>
            <th className="text-left px-4 py-3">Visa</th>
            <th className="text-right px-4 py-3">PNBP</th>
            <th className="text-right px-4 py-3">Urgent</th>
            {showTotalIncome && (
              <th className="text-right px-4 py-3">Income</th>
            )}
            <th className="text-right px-4 py-3">MBS</th>
            <th className="text-right px-4 py-3">MBZ</th>
            {showFinalPrice && (
              <th className="text-right px-4 py-3">Final</th>
            )}
            <th className="text-left px-4 py-3">Note</th>
          </tr>
        </thead>
        <tbody className="text-zinc-300">
          {rows.map((r, idx) => (
            <tr
              key={`${r.entity}-${r.row_index}-${idx}`}
              className="border-b border-zinc-800 last:border-b-0"
            >
              <td className="px-4 py-2">{r.client_name}</td>
              <td className="px-4 py-2 text-zinc-400">{r.process || "—"}</td>
              <td className="text-right px-4 py-2">{formatIDR(r.pnbp_idr)}</td>
              <td className="text-right px-4 py-2">
                {r.urgent_idr > 0 ? formatIDR(r.urgent_idr) : "—"}
              </td>
              {showTotalIncome && (
                <td className="text-right px-4 py-2">
                  {formatIDR(r.total_income_idr)}
                </td>
              )}
              <td className="text-right px-4 py-2 text-amber-400">
                {formatIDR(r.margin_bs_idr)}
              </td>
              <td className="text-right px-4 py-2 text-emerald-400">
                {formatIDR(r.margin_bz_idr)}
              </td>
              {showFinalPrice && (
                <td className="text-right px-4 py-2">
                  {formatIDR(r.final_price_idr)}
                </td>
              )}
              <td className="px-4 py-2 text-xs text-zinc-500">
                {r.note || ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function OwnerCashoutWeekDetailPage({
  params,
}: {
  params: Promise<{ weekId: string }>;
}) {
  const { weekId } = use(params);
  const [detail, setDetail] = useState<OwnerCashoutWeekDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const d = await api.getWeekDetail(Number(weekId));
        if (mounted) setDetail(d);
      } catch (e) {
        if (mounted)
          setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [weekId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-zinc-800 rounded w-80 animate-pulse" />
        <div className="h-64 bg-zinc-900 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-xl p-6 text-red-400">
        <Link
          href="/hr/owner-cashout"
          className="inline-flex items-center gap-2 text-sm mb-3"
        >
          <ArrowLeft size={14} /> Back
        </Link>
        <p>{error || "Week not found"}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <Link
            href="/hr/owner-cashout"
            className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-200 mb-2"
          >
            <ArrowLeft size={14} /> Back to Owner Cashout
          </Link>
          <h1 className="text-2xl font-bold text-zinc-100">
            Week of{" "}
            {new Date(detail.week.week_start).toLocaleDateString("en-GB", {
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </h1>
          <div className="text-xs text-zinc-500 mt-1">
            Tabs: {detail.week.tab_name_bz || "—"} /{" "}
            {detail.week.tab_name_bs || "—"}
          </div>
        </div>
        <a
          href={SHEET_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 rounded-lg border border-zinc-700 text-sm"
        >
          <ExternalLink size={14} /> Open in Sheets
        </a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Practices</div>
          <div className="text-xl font-bold text-zinc-100">
            {detail.week.total_practices}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Total Income</div>
          <div className="text-xl font-bold text-zinc-100">
            {formatIDR(detail.week.total_income_idr)}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Margin BZ</div>
          <div className="text-xl font-bold text-emerald-400">
            {formatIDR(detail.week.total_margin_bz_idr)}
          </div>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="text-xs text-zinc-400">Margin BS</div>
          <div className="text-xl font-bold text-amber-400">
            {formatIDR(detail.week.total_margin_bs_idr)}
          </div>
        </div>
      </div>

      {detail.subtotals_by_process.length > 0 && (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-200 mb-3">
            Subtotals by visa type
          </h2>
          <div className="flex flex-wrap gap-2">
            {detail.subtotals_by_process.map((s) => (
              <div
                key={s.process}
                className="px-3 py-2 bg-zinc-800 rounded-lg border border-zinc-700 text-xs"
              >
                <span className="text-zinc-400">{s.process}: </span>
                <span className="text-zinc-100">{s.count}</span>
                <span className="text-zinc-500"> · </span>
                <span className="text-emerald-400">
                  {formatIDR(s.margin_bz_idr)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <EntityTable
        title="Bali Zero"
        rows={detail.rows_bz}
        showTotalIncome={true}
        showFinalPrice={false}
      />
      <EntityTable
        title="Bali Services"
        rows={detail.rows_bs}
        showTotalIncome={false}
        showFinalPrice={true}
      />
    </div>
  );
}
