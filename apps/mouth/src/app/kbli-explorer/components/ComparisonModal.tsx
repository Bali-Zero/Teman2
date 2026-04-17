"use client";

import React, { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Loader2 } from "lucide-react";
import { kbliApi, KBLIDetail } from "@/lib/api/kbli.api";
import { getPmaBadge, getRiskBadge } from "./KBLIInspector";

interface ComparisonModalProps {
  codes: string[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const COLUMNS = [
  "Code",
  "Title",
  "PMA Status",
  "Risk Level",
  "Licenses",
  "Sector",
] as const;

export default function ComparisonModal({
  codes,
  open,
  onOpenChange,
}: ComparisonModalProps) {
  const [details, setDetails] = useState<(KBLIDetail | null)[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || codes.length === 0) return;
    setLoading(true);
    Promise.all(codes.map((code) => kbliApi.inspect(code).catch(() => null)))
      .then(setDetails)
      .finally(() => setLoading(false));
  }, [open, codes]);

  function getCellValue(
    detail: KBLIDetail,
    col: (typeof COLUMNS)[number],
  ): React.ReactNode {
    switch (col) {
      case "Code":
        return (
          <span className="font-mono text-accent-sand text-xs">
            {detail.code}
          </span>
        );
      case "Title":
        return <span className="text-sm text-silver">{detail.title}</span>;
      case "PMA Status": {
        const badge = getPmaBadge(detail.pma_status);
        return <span className={badge.className}>{badge.label}</span>;
      }
      case "Risk Level": {
        const badge = getRiskBadge(detail.risk_profile);
        return <span className={badge.className}>{badge.label}</span>;
      }
      case "Licenses":
        return (
          <div className="space-y-1">
            {detail.licenses.length === 0 ? (
              <span className="text-xs text-[#555]">None</span>
            ) : (
              detail.licenses.map((l, i) => (
                <div key={i} className="text-xs text-[#BBB]">
                  {l.type}
                </div>
              ))
            )}
          </div>
        );
      case "Sector":
        return <span className="text-xs text-[#999]">{detail.sector}</span>;
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay asChild>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 z-50"
          />
        </Dialog.Overlay>
        <Dialog.Content asChild>
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className="fixed top-[50%] left-[50%] -translate-x-1/2 -translate-y-1/2 z-50 w-[95vw] max-w-4xl max-h-[85vh] bg-[#0A0C10] border border-white/10 rounded-xl shadow-2xl overflow-hidden flex flex-col"
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b border-white/5">
              <div>
                <Dialog.Title className="text-lg font-serif text-[#F0F0F0]">
                  Compare KBLI Codes
                </Dialog.Title>
                <Dialog.Description className="text-xs text-[#666] mt-1">
                  Side-by-side comparison of {codes.length} business codes
                </Dialog.Description>
              </div>
              <Dialog.Close asChild>
                <button className="p-2 rounded-lg hover:bg-surface-editorial-elevated text-[#888] hover:text-white transition-colors" aria-label="Close comparison">
                  <X size={18} />
                </button>
              </Dialog.Close>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto custom-scrollbar p-6">
              {loading ? (
                <div className="flex items-center justify-center py-20 text-accent-sand">
                  <Loader2 size={24} className="animate-spin mr-3" />
                  <span className="text-sm">Loading details...</span>
                </div>
              ) : (
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      <th className="text-left text-[10px] uppercase tracking-widest text-[#555] py-3 px-3 border-b border-white/5 w-28">
                        Field
                      </th>
                      {details.map((d, i) => (
                        <th
                          key={i}
                          className="text-left text-[10px] uppercase tracking-widest text-accent-sand py-3 px-3 border-b border-white/5"
                        >
                          {d?.code || codes[i]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {COLUMNS.map((col) => (
                      <tr
                        key={col}
                        className="border-b border-white/5 last:border-0"
                      >
                        <td className="py-3 px-3 text-xs text-[#666] font-medium align-top whitespace-nowrap">
                          {col}
                        </td>
                        {details.map((d, i) => (
                          <td key={i} className="py-3 px-3 align-top">
                            {d ? (
                              getCellValue(d, col)
                            ) : (
                              <span className="text-xs text-[#444]">Error</span>
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </motion.div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
