"use client";

import React, { useEffect, useState } from "react";
import { Save, Plus, Settings } from "lucide-react";
import { toast } from "sonner";
import * as hrApi from "@/lib/api/hr/hr";
import type { BonusRate } from "@/types/hr";

function formatIDR(amount: number): string {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(amount);
}

export default function HRSettingsPage() {
  const [rates, setRates] = useState<BonusRate[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editAmount, setEditAmount] = useState("");
  const [newRate, setNewRate] = useState({
    practice_type_code: "",
    amount_idr: "",
  });
  const [showNew, setShowNew] = useState(false);

  useEffect(() => {
    hrApi
      .listBonusRates()
      .then((data) => {
        setRates(data.rates || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleSave = async (code: string, amount: number) => {
    try {
      await hrApi.upsertBonusRate({
        practice_type_code: code,
        amount_idr: amount,
      });
      setRates((prev) =>
        prev.map((r) =>
          r.practice_type_code === code ? { ...r, amount_idr: amount } : r,
        ),
      );
      setEditingId(null);
      toast.success("Rate saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save rate");
    }
  };

  const handleCreate = async () => {
    if (!newRate.practice_type_code || !newRate.amount_idr) return;
    try {
      const result = await hrApi.upsertBonusRate({
        practice_type_code: newRate.practice_type_code,
        amount_idr: Number(newRate.amount_idr),
      });
      setRates((prev) => [...prev, result.rate]);
      setNewRate({ practice_type_code: "", amount_idr: "" });
      setShowNew(false);
      toast.success("Rate created");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create rate");
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-100">HR Settings</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-zinc-900 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-100">
          <Settings size={24} className="inline mr-2 mb-1" />
          Bonus Rate Configuration
        </h1>
        <button
          onClick={() => setShowNew(!showNew)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[var(--bz-accent)]/10 text-[var(--bz-accent)] hover:bg-[var(--bz-accent)]/20 text-sm"
        >
          <Plus size={16} />
          Add Rate
        </button>
      </div>

      {showNew && (
        <div className="bg-zinc-900 border border-[var(--bz-accent)]/30 rounded-lg p-4 flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-xs text-zinc-400 mb-1">
              Practice Type Code
            </label>
            <input
              type="text"
              value={newRate.practice_type_code}
              onChange={(e) =>
                setNewRate((prev) => ({
                  ...prev,
                  practice_type_code: e.target.value,
                }))
              }
              placeholder="e.g. property_sale"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-200"
            />
          </div>
          <div className="w-40">
            <label className="block text-xs text-zinc-400 mb-1">
              Amount (IDR)
            </label>
            <input
              type="number"
              value={newRate.amount_idr}
              onChange={(e) =>
                setNewRate((prev) => ({ ...prev, amount_idr: e.target.value }))
              }
              placeholder="500000"
              className="w-full bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-sm text-zinc-200"
            />
          </div>
          <button
            onClick={handleCreate}
            className="px-3 py-1.5 rounded bg-[var(--bz-accent)] text-zinc-950 text-sm font-medium"
          >
            Create
          </button>
        </div>
      )}

      <div className="space-y-1">
        <div className="grid grid-cols-3 text-xs text-zinc-500 px-4 py-2 uppercase tracking-wider">
          <span>Practice Type</span>
          <span>Bonus Amount</span>
          <span>Status</span>
        </div>
        {rates.map((rate) => (
          <div
            key={rate.id}
            className="grid grid-cols-3 items-center bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-3"
          >
            <div>
              <span className="text-zinc-200">
                {rate.practice_type_code?.replace(/_/g, " ")}
              </span>
              {rate.practice_type_name && (
                <span className="text-xs text-zinc-500 ml-2">
                  ({rate.practice_type_name})
                </span>
              )}
            </div>
            <div>
              {editingId === rate.id ? (
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    value={editAmount}
                    onChange={(e) => setEditAmount(e.target.value)}
                    className="w-32 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-200"
                  />
                  <button
                    onClick={() =>
                      handleSave(rate.practice_type_code, Number(editAmount))
                    }
                    className="p-1 text-emerald-400 hover:text-emerald-300"
                  >
                    <Save size={14} />
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => {
                    setEditingId(rate.id);
                    setEditAmount(String(rate.amount_idr));
                  }}
                  className="text-[var(--bz-accent)] hover:underline"
                >
                  {formatIDR(rate.amount_idr)}
                </button>
              )}
            </div>
            <span
              className={`text-xs ${rate.is_active ? "text-emerald-400" : "text-zinc-500"}`}
            >
              {rate.is_active ? "Active" : "Inactive"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
