"use client";

import React from "react";
import { motion } from "framer-motion";
import { Search, Loader2, X, FileText, Scale, Activity } from "lucide-react";
import type { KBLIDetail } from "@/lib/api/kbli.api";

// =============================================================================
// HELPERS
// =============================================================================

export function getPmaBadge(status: string): {
  label: string;
  className: string;
} {
  const s = (status || "").toUpperCase();
  if (s === "TERBUKA")
    return {
      label: "Open to Foreign Investment",
      className: "badge badge-success",
    };
  if (s === "TERBATAS")
    return {
      label: "Restricted - Conditions Apply",
      className: "badge badge-warning",
    };
  if (s === "TERTUTUP")
    return {
      label: "Closed to Foreign Investment",
      className: "badge badge-error",
    };
  return { label: "Status Unknown", className: "badge badge-neutral" };
}

export function getRiskBadge(risk: string): {
  label: string;
  className: string;
} {
  const r = (risk || "").toLowerCase();
  if (r.includes("tinggi") && r.includes("menengah"))
    return { label: "Medium-High Risk", className: "badge badge-warning" };
  if (r.includes("tinggi") || r === "high")
    return { label: "High Risk", className: "badge badge-error" };
  if (r.includes("menengah") && r.includes("rendah"))
    return { label: "Medium-Low Risk", className: "badge badge-cyan" };
  if (r.includes("menengah") || r === "medium")
    return { label: "Medium Risk", className: "badge badge-warning" };
  if (r.includes("rendah") || r === "low")
    return { label: "Low Risk", className: "badge badge-info" };
  return { label: risk || "Unknown", className: "badge badge-neutral" };
}

export function getRiskLevel(
  risk: string,
): "low" | "medium-low" | "medium" | "medium-high" | "high" {
  const r = (risk || "").toLowerCase();
  if (r.includes("tinggi") && r.includes("menengah")) return "medium-high";
  if (r.includes("tinggi") || r === "high") return "high";
  if (r.includes("menengah") && r.includes("rendah")) return "medium-low";
  if (r.includes("menengah") || r === "medium") return "medium";
  return "low";
}

// =============================================================================
// INSPECTOR COMPONENT
// =============================================================================

const KBLIInspector = ({
  data,
  isLoading,
  onClose,
  onInspect,
}: {
  data: KBLIDetail | null;
  isLoading: boolean;
  onClose?: () => void;
  onInspect?: (code: string) => void;
}) => {
  if (isLoading) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-accent-sand">
        <Loader2 size={32} className="animate-spin mb-4" />
        <p className="text-xs uppercase tracking-widest opacity-50">
          Loading details...
        </p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-[#444] px-8 text-center">
        <Search size={48} className="mb-6 opacity-20 stroke-1" />
        <p className="text-sm font-medium text-[#666] mb-2">
          Click on any result to see full details
        </p>
        <p className="text-xs text-[#444]">
          Licenses, restrictions, risk level and related business codes will
          appear here
        </p>
      </div>
    );
  }

  const pmaBadge = getPmaBadge(data.pma_status);
  const riskBadge = getRiskBadge(data.risk_profile);

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      className="h-full flex flex-col"
    >
      {/* Mobile close button */}
      {onClose && (
        <button
          onClick={onClose}
          className="md:hidden absolute top-4 right-4 z-10 p-2 rounded-full bg-surface-editorial-elevated text-[#888]"
        >
          <X size={18} />
        </button>
      )}
      {/* Drag handle for mobile */}
      {onClose && (
        <div className="md:hidden flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-white/20" />
        </div>
      )}

      <div className="p-6 md:p-8 border-b border-white/5 bg-gradient-to-b from-[#0F1115] to-[#050507]">
        <div className="flex items-center gap-2 flex-wrap mb-4">
          <span className="px-3 py-1 rounded text-xs font-mono tracking-wider bg-accent-sand/10 text-accent-sand border border-accent-sand/20">
            KBLI {data.code}
          </span>
          <span className={pmaBadge.className}>{pmaBadge.label}</span>
        </div>
        <h2 className="text-2xl md:text-3xl font-serif text-[#F0F0F0] leading-tight mb-6">
          {data.title}
        </h2>

        <div className="space-y-3">
          <div className="flex justify-between items-center text-[11px] md:text-[10px] uppercase tracking-widest text-[#666]">
            <span className={riskBadge.className}>{riskBadge.label}</span>
            <span className="text-accent-sand">{data.licensing_status}</span>
          </div>
          <div className="h-[2px] w-full bg-surface-editorial-elevated relative">
            <div
              className="absolute top-0 left-0 h-full bg-accent-sand shadow-[0_0_10px_rgba(212,180,131,0.3)] transition-all duration-1000"
              style={{
                width: data.risk_profile.toLowerCase().includes("tinggi")
                  ? "90%"
                  : data.risk_profile.toLowerCase().includes("menengah")
                    ? "50%"
                    : "20%",
              }}
            />
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 md:p-8 space-y-10 custom-scrollbar">
        <section>
          <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <FileText size={12} /> Official Description
          </h3>
          <p className="text-sm text-[#CCC] leading-loose font-light border-l border-accent-sand/30 pl-5 italic">
            &ldquo;{data.description}&rdquo;
          </p>
        </section>

        {/* NEW: 2026 Business Intelligence Section */}
        {data.intel && (
          <section className="space-y-6">
            <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
              <Activity size={12} className="text-blue-400" /> 2026 Business
              Intelligence
            </h3>

            <div className="grid grid-cols-1 gap-4">
              <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl p-5">
                <h4 className="text-blue-400 font-bold text-[10px] uppercase tracking-wider mb-2">
                  What it Means
                </h4>
                <p className="text-[#CCC] text-xs leading-relaxed">
                  {data.intel.whatItMeans}
                </p>
              </div>
              <div className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-5">
                <h4 className="text-amber-400 font-bold text-[10px] uppercase tracking-wider mb-2">
                  What you Need
                </h4>
                <p className="text-[#CCC] text-xs leading-relaxed whitespace-pre-line">
                  {data.intel.whatYouNeed}
                </p>
              </div>
              <div className="bg-green-500/5 border border-green-500/20 rounded-xl p-5">
                <h4 className="text-green-400 font-bold text-[10px] uppercase tracking-wider mb-2">
                  The Bali Context
                </h4>
                <p className="text-[#CCC] text-xs leading-relaxed whitespace-pre-line">
                  {data.intel.baliContext}
                </p>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4 text-[10px] text-[#888] italic">
              <strong>2025 Transition:</strong> {data.intel.whatChanged}
            </div>
          </section>
        )}

        {data.licenses.length > 0 && (
          <section>
            <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
              <Scale size={12} /> Required Licenses
            </h3>
            <div className="space-y-4">
              {data.licenses.map((lic, idx) => (
                <div
                  key={idx}
                  className="group p-4 bg-[#0A0C10] rounded border border-white/5 hover:border-accent-sand/20 transition-all"
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-sm font-medium text-silver group-hover:text-white transition-colors">
                      {lic.type}
                    </span>
                    <span className="text-[10px] uppercase px-2 py-1 rounded-full bg-[#151921] text-[#888] border border-white/5">
                      {lic.sla}
                    </span>
                  </div>
                  <div className="flex flex-col gap-1 text-xs text-[#666]">
                    <span>
                      Business Size:{" "}
                      <span className="text-[#999]">
                        {lic.scale.join(", ")}
                      </span>
                    </span>
                    <span>
                      Risk Level:{" "}
                      <span className="text-[#999]">{lic.risk_level}</span>
                    </span>
                  </div>
                  {lic.requirements.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-white/5">
                      <p className="text-[10px] text-[#444] uppercase mb-2">
                        What you need to do:
                      </p>
                      <ul className="space-y-1">
                        {lic.requirements.slice(0, 3).map((req, ridx) => (
                          <li
                            key={ridx}
                            className="text-[11px] text-[#888] leading-tight"
                          >
                            &bull; {req}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        <section>
          <h3 className="text-[11px] md:text-[10px] font-bold uppercase tracking-[0.2em] text-[#555] mb-4 flex items-center gap-2">
            <Activity size={12} /> Related Business Codes
          </h3>
          <div className="flex flex-wrap gap-2">
            <div className="px-4 py-2 rounded-full bg-surface-deep text-xs text-accent-sand border border-accent-sand/20">
              Sector: {data.sector}
            </div>
            {data.related_codes.map((rel, idx) => (
              <button
                key={idx}
                onClick={() => onInspect?.(rel)}
                className="px-4 py-2 rounded-full bg-surface-deep text-xs text-[#888] border border-white/5 hover:border-accent-sand/30 hover:text-accent-sand cursor-pointer transition-all"
              >
                {rel}
              </button>
            ))}
          </div>
        </section>
      </div>
    </motion.div>
  );
};

export default KBLIInspector;
