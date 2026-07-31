"use client";

import React, { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink } from "lucide-react";

import * as api from "@/lib/api/hr/owner-cashout";
import type {
  OwnerCashoutRow,
  OwnerCashoutWeekDetail,
} from "@/types/owner-cashout";
import { Money } from "@balizero/core";

const SHEET_URL =
  "https://docs.google.com/spreadsheets/d/1OZzgvDLgf3yd9eUh5CyADjHCHLoXmE5nIRoJlut_jBE/edit";

/** Dashboard panel recipe — mirrors the day/dark-aware Kita surfaces. */
const PANEL: React.CSSProperties = {
  background: "var(--bz-card)",
  borderColor: "var(--bz-border)",
};

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
    <div className="border rounded-xl overflow-hidden" style={PANEL}>
      <h3
        className="text-sm font-semibold p-5 border-b"
        style={{ color: "var(--bz-text-1)", borderColor: "var(--bz-border)" }}
      >
        {title}
      </h3>
      <table className="w-full text-sm">
        <thead
          className="text-xs uppercase border-b"
          style={{ color: "var(--bz-text-2)", borderColor: "var(--bz-border)" }}
        >
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
            {showFinalPrice && <th className="text-right px-4 py-3">Final</th>}
            <th className="text-left px-4 py-3">Note</th>
          </tr>
        </thead>
        <tbody style={{ color: "var(--bz-text-1)" }}>
          {rows.map((r, idx) => (
            <tr
              key={`${r.entity}-${r.row_index}-${idx}`}
              className="border-b last:border-b-0"
              style={{ borderColor: "var(--bz-border)" }}
            >
              <td className="px-4 py-2">{r.client_name}</td>
              <td className="px-4 py-2" style={{ color: "var(--bz-text-2)" }}>
                {r.process || "—"}
              </td>
              <td className="text-right px-4 py-2">
                <Money value={r.pnbp_idr} />
              </td>
              <td className="text-right px-4 py-2">
                {r.urgent_idr > 0 ? <Money value={r.urgent_idr} /> : "—"}
              </td>
              {showTotalIncome && (
                <td className="text-right px-4 py-2">
                  <Money value={r.total_income_idr} />
                </td>
              )}
              <td className="text-right px-4 py-2">
                <Money
                  value={r.margin_bs_idr}
                  style={{ color: "var(--state-warning)" }}
                />
              </td>
              <td className="text-right px-4 py-2">
                <Money
                  value={r.margin_bz_idr}
                  style={{ color: "var(--state-success)" }}
                />
              </td>
              {showFinalPrice && (
                <td className="text-right px-4 py-2">
                  <Money value={r.final_price_idr} />
                </td>
              )}
              <td
                className="px-4 py-2 text-xs"
                style={{ color: "var(--bz-text-2)" }}
              >
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
        <div
          className="h-8 rounded w-80 animate-pulse"
          style={{
            background:
              "color-mix(in srgb, var(--bz-text-pure) 6%, transparent)",
          }}
        />
        <div className="h-64 border rounded-xl animate-pulse" style={PANEL} />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div
        className="border rounded-xl p-6"
        style={{
          background:
            "color-mix(in srgb, var(--state-danger) 12%, transparent)",
          borderColor:
            "color-mix(in srgb, var(--state-danger) 30%, transparent)",
          color: "var(--state-danger)",
        }}
      >
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
            className="inline-flex items-center gap-2 text-sm text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] mb-2"
          >
            <ArrowLeft size={14} /> Back to Owner Cashout
          </Link>
          <h1
            className="text-2xl font-bold"
            style={{ color: "var(--bz-text-1)" }}
          >
            Week of{" "}
            {new Date(detail.week.week_start).toLocaleDateString("en-GB", {
              day: "2-digit",
              month: "long",
              year: "numeric",
            })}
          </h1>
          <div className="text-xs mt-1" style={{ color: "var(--bz-text-2)" }}>
            Tabs: {detail.week.tab_name_bz || "—"} /{" "}
            {detail.week.tab_name_bs || "—"}
          </div>
        </div>
        <a
          href={SHEET_URL}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-2 px-3 py-2 bg-[var(--bz-card)] hover:bg-[var(--surface-raised)] text-[var(--bz-text-1)] rounded-lg border border-[var(--bz-border)] text-sm transition-colors"
        >
          <ExternalLink size={14} /> Open in Sheets
        </a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="border rounded-xl p-4" style={PANEL}>
          <div className="text-xs" style={{ color: "var(--bz-text-2)" }}>
            Practices
          </div>
          <div
            className="text-xl font-bold"
            style={{ color: "var(--bz-text-1)" }}
          >
            {detail.week.total_practices}
          </div>
        </div>
        <div className="border rounded-xl p-4" style={PANEL}>
          <div className="text-xs" style={{ color: "var(--bz-text-2)" }}>
            Total Income
          </div>
          <Money
            value={detail.week.total_income_idr}
            className="block text-xl font-bold"
            style={{ color: "var(--bz-text-1)" }}
          />
        </div>
        <div className="border rounded-xl p-4" style={PANEL}>
          <div className="text-xs" style={{ color: "var(--bz-text-2)" }}>
            Margin BZ
          </div>
          <Money
            value={detail.week.total_margin_bz_idr}
            className="block text-xl font-bold"
            style={{ color: "var(--state-success)" }}
          />
        </div>
        <div className="border rounded-xl p-4" style={PANEL}>
          <div className="text-xs" style={{ color: "var(--bz-text-2)" }}>
            Margin BS
          </div>
          <Money
            value={detail.week.total_margin_bs_idr}
            className="block text-xl font-bold"
            style={{ color: "var(--state-warning)" }}
          />
        </div>
      </div>

      {detail.subtotals_by_process.length > 0 && (
        <div className="border rounded-xl p-5" style={PANEL}>
          <h2
            className="text-sm font-semibold mb-3"
            style={{ color: "var(--bz-text-1)" }}
          >
            Subtotals by visa type
          </h2>
          <div className="flex flex-wrap gap-2">
            {detail.subtotals_by_process.map((s) => (
              <div
                key={s.process}
                className="px-3 py-2 rounded-lg border text-xs"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              >
                <span style={{ color: "var(--bz-text-2)" }}>{s.process}: </span>
                <span style={{ color: "var(--bz-text-1)" }}>{s.count}</span>
                <span style={{ color: "var(--bz-text-3)" }}> · </span>
                <Money
                  value={s.margin_bz_idr}
                  style={{ color: "var(--state-success)" }}
                />
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
