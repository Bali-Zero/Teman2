"use client";

import React, { useEffect, useRef, useState } from "react";
import { Loader2, Send, ArrowLeft, Search, User } from "lucide-react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";

const INVESTMENT_CATEGORIES = [
  { key: "land_building", label: "Land & Building" },
  { key: "machinery", label: "Machinery & Equipment" },
  { key: "equipment", label: "Tools & Equipment" },
  { key: "vehicles", label: "Vehicles" },
  { key: "other_fixed", label: "Other Fixed Assets" },
  { key: "working_capital", label: "Working Capital" },
] as const;

const QUARTERS = ["Q1", "Q2", "Q3", "Q4"] as const;

interface CRMClient {
  id: number;
  full_name: string;
  email?: string;
  phone?: string;
  nationality?: string;
}

export default function WorkspaceLKPMSubmitPage() {
  const router = useRouter();
  const { error, success } = useToast();
  const searchRef = useRef<HTMLDivElement>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Client selection — same pattern as process/new
  const [clients, setClients] = useState<CRMClient[]>([]);
  const [selectedClient, setSelectedClient] = useState<CRMClient | null>(null);
  const [clientSearch, setClientSearch] = useState("");
  const [isSearchingClients, setIsSearchingClients] = useState(false);
  const [showClientDropdown, setShowClientDropdown] = useState(false);

  // Period
  const currentYear = new Date().getFullYear();
  const [quarter, setQuarter] = useState<string>(QUARTERS[0]);
  const [year, setYear] = useState<number>(currentYear);

  // Investment data
  const [investment, setInvestment] = useState<Record<string, number>>(() => {
    const init: Record<string, number> = {};
    for (const cat of INVESTMENT_CATEGORIES) {
      init[`${cat.key}_domestic`] = 0;
      init[`${cat.key}_import`] = 0;
    }
    return init;
  });

  const [tki, setTki] = useState(0);
  const [tka, setTka] = useState(0);
  const [revenueQuarterly, setRevenueQuarterly] = useState(0);
  const [revenueAnnual, setRevenueAnnual] = useState(0);
  const [obstacles, setObstacles] = useState("");
  const [plans, setPlans] = useState("");

  // Debounced client search — same as process/new
  useEffect(() => {
    const searchClients = async () => {
      if (!clientSearch.trim()) {
        setClients([]);
        return;
      }
      setIsSearchingClients(true);
      try {
        const results = await api.crm.getClients({
          search: clientSearch,
          limit: 20,
        });
        setClients(results);
      } catch (err) {
        logger.error("Failed to search clients for LKPM", {}, err as Error);
      } finally {
        setIsSearchingClients(false);
      }
    };

    const debounce = setTimeout(searchClients, 300);
    return () => clearTimeout(debounce);
  }, [clientSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowClientDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const updateInvestment = (field: string, value: string) => {
    const num = parseInt(value.replace(/\D/g, ""), 10) || 0;
    setInvestment((prev) => ({ ...prev, [field]: num }));
  };

  const formatNumber = (n: number) =>
    n > 0 ? new Intl.NumberFormat("id-ID").format(n) : "";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedClient) {
      error("Missing Client", "Please select a client to submit LKPM data for.");
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await api.post<{
        success: boolean;
        draft_id: number;
        quarter: string;
        year: number;
        realized_total: number;
      }>("/api/v1/lkpm/submit-data", {
        client_id: selectedClient.id,
        quarter,
        year,
        investment,
        employment: { tki, tka },
        revenue_quarterly: revenueQuarterly || undefined,
        revenue_annual: revenueAnnual || undefined,
        obstacles: obstacles || undefined,
        plans: plans || undefined,
      });
      success(
        "Data submitted",
        `Draft created for ${selectedClient.full_name} — ${result.quarter} ${result.year}`,
      );
      router.push("/lkpm");
    } catch (err) {
      error("Submission failed", "Please check your data and try again");
      logger.error("LKPM workspace submission failed", {}, err as Error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section className="flex items-center gap-3">
        <Link href="/lkpm">
          <ArrowLeft className="w-5 h-5" style={{ color: "var(--bz-text-2)" }} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Submit LKPM Data</h1>
          <p style={{ color: "var(--bz-text-2)" }}>
            Enter quarterly investment data on behalf of a client
          </p>
        </div>
      </section>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Client Selection — same UX as process/new */}
        <section
          className="rounded-xl border p-6 space-y-4"
          style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
        >
          <h2 className="text-lg font-semibold">
            Client <span className="text-red-500">*</span>
          </h2>

          <div className="relative" ref={searchRef}>
            {selectedClient ? (
              <div
                className="flex items-center justify-between p-3 rounded-lg border"
                style={{ background: "rgba(201,169,110,0.1)", borderColor: "rgba(201,169,110,0.3)" }}
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center"
                    style={{ background: "rgba(201,169,110,0.2)" }}
                  >
                    <User className="w-4 h-4" style={{ color: "var(--bz-accent-warm)" }} />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{selectedClient.full_name}</p>
                    <p className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                      {selectedClient.email || selectedClient.phone || "No contact info"}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedClient(null);
                    setClientSearch("");
                  }}
                  className="text-xs px-2 py-1 rounded"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  Change
                </button>
              </div>
            ) : (
              <>
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
                  style={{ color: "var(--bz-text-2)" }}
                />
                <input
                  type="text"
                  value={clientSearch}
                  onChange={(e) => {
                    setClientSearch(e.target.value);
                    setShowClientDropdown(true);
                  }}
                  onFocus={() => setShowClientDropdown(true)}
                  placeholder="Search client by name or email..."
                  className="w-full rounded-lg border pl-9 pr-3 py-2 text-sm"
                  style={{
                    background: "var(--bz-surface)",
                    borderColor: "var(--bz-border)",
                  }}
                />
                {isSearchingClients && (
                  <Loader2
                    className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin"
                    style={{ color: "var(--bz-text-2)" }}
                  />
                )}

                {/* Search Results Dropdown */}
                {showClientDropdown && clientSearch && (
                  <div
                    className="absolute z-10 w-full mt-1 rounded-lg border shadow-lg max-h-60 overflow-y-auto"
                    style={{ background: "var(--bz-card)", borderColor: "var(--bz-border)" }}
                  >
                    {clients.length > 0 ? (
                      clients.map((client) => (
                        <button
                          key={client.id}
                          type="button"
                          onClick={() => {
                            setSelectedClient(client);
                            setShowClientDropdown(false);
                          }}
                          className="w-full text-left px-4 py-3 transition-colors flex items-center justify-between border-b last:border-0 hover:bg-[var(--bz-surface)]"
                          style={{ borderColor: "var(--bz-border)" }}
                        >
                          <div>
                            <p className="text-sm font-medium">{client.full_name}</p>
                            <p className="text-xs" style={{ color: "var(--bz-text-2)" }}>
                              {client.email || client.phone || "No contact info"}
                            </p>
                          </div>
                          {client.nationality && (
                            <span
                              className="text-xs px-2 py-0.5 rounded"
                              style={{ background: "var(--bz-surface)", color: "var(--bz-text-2)" }}
                            >
                              {client.nationality}
                            </span>
                          )}
                        </button>
                      ))
                    ) : (
                      <div className="p-4 text-center text-sm" style={{ color: "var(--bz-text-2)" }}>
                        {isSearchingClients ? "Searching..." : "No clients found"}
                      </div>
                    )}
                    {clients.length === 20 && (
                      <div
                        className="px-4 py-2 text-xs border-t"
                        style={{ color: "var(--bz-text-2)", borderColor: "var(--bz-border)" }}
                      >
                        Showing top 20 results. Type more to refine search.
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </section>

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
            <div className="grid grid-cols-3 gap-3 text-xs font-medium" style={{ color: "var(--bz-text-2)" }}>
              <span>Category</span>
              <span>Domestic</span>
              <span>Import</span>
            </div>

            {INVESTMENT_CATEGORIES.map((cat) => (
              <div key={cat.key} className="grid grid-cols-3 gap-3 items-center">
                <span className="text-sm">{cat.label}</span>
                <input
                  type="text"
                  inputMode="numeric"
                  value={formatNumber(investment[`${cat.key}_domestic`])}
                  onChange={(e) => updateInvestment(`${cat.key}_domestic`, e.target.value)}
                  placeholder="0"
                  className="w-full rounded-lg border px-3 py-2 text-sm text-right"
                  style={{ background: "var(--bz-surface)", borderColor: "var(--bz-border)" }}
                />
                <input
                  type="text"
                  inputMode="numeric"
                  value={formatNumber(investment[`${cat.key}_import`])}
                  onChange={(e) => updateInvestment(`${cat.key}_import`, e.target.value)}
                  placeholder="0"
                  className="w-full rounded-lg border px-3 py-2 text-sm text-right"
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
                placeholder="0"
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
                placeholder="0"
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
                placeholder="Describe any obstacles encountered during this period..."
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
                placeholder="Describe plans for the next period..."
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
            disabled={isSubmitting || !selectedClient}
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
