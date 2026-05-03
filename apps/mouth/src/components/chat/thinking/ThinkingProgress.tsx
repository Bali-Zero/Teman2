"use client";

import { motion } from "framer-motion";

interface ThinkingProgressProps {
  actualStep: number;
  maxSteps: number;
  elapsedTime?: number;
}

export function ThinkingProgress({
  actualStep,
  maxSteps,
  elapsedTime = 0,
}: ThinkingProgressProps) {
  const progressPercent = Math.min((actualStep / maxSteps) * 100, 100);

  return (
    <>
      {/* Header with Step Counter */}
      <div className="relative flex items-center gap-3 mb-3">
        <div className="flex-1">
          <span className="text-sm font-semibold text-[var(--foreground)]">
            Zantara sta ragionando
          </span>
          <motion.span
            animate={{ opacity: [1, 0.3, 1] }}
            transition={{ duration: 1, repeat: Infinity }}
            className="text-[var(--accent)]"
          >
            ...
          </motion.span>
        </div>
        <div className="flex items-center gap-2">
          {/* Step counter badge */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="px-2 py-1 rounded-full bg-[var(--accent)]/20 text-[10px] font-bold text-[var(--accent)] border border-[var(--accent)]/30"
          >
            Step {actualStep}/{maxSteps}
          </motion.div>
          {elapsedTime > 0 && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="px-2 py-1 rounded-full bg-[var(--background)] text-[10px] font-mono text-[var(--foreground-muted)]"
            >
              {elapsedTime}s
            </motion.div>
          )}
        </div>
      </div>

      {/* Step Progress Bar */}
      <div className="relative h-2 bg-[var(--background)] rounded-full overflow-hidden mb-4">
        {/* Background segments for each step */}
        <div className="absolute inset-0 flex">
          {Array.from({ length: maxSteps }).map((_, i) => (
            <div
              key={i}
              className={`flex-1 ${i > 0 ? "border-l border-[var(--border)]/30" : ""}`}
            />
          ))}
        </div>
        {/* Filled progress */}
        <motion.div
          className="absolute inset-y-0 left-0 bg-gradient-to-r from-purple-500 via-blue-500 to-cyan-500"
          initial={{ width: "0%" }}
          animate={{ width: `${progressPercent}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
        {/* Shimmer effect */}
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent"
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
        />
      </div>
    </>
  );
}
