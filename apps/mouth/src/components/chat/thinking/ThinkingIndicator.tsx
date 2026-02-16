"use client";

/**
 * ThinkingIndicator - Visual indicator for AI reasoning process
 *
 * PERFORMANCE NOTE: This component uses motion components which can impact INP.
 * The component has been modularized for better maintainability and tree-shaking.
 */

import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ThinkingIndicatorProps, GenericStep } from "./types";
import { THINKING_PHRASES, INDONESIAN_INTERJECTIONS } from "./constants";
import { buildActivities } from "./utils";
import { ThinkingAvatar } from "./ThinkingAvatar";
import { ThinkingProgress } from "./ThinkingProgress";
import { ThinkingActivities } from "./ThinkingActivities";
import { ThinkingPhases } from "./ThinkingPhases";

export const ThinkingIndicator: React.FC<ThinkingIndicatorProps> = ({
  isVisible,
  steps = [],
  elapsedTime = 0,
  maxSteps = 3,
  currentStep = 0,
}) => {
  const [phraseIndex, setPhraseIndex] = useState(0);
  const [interjectionIndex, setInterjectionIndex] = useState(0);

  // Rotate through thinking phrases every 4 seconds
  useEffect(() => {
    if (!isVisible) return;
    const interval = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % THINKING_PHRASES.length);
    }, 4000);
    return () => clearInterval(interval);
  }, [isVisible]);

  // Rotate through Indonesian interjections every 3 seconds
  useEffect(() => {
    if (!isVisible) return;
    const interval = setInterval(() => {
      setInterjectionIndex(
        (prev) => (prev + 1) % INDONESIAN_INTERJECTIONS.length,
      );
    }, 3000);
    return () => clearInterval(interval);
  }, [isVisible]);

  if (!isVisible) return null;

  // Get tool events from steps
  const toolCalls = steps.filter(
    (s) => s.type === "tool_call" || s.type === "tool_start",
  );
  const toolEnds = steps.filter((s) => s.type === "tool_end");
  const thinkingSteps = steps.filter((s) => s.type === "thinking");

  // Detect active phase and reasoning steps
  const phases = steps.filter((s) => s.type === "phase");
  const reasoningSteps = steps.filter((s) => s.type === "reasoning_step");

  const latestPhase = phases.length > 0 ? phases[phases.length - 1] : null;
  const latestReasoning =
    reasoningSteps.length > 0
      ? reasoningSteps[reasoningSteps.length - 1]
      : null;

  // Type-safe data extraction
  const latestReasoningData = latestReasoning?.data as
    | Record<string, unknown>
    | undefined;
  const latestPhaseData = latestPhase?.data as
    | Record<string, unknown>
    | undefined;
  const currentPhaseName =
    (latestReasoningData?.phase as string) ||
    (latestPhaseData?.name as string) ||
    null;
  const currentMessage = (latestReasoningData?.message as string) || null;

  // Calculate actual step from thinking events
  const actualStep =
    thinkingSteps.length > 0 ? thinkingSteps.length : currentStep || 1;

  // Build activity list
  const activities = buildActivities(
    toolCalls as GenericStep[],
    toolEnds as GenericStep[],
  );

  const currentPhrase = THINKING_PHRASES[phraseIndex];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.95 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="flex w-full justify-start mb-6"
    >
      <div className="flex max-w-[85%] md:max-w-[75%] gap-3">
        <ThinkingAvatar />

        {/* Thinking Card */}
        <div className="flex flex-col items-start min-w-0">
          <motion.div
            className="
              relative px-5 py-4 rounded-2xl shadow-lg
              bg-gradient-to-br from-[var(--background-elevated)] to-[var(--background-secondary)]
              text-[var(--foreground)]
              rounded-tl-sm border border-[var(--accent)]/20
              min-w-[300px] overflow-hidden
            "
          >
            {/* Animated shimmer effect */}
            <motion.div
              className="absolute inset-0 opacity-20"
              style={{
                background:
                  "linear-gradient(45deg, transparent 0%, rgba(139, 92, 246, 0.1) 50%, transparent 100%)",
              }}
              animate={{ x: ["-100%", "100%"] }}
              transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
            />

            <ThinkingProgress
              actualStep={actualStep}
              maxSteps={maxSteps}
              elapsedTime={elapsedTime}
            />

            {currentPhaseName && (
              <ThinkingPhases
                currentPhaseName={currentPhaseName}
                currentMessage={currentMessage}
                latestReasoningData={latestReasoningData}
              />
            )}

            <ThinkingActivities
              activities={activities}
              currentPhrase={currentPhrase}
              currentPhaseName={currentPhaseName}
              phraseIndex={phraseIndex}
              interjectionIndex={interjectionIndex}
              interjections={INDONESIAN_INTERJECTIONS}
            />

            {/* Sources counter with animation */}
            {toolEnds.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="mt-4 pt-3 border-t border-[var(--border)]/30 flex items-center gap-2"
              >
                <motion.div
                  animate={{ scale: [1, 1.2, 1] }}
                  transition={{ duration: 0.5 }}
                  className="w-5 h-5 rounded-full bg-[var(--success)]/20 flex items-center justify-center"
                >
                  <span className="text-[10px] font-bold text-[var(--success)]">
                    {toolEnds.length}
                  </span>
                </motion.div>
                <span className="text-xs text-[var(--foreground-muted)]">
                  {toolEnds.length === 1 ? "source" : "sources"} found
                </span>
              </motion.div>
            )}
          </motion.div>
        </div>
      </div>
    </motion.div>
  );
};
