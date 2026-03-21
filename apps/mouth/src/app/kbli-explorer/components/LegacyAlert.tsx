"use client";

import React from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ShieldAlert, ArrowRight, Download } from "lucide-react";
import { KBLI_CONCORDANCE_2025, ConcordanceEntry } from "../concordance";

interface LegacyAlertProps {
  code: string;
  onOpenBlackBook: () => void;
}

export default function LegacyAlert({
  code,
  onOpenBlackBook,
}: LegacyAlertProps) {
  const entry = KBLI_CONCORDANCE_2025[code];

  if (!entry) return null;

  const isDanger = entry.status === "REVOKED" || entry.status === "CRITICAL";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`p-4 md:p-6 rounded-xl border-2 mb-6 ${
        isDanger
          ? "bg-red-500/10 border-red-500/30 text-red-200"
          : "bg-amber-500/10 border-amber-500/30 text-amber-200"
      }`}
    >
      <div className="flex items-start gap-4">
        <div
          className={`p-2 rounded-lg ${isDanger ? "bg-red-500/20" : "bg-amber-500/20"}`}
        >
          {isDanger ? (
            <ShieldAlert size={24} className="text-red-500" />
          ) : (
            <AlertTriangle size={24} className="text-amber-500" />
          )}
        </div>
        <div className="flex-1">
          <h3 className="font-serif text-lg md:text-xl font-bold mb-1 tracking-tight">
            2025 COMPLIANCE ALERT: KBLI {code}
          </h3>
          <p className="text-sm opacity-90 leading-relaxed mb-4">
            <span className="font-bold uppercase tracking-wider">
              {entry.status}:
            </span>{" "}
            {entry.reason}
            <br />
            <span className="mt-2 block italic opacity-80">{entry.impact}</span>
          </p>

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={onOpenBlackBook}
              className="group flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[#D4B483] text-[#050507] text-sm font-bold hover:bg-[#C4A473] transition-all"
            >
              <Download size={16} />
              <span>UNLOCK 2025 BLACK BOOK</span>
              <ArrowRight
                size={14}
                className="group-hover:translate-x-1 transition-transform"
              />
            </button>

            <div className="flex items-center gap-2 px-3 py-2 text-[10px] uppercase tracking-[0.2em] font-bold opacity-60">
              <div className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              Extraction Protocol Available
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
