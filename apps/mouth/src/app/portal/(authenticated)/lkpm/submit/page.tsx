"use client";

import React, { useState } from "react";
import { Loader2, Send, ArrowLeft, Globe } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";

type Lang = "en" | "id";

const T = {
  en: {
    title: "Submit LKPM Data",
    subtitle: "Enter your quarterly investment activity data",
    period: "Reporting Period",
    quarter: "Quarter",
    year: "Year",
    modalTetap: "Fixed Capital Realization (IDR)",
    component: "Component",
    domestic: "Domestic",
    import: "Import",
    building: "Building / Construction",
    buildingHint: "Construction, renovation, office setup",
    equipment: "Machinery / Equipment",
    equipmentHint: "Computers, machinery, furniture, office equipment",
    vehicle: "Vehicles",
    vehicleHint: "Company cars, motorbikes, operational vehicles",
    land: "Land Acquisition / Preparation",
    landHint: "Hak Pakai, HGB, land lease",
    other: "Others",
    otherHint: "Pre-operational costs, licensing, feasibility studies",
    modalKerja: "Working Capital — 1 Turnover (IDR)",
    modalKerjaHint: "Raw materials, salaries, utilities, spare parts, overhead",
    modalKerjaPlaceholder: "Total working capital for 1 operational cycle",
    employment: "Employment Data",
    tki: "Indonesian Workers (TKI)",
    tkiPlaceholder: "Local employees",
    tka: "Foreign Workers (TKA)",
    tkaPlaceholder: "KITAS holders",
    revenue: "Revenue (IDR)",
    revenueQ: "Quarterly Revenue",
    revenueY: "Annual Revenue",
    narrative: "Challenges & Plans",
    obstacles: "Challenges Encountered",
    obstaclesPlaceholder:
      "e.g. permit delays, supply chain issues, construction delays...",
    plans: "Plans for Next Period",
    plansPlaceholder:
      "e.g. hire 2 TKI, complete renovation, expand operations...",
    submit: "Submit Data",
    submitting: "Submitting...",
  },
  id: {
    title: "Submit Data LKPM",
    subtitle: "Input data realisasi investasi triwulanan",
    period: "Periode Pelaporan",
    quarter: "Triwulan",
    year: "Tahun",
    modalTetap: "Realisasi Modal Tetap (Rp)",
    component: "Komponen",
    domestic: "Domestik",
    import: "Impor",
    building: "Bangunan / Gedung",
    buildingHint: "Konstruksi, renovasi, pembangunan kantor",
    equipment: "Mesin / Peralatan",
    equipmentHint: "Komputer, mesin, furnitur, perlengkapan kantor",
    vehicle: "Kendaraan",
    vehicleHint: "Mobil, motor, kendaraan operasional",
    land: "Pembelian / Pematangan Tanah",
    landHint: "Hak Pakai, HGB, sewa tanah",
    other: "Lain-lain",
    otherHint: "Biaya pra-operasional, perizinan, studi kelayakan",
    modalKerja: "Modal Kerja — 1 Turnover (Rp)",
    modalKerjaHint:
      "Bahan baku, gaji/upah, listrik-air-telepon, suku cadang, overhead",
    modalKerjaPlaceholder: "Total modal kerja untuk 1 siklus operasional",
    employment: "Realisasi Tenaga Kerja",
    tki: "TKI (Tenaga Kerja Indonesia)",
    tkiPlaceholder: "Jumlah karyawan lokal",
    tka: "TKA (Tenaga Kerja Asing)",
    tkaPlaceholder: "Pemegang KITAS",
    revenue: "Pendapatan (Rp)",
    revenueQ: "Pendapatan Triwulan",
    revenueY: "Pendapatan Tahunan",
    narrative: "Kendala & Rencana",
    obstacles: "Permasalahan yang Dihadapi",
    obstaclesPlaceholder:
      "Contoh: keterlambatan perizinan, gangguan rantai pasokan...",
    plans: "Rencana Kegiatan Berikutnya",
    plansPlaceholder: "Contoh: penambahan 2 TKI, penyelesaian renovasi...",
    submit: "Kirim Data",
    submitting: "Mengirim...",
  },
} as const;

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"] as const;

export default function LKPMSubmitPage() {
  const router = useRouter();
  const { error, success } = useToast();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lang, setLang] = useState<Lang>("en");
  const t = T[lang];

  const currentYear = new Date().getFullYear();
  const [quarter, setQuarter] = useState<string>(QUARTERS[0]);
  const [year, setYear] = useState<number>(currentYear);

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
        client_id: 0,
        quarter,
        year,
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

  const modalTetap = [
    { key: "building", label: t.building, hint: t.buildingHint },
    { key: "equipment", label: t.equipment, hint: t.equipmentHint },
    { key: "vehicle", label: t.vehicle, hint: t.vehicleHint },
  ];

  const modalTetapSingle = [
    { key: "land", label: t.land, hint: t.landHint },
    { key: "other", label: t.other, hint: t.otherHint },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center gap-3">
        <Link href="/portal/lkpm">
          <ArrowLeft
            className="w-5 h-5"
            style={{ color: "var(--bz-text-2)" }}
          />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">{t.title}</h1>
          <p style={{ color: "var(--bz-text-2)" }}>{t.subtitle}</p>
        </div>
        <button
          type="button"
          onClick={() => setLang(lang === "en" ? "id" : "en")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border"
          style={{
            background: "var(--bz-surface)",
            borderColor: "var(--bz-border)",
            color: "var(--bz-text-2)",
          }}
        >
          <Globe className="w-3.5 h-3.5" />
          {lang === "en" ? "Bahasa" : "English"}
        </button>
      </section>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Period */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <h2 className="text-lg font-semibold">{t.period}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.quarter}
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
                  <option key={q} value={q}>
                    {q}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.year}
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
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* Modal Tetap */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <h2 className="text-lg font-semibold">{t.modalTetap}</h2>
          <div className="grid grid-cols-1 gap-4">
            <div
              className="grid grid-cols-3 gap-3 text-xs font-medium"
              style={{ color: "var(--bz-text-2)" }}
            >
              <span>{t.component}</span>
              <span>{t.domestic}</span>
              <span>{t.import}</span>
            </div>

            {modalTetap.map((cat) => (
              <div
                key={cat.key}
                className="grid grid-cols-3 gap-3 items-center"
              >
                <div>
                  <span className="text-sm">{cat.label}</span>
                  <p
                    className="text-[10px] mt-0.5"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    {cat.hint}
                  </p>
                </div>
                <input
                  type="text"
                  inputMode="numeric"
                  value={formatNumber(investment[`${cat.key}_domestic`])}
                  onChange={(e) =>
                    updateInvestment(`${cat.key}_domestic`, e.target.value)
                  }
                  placeholder="0"
                  className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                  style={{
                    background: "var(--bz-surface)",
                    borderColor: "var(--bz-border)",
                  }}
                />
                <input
                  type="text"
                  inputMode="numeric"
                  value={formatNumber(investment[`${cat.key}_import`])}
                  onChange={(e) =>
                    updateInvestment(`${cat.key}_import`, e.target.value)
                  }
                  placeholder="0"
                  className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                  style={{
                    background: "var(--bz-surface)",
                    borderColor: "var(--bz-border)",
                  }}
                />
              </div>
            ))}

            {modalTetapSingle.map((field) => (
              <div
                key={field.key}
                className="grid grid-cols-3 gap-3 items-center"
              >
                <div>
                  <span className="text-sm">{field.label}</span>
                  <p
                    className="text-[10px] mt-0.5"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    {field.hint}
                  </p>
                </div>
                <input
                  type="text"
                  inputMode="numeric"
                  value={formatNumber(investment[field.key])}
                  onChange={(e) => updateInvestment(field.key, e.target.value)}
                  placeholder="0"
                  className="w-full rounded-lg border px-3 py-2 text-sm text-right col-span-2"
                  style={{
                    background: "var(--bz-surface)",
                    borderColor: "var(--bz-border)",
                  }}
                />
              </div>
            ))}
          </div>
        </section>

        {/* Modal Kerja */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <div>
            <h2 className="text-lg font-semibold">{t.modalKerja}</h2>
            <p
              className="text-[10px] mt-1"
              style={{ color: "var(--bz-text-2)" }}
            >
              {t.modalKerjaHint}
            </p>
          </div>
          <input
            type="text"
            inputMode="numeric"
            value={formatNumber(investment.working_capital)}
            onChange={(e) =>
              updateInvestment("working_capital", e.target.value)
            }
            placeholder={t.modalKerjaPlaceholder}
            className="w-full rounded-lg border px-3 py-2 text-sm text-right"
            style={{
              background: "var(--bz-surface)",
              borderColor: "var(--bz-border)",
            }}
          />
        </section>

        {/* Employment */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <h2 className="text-lg font-semibold">{t.employment}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.tki}
              </label>
              <input
                type="number"
                min="0"
                value={tki || ""}
                onChange={(e) => setTki(Number(e.target.value) || 0)}
                placeholder={t.tkiPlaceholder}
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              />
            </div>
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.tka}
              </label>
              <input
                type="number"
                min="0"
                value={tka || ""}
                onChange={(e) => setTka(Number(e.target.value) || 0)}
                placeholder={t.tkaPlaceholder}
                className="w-full rounded-lg border px-3 py-2 text-sm"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              />
            </div>
          </div>
        </section>

        {/* Revenue */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <h2 className="text-lg font-semibold">{t.revenue}</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.revenueQ}
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={formatNumber(revenueQuarterly)}
                onChange={(e) =>
                  setRevenueQuarterly(
                    parseInt(e.target.value.replace(/\D/g, ""), 10) || 0,
                  )
                }
                placeholder="0"
                className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              />
            </div>
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.revenueY}
              </label>
              <input
                type="text"
                inputMode="numeric"
                value={formatNumber(revenueAnnual)}
                onChange={(e) =>
                  setRevenueAnnual(
                    parseInt(e.target.value.replace(/\D/g, ""), 10) || 0,
                  )
                }
                placeholder="0"
                className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              />
            </div>
          </div>
        </section>

        {/* Narrative */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
          }}
        >
          <h2 className="text-lg font-semibold">{t.narrative}</h2>
          <div className="space-y-4">
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.obstacles}
              </label>
              <textarea
                value={obstacles}
                onChange={(e) => setObstacles(e.target.value)}
                placeholder={t.obstaclesPlaceholder}
                rows={3}
                className="w-full rounded-lg border px-3 py-2 text-sm resize-none"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              />
            </div>
            <div>
              <label
                className="block text-xs mb-1"
                style={{ color: "var(--bz-text-2)" }}
              >
                {t.plans}
              </label>
              <textarea
                value={plans}
                onChange={(e) => setPlans(e.target.value)}
                placeholder={t.plansPlaceholder}
                rows={3}
                className="w-full rounded-lg border px-3 py-2 text-sm resize-none"
                style={{
                  background: "var(--bz-surface)",
                  borderColor: "var(--bz-border)",
                }}
              />
            </div>
          </div>
        </section>

        {/* Submit */}
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
            {isSubmitting ? t.submitting : t.submit}
          </button>
        </div>
      </form>
    </div>
  );
}
