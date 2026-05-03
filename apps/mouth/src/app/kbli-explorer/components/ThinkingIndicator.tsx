"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, BarChart3, Sparkles } from "lucide-react";

const STAGES = [
  { icon: Search, text: "Searching 9,612 business codes...", delay: 0 },
  { icon: BarChart3, text: "Analyzing matches...", delay: 2500 },
  { icon: Sparkles, text: "Generating answer...", delay: 6000 },
];

const PROGRESS_DURATION = 12; // seconds to reach 95%

export default function ThinkingIndicator({
  isComplete,
}: {
  isComplete?: boolean;
}) {
  const [activeStage, setActiveStage] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const timers = STAGES.map((stage, idx) => {
      if (idx === 0) return null;
      return setTimeout(() => setActiveStage(idx), stage.delay);
    });
    return () => timers.forEach((t) => t && clearTimeout(t));
  }, []);

  // Animate progress bar
  useEffect(() => {
    if (isComplete) {
      setProgress(100);
      return;
    }
    const start = Date.now();
    const frame = () => {
      const elapsed = (Date.now() - start) / 1000;
      const pct = Math.min(95, (elapsed / PROGRESS_DURATION) * 95);
      setProgress(pct);
      if (pct < 95) rafId = requestAnimationFrame(frame);
    };
    let rafId = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(rafId);
  }, [isComplete]);

  return (
    <div className="flex gap-4 md:gap-6 items-start">
      <div className="w-8 h-8 rounded-full border bg-surface-deep border-accent-sand/20 text-accent-sand flex items-center justify-center shrink-0">
        <Sparkles size={14} />
      </div>
      <div className="flex-1 space-y-3 pt-1">
        <AnimatePresence mode="wait">
          {STAGES.map(
            (stage, idx) =>
              idx <= activeStage && (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: idx === activeStage ? 1 : 0.4, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="flex items-center gap-2.5"
                >
                  <stage.icon
                    size={14}
                    className={
                      idx === activeStage ? "text-accent-sand" : "text-[#555]"
                    }
                  />
                  <span
                    className={`text-sm ${idx === activeStage ? "text-[#CCC]" : "text-[#555]"}`}
                  >
                    {stage.text}
                  </span>
                  {idx < activeStage && (
                    <motion.span
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="text-emerald-400 text-xs"
                    >
                      ✓
                    </motion.span>
                  )}
                </motion.div>
              ),
          )}
        </AnimatePresence>

        {/* Progress bar */}
        <div className="h-[2px] w-full bg-surface-editorial-elevated rounded-full overflow-hidden mt-2">
          <motion.div
            className="h-full bg-gradient-to-r from-[#D4B483] to-[#C4A473]"
            style={{ width: `${progress}%` }}
            animate={isComplete ? { width: "100%" } : undefined}
            transition={
              isComplete
                ? { type: "spring", stiffness: 200, damping: 20 }
                : undefined
            }
          />
        </div>
      </div>
    </div>
  );
}
