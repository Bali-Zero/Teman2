"use client";

import React, { useState } from "react";
import { Loader2, Send, ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";

// Keys match backend LKPMClientSubmission fields exactly
const INVESTMENT_CATEGORIES = [
  { key: "equipment", label: "Equipment & Machinery", hint: "Computers, machinery, furniture..." },
  { key: "building", label: "Building & Construction", hint: "Construction, renovation, office setup..." },
  { key: "vehicle", label: "Vehicles", hint: "Company cars, motorbikes..." },
  { key: "working_capital", label: "Working Capital", domesticOnly: true, hint: "Salaries, rent, bank deposits..." },
] as const;

// These backend fields have no domestic/import split
const SINGLE_FIELDS = [
  { key: "land", label: "Land (Hak Pakai / HGB)", hint: "Land lease, Hak Pakai, HGB..." },
  { key: "other", label: "Other Assets", hint: "Pre-operational, licensing costs..." },
] as const;

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"] as const;

export default function LKPMSubmitPage() {
  const router = useRouter();
  const { error, success } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const currentYear = new Date().getFullYear();
  const [quarter, setQuarter] = useState<string>(QUARTERS[0]);
  const [year, setYear] = useState<number>(currentYear);

  // Investment data — flat keys matching backend LKPMClientSubmission
  const [investment, setInvestment] = useState<Record<string, number>>({
    equipment_domestic: 0,
    equipment_import: 0,
    building_domestic: 0,
    building_import: 0,
    vehicle_domestic: 0,
    vehicle_import: 0,
    land: 0,
    working_capital: 0,
    other: 0,
  });

  const [tki, setTki] = useState(0);
  const [tka, setTka] = useState(0);
  const [revenueQuarterly, setRevenueQuarterly] = useState(0);
  const [revenueAnnual, setRevenueAnnual] = useState(0);
  const [obstacles, setObstacles] = useState("");
  const [plans, setPlans] = useState("");

  const updateInvestment = (field: string, value: string) => {
    const num = parseInt(value.replace(/\D/g, ""), 10) || 0;
    setInvestment((prev) => ({ ...prev, [field]: num }));
  };

  const formatNumber = (n: number) =>
    n > 0 ? new Intl.NumberFormat("id-ID").format(n) : "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const result = await api.post<{
        success: boolean;
        draft_id: number;
        quarter: string;
        year: number;
        realized_total: number;
      }>("/api/v1/lkpm/submit-data", {
        client_id: 0, // Backend resolves from auth context
        quarter,
        year,
        // Flat investment fields matching LKPMClientSubmission
        ...investment,
        tki,
        tka,
        quarterly_revenue: revenueQuarterly || 0,
        annual_revenue: revenueAnnual || 0,
        narrative_obstacles: obstacles || undefined,
        narrative_plans: plans || undefined,
      });
      success(
        "Data submitted successfully",
        `Draft created for ${result.quarter} ${result.year}`,
      );
      router.push(`/portal/lkpm/${result.quarter}?year=${result.year}`);
    } catch (err) {
      error("Submission failed", "Please check your data and try again");
      logger.error("LKPM submission failed", {}, err as Error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center gap-3">
        <Link href="/portal/lkpm">
          <ArrowLeft className="w-5 h-5" style={{ color: "var(--bz-text-2)" }} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Submit LKPM Data</h1>
          <p style={{ color: "var(--bz-text-2)" }}>
            Enter your quarterly investment activity data
          </p>
        </div>
      </section>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Period Selection */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
        >
          <h2 className="text-lg font-semibold">Reporting Period</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Quarter
              </label>
              <select
                value={quarter}
                onChange={(e) => setQuarter(e.target.value)}
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              >
                {QUARTERS.map((q) => (
                  <option key={q} value={q}>{q}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Year
              </label>
              <select
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              >
                {[currentYear, currentYear - 1, currentYear - 2].map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Investment Realization */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
        >
          <h2 className="text-lg font-semibold">Investment Realization (IDR)</h2>
          <div className="grid grid-cols-1 gap-4">
            {/* Categories with domestic/import split */}
            <div className="grid grid-cols-3 gap-3 text-xs font-medium" style={{ color: "var(--bz-text-2)" }}>
              <span>Category</span>
              <span>Domestic</span>
              <span>Import</span>
            </div>

            {INVESTMENT_CATEGORIES.map((cat) => (
              <div key={cat.key} className="grid grid-cols-3 gap-3 items-center">
                <div>
                  <span className="text-sm">{cat.label}</span>
                  <p className="text-[10px] mt-0.5" style={{ color: "var(--bz-text-2)" }}>{cat.hint}</p>
                </div>
                <input
                  type="text"
                  inputMode="numeric"
                  value={formatNumber(investment[cat.key === "working_capital" ? "working_capital" : `${cat.key}_domestic`])}
                  onChange={(e) => updateInvestment(cat.key === "working_capital" ? "working_capital" : `${cat.key}_domestic`, e.target.value)}
                  placeholder="0"
                  className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                  style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
                />
                {"domesticOnly" in cat && cat.domesticOnly ? (
                  <span className="text-xs text-center" style={{ color: "var(--bz-text-2)" }}>—</span>
                ) : (
                  <input
                    type="text"
                    inputMode="numeric"
                    value={formatNumber(investment[`${cat.key}_import`])}
                    onChange={(e) => updateInvestment(`${cat.key}_import`, e.target.value)}
                    placeholder="Imported"
                    className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                    style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
                  />
                )}
              </div>
            ))}

            {/* Single fields (no domestic/import split) */}
            {SINGLE_FIELDS.map((field) => (
              <div key={field.key} className="grid grid-cols-3 gap-3 items-center">
                <div>
                  <span className="text-sm">{field.label}</span>
                  <p className="text-[10px] mt-0.5" style={{ color: "var(--bz-text-2)" }}>{field.hint}</p>
                </div>
                <input
                  type="text"
                  inputMode="numeric"
                  value={formatNumber(investment[field.key])}
                  onChange={(e) => updateInvestment(field.key, e.target.value)}
                  placeholder="0"
                  className="w-full rounded-lg border px-3 py-2 text-sm text-right col-span-2"
                  style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
                />
              </div>
            ))}
          </div>
        </section>

        {/* Employment */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
        >
          <h2 className="text-lg font-semibold">Employment</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Indonesian Workers (TKI)
              </label>
              <input
                type="number"
                min="0"
                value={tki || ""}
                onChange={(e) => setTki(Number(e.target.value) || 0)}
                placeholder="Indonesian employees"
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Foreign Workers (TKA)
              </label>
              <input
                type="number"
                min="0"
                value={tka || ""}
                onChange={(e) => setTka(Number(e.target.value) || 0)}
                placeholder="KITAS holders"
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
              />
            </div>
          </div>
        </section>

        {/* Revenue */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
        >
          <h2 className="text-lg font-semibold">Revenue (IDR)</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Quarterly Revenue
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={formatNumber(revenueQuarterly)}
                onChange={(e) =>
                  setRevenueQuarterly(parseInt(e.target.value.replace(/\D/g, ""), 10) || 0)
                }
                placeholder="0"
                className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Annual Revenue
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={formatNumber(revenueAnnual)}
                onChange={(e) =>
                  setRevenueAnnual(parseInt(e.target.value.replace(/\D/g, ""), 10) || 0)
                }
                placeholder="0"
                className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
              />
            </div>
          </div>
        </section>

        {/* Narrative */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
        >
          <h2 className="text-lg font-semibold">Narrative</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Obstacles Encountered (optional)
              </label>
              <textarea
                value={obstacles}
                onChange={(e) => setObstacles(e.target.value)}
                placeholder="e.g. permit delays, supply chain issues, construction delays..."
                rows={3}
                className="w-full rounded-lg border px-3 py-2 text-sm resize-none"
                style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
              />
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: "var(--bz-text-2)" }}>
                Future Plans (optional)
              </label>
              <textarea
                value={plans}
                onChange={(e) => setPlans(e.target.value)}
                placeholder="e.g. hire 2 TKI, complete renovation, expand operations..."
                rows={3}
                className="w-full rounded-lg border px-3 py-2 text-sm resize-none"
                style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
              />
            </div>
          </div>
        </section>

        {/* Submit Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-6 py-2.5 rounded-lg text-sm font-medium text-white flex items-center gap-2 disabled:opacity-50"
            style={{ background: "var(--bz-accent-warm)" }}
          >
            {isSubmitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            {isSubmitting ? "Submitting..." : "Submit Data"}
          </button>
        </div>
      </form>
    </div>
  );
}
