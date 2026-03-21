"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Lock,
  CheckCircle2,
  Send,
  ShieldCheck,
  FileText,
} from "lucide-react";
import { toast } from "sonner";

interface BlackBookModalProps {
  isOpen: boolean;
  onClose: () => void;
  detectedCode?: string;
}

export default function BlackBookModal({
  isOpen,
  onClose,
  detectedCode,
}: BlackBookModalProps) {
  const [email, setEmail] = useState("");
  const [whatsapp, setWhatsApp] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !whatsapp) {
      toast.error("Please fill in all fields to unlock the dossier.");
      return;
    }

    setIsLoading(true);
    // Simulate API call to CRM
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setIsLoading(false);
    setSubmitted(true);
    toast.success("Intelligence Dossier sent to your inbox.");
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-6">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 bg-black/90 backdrop-blur-md"
          />

          {/* Modal Content */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="relative w-full max-w-lg bg-[#0F1115] border border-[#D4B483]/30 rounded-2xl overflow-hidden shadow-[0_0_50px_rgba(212,180,131,0.1)]"
          >
            {/* Header / Top Bar */}
            <div className="bg-[#1A1D24] p-4 flex items-center justify-between border-b border-white/5">
              <div className="flex items-center gap-2">
                <Lock size={14} className="text-[#D4B483]" />
                <span className="text-[10px] uppercase tracking-[0.3em] font-bold text-[#D4B483]">
                  Intelligence Briefing: RESTRICTED
                </span>
              </div>
              <button
                onClick={onClose}
                className="text-[#555] hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <div className="p-6 md:p-8">
              {!submitted ? (
                <>
                  <div className="text-center mb-8">
                    <div className="w-20 h-28 mx-auto mb-6 relative">
                      {/* Black Book Cover Mini representation */}
                      <div className="absolute inset-0 bg-[#050507] border border-[#D4B483]/40 rounded-sm shadow-2xl transform -rotate-3" />
                      <div className="absolute inset-0 bg-[#0A0C10] border border-[#D4B483]/20 rounded-sm shadow-xl flex flex-col items-center justify-center p-2 text-center">
                        <div className="text-[6px] uppercase tracking-[0.2em] text-[#D4B483] mb-1">
                          KBLI 2025
                        </div>
                        <div className="text-[8px] font-serif text-white leading-tight">
                          BLACK BOOK
                        </div>
                        <div className="mt-2 w-8 h-[1px] bg-[#D4B483]/30" />
                      </div>
                    </div>
                    <h2 className="text-2xl md:text-3xl font-serif text-white mb-3">
                      Unlock the Black Book.
                    </h2>
                    <p className="text-sm text-[#888] leading-relaxed">
                      We have identified{" "}
                      {detectedCode
                        ? `issues with KBLI ${detectedCode}`
                        : "critical vulnerabilities"}{" "}
                      in your current NIB. Unlock our restricted dossier on the
                      2025 migration successor codes and compliance moats.
                    </p>
                  </div>

                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest text-[#555] mb-2 px-1">
                        Business Email
                      </label>
                      <input
                        type="email"
                        required
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@company.com"
                        className="w-full bg-[#050507] border border-white/5 rounded-lg py-3 px-4 text-[#E1E1E3] focus:border-[#D4B483]/50 focus:outline-none transition-all"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase tracking-widest text-[#555] mb-2 px-1">
                        WhatsApp Number
                      </label>
                      <input
                        type="tel"
                        required
                        value={whatsapp}
                        onChange={(e) => setWhatsApp(e.target.value)}
                        placeholder="+62 ..."
                        className="w-full bg-[#050507] border border-white/5 rounded-lg py-3 px-4 text-[#E1E1E3] focus:border-[#D4B483]/50 focus:outline-none transition-all"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={isLoading}
                      className="w-full flex items-center justify-center gap-2 py-4 bg-[#D4B483] text-[#050507] font-bold rounded-lg hover:bg-[#C4A473] transition-all mt-6 disabled:opacity-50"
                    >
                      {isLoading ? (
                        <div className="w-5 h-5 border-2 border-[#050507]/30 border-t-[#050507] rounded-full animate-spin" />
                      ) : (
                        <>
                          <ShieldCheck size={18} />
                          <span>GRANT ACCESS & DOWNLOAD</span>
                        </>
                      )}
                    </button>
                  </form>
                  <p className="text-[9px] text-[#444] text-center mt-6 uppercase tracking-wider leading-relaxed">
                    By requesting access, you agree to a compliance audit by
                    Bali Zero. <br />
                    Intelligence is delivered via secure email.
                  </p>
                </>
              ) : (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="text-center py-8"
                >
                  <div className="w-16 h-16 bg-[#D4B483]/10 border border-[#D4B483]/20 rounded-full flex items-center justify-center mx-auto mb-6 text-[#D4B483]">
                    <CheckCircle2 size={32} />
                  </div>
                  <h2 className="text-2xl font-serif text-white mb-4">
                    Dossier Unlocked.
                  </h2>
                  <p className="text-[#888] text-sm leading-relaxed mb-8">
                    The KBLI 2025 Black Book has been dispatched to{" "}
                    <span className="text-[#D4B483]">{email}</span>. Our team is
                    also reviewing the status of your company codes.
                  </p>
                  <div className="space-y-3">
                    <button
                      onClick={onClose}
                      className="w-full py-3 bg-[#1A1D24] text-white font-medium rounded-lg hover:bg-[#252932] transition-all"
                    >
                      Back to Explorer
                    </button>
                    <a
                      href="https://wa.me/62812345678" // Example WhatsApp Link
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-2 w-full py-3 text-[#D4B483] text-sm font-bold border border-[#D4B483]/20 rounded-lg hover:bg-[#D4B483]/5 transition-all"
                    >
                      <Send size={14} />
                      PRIORITY AUDIT VIA WHATSAPP
                    </a>
                  </div>
                </motion.div>
              )}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
