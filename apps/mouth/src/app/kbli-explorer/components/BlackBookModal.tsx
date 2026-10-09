"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Send } from "lucide-react";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { trackKBLICTA } from "@/lib/analytics";

interface BlackBookModalProps {
  isOpen: boolean;
  onClose: () => void;
  detectedCode?: string;
}

/**
 * Entry point for the KBLI 2025 transition from /kbli-explorer.
 *
 * This used to be a "Black Book" lead form: it asked for an email and a
 * WhatsApp number, waited 1.5 s on a timer ("Simulate API call to CRM"),
 * sent nothing anywhere, and then claimed a dossier had been delivered
 * and that the team was looking at the visitor's company codes. No dossier
 * exists and no request was made. It now says what is true and
 * hands the visitor to the WhatsApp line the old success screen already used.
 */
export default function BlackBookModal({
  isOpen,
  onClose,
  detectedCode,
}: BlackBookModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-6"
          role="dialog"
          aria-modal="true"
          aria-labelledby="kbli-transition-title"
        >
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/90 backdrop-blur-md"
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="relative w-full max-w-lg bg-surface-deep border border-accent-sand/30 rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(212,180,131,0.1)]"
          >
            <div className="bg-surface-editorial-elevated p-4 flex items-center justify-between border-b border-white/5">
              <span className="text-xs uppercase tracking-[0.2em] font-bold text-accent-sand">
                KBLI 2025 transition
              </span>
              <button
                onClick={onClose}
                aria-label="Close"
                className="text-[#888] hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <div className="p-6 md:p-8 text-center">
              <h2
                id="kbli-transition-title"
                className="text-2xl md:text-3xl font-serif text-white mb-3"
              >
                {detectedCode
                  ? `Ask about KBLI ${detectedCode}`
                  : "Ask about your KBLI codes"}
              </h2>
              <p className="text-sm text-[#888] leading-relaxed mb-8">
                We don&apos;t have a downloadable guide to the 2025
                classification yet. Our team can tell you which KBLI 2025 code
                applies to your business and what changes for your NIB.
              </p>
              <div className="space-y-3">
                <a
                  href={buildWhatsAppLink("kbli")}
                  onClick={() => trackKBLICTA("consult_click")}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full py-4 bg-accent-sand text-[#050507] font-bold rounded-lg hover:bg-[#C4A473] transition-all"
                >
                  <Send size={16} />
                  Ask our team on WhatsApp
                </a>
                <button
                  onClick={onClose}
                  className="w-full py-3 bg-surface-editorial-elevated text-white font-medium rounded-lg hover:bg-[#252932] transition-all"
                >
                  Back to Explorer
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
