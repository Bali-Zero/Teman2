"use client";

import { motion } from "framer-motion";
import {
  BookOpen,
  Scale,
  Sparkles,
  CheckCircle2,
  Lightbulb,
  ShieldAlert,
} from "lucide-react";

interface ThinkingPhasesProps {
  currentPhaseName: string | null;
  currentMessage: string | null;
  latestReasoningData?: Record<string, unknown>;
}

export function ThinkingPhases({
  currentPhaseName,
  currentMessage,
  latestReasoningData,
}: ThinkingPhasesProps) {
  if (!currentPhaseName) return null;

  const phases = [
    { id: "giant", label: "Giant", icon: <BookOpen className="w-3 h-3" /> },
    { id: "cell", label: "Cell", icon: <Scale className="w-3 h-3" /> },
    { id: "zantara", label: "Zantara", icon: <Sparkles className="w-3 h-3" /> },
  ];

  const currentIndex = phases.findIndex((p) => p.id === currentPhaseName);

  return (
    <div className="flex flex-col mb-3 px-1">
      <div className="flex items-center justify-between z-10 relative">
        {phases.map((phase, idx) => {
          const isActive = phase.id === currentPhaseName;
          const isCompleted = currentIndex > idx;

          return (
            <div key={phase.id} className="flex flex-col items-center gap-1">
              <motion.div
                initial={false}
                animate={{
                  backgroundColor: isActive
                    ? "rgba(var(--accent-rgb), 0.2)"
                    : isCompleted
                      ? "rgba(var(--success-rgb), 0.2)"
                      : "rgba(var(--foreground-rgb), 0.05)",
                  borderColor: isActive
                    ? "var(--accent)"
                    : isCompleted
                      ? "var(--success)"
                      : "transparent",
                  scale: isActive ? 1.1 : 1,
                }}
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center border-2 transition-colors bg-[var(--background)]
                  ${isActive ? "text-[var(--accent)]" : isCompleted ? "text-[var(--success)]" : "text-[var(--foreground-muted)]"}
                `}
              >
                {isCompleted ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : (
                  phase.icon
                )}
              </motion.div>
              <span
                className={`text-[10px] font-medium ${isActive ? "text-[var(--accent)]" : "text-[var(--foreground-muted)]"}`}
              >
                {phase.label}
              </span>
            </div>
          );
        })}
        {/* Progress Line */}
        <div className="absolute left-4 right-4 top-4 h-0.5 bg-[var(--border)] -z-10">
          <motion.div
            className="h-full bg-[var(--accent)]"
            initial={{ width: "0%" }}
            animate={{ width: `${(currentIndex / 2) * 100}%` }}
            transition={{ duration: 0.5 }}
          />
        </div>
      </div>

      {/* Current Message Display */}
      {currentMessage && (
        <motion.div
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          key={currentMessage}
          className="mt-3 text-center text-xs text-[var(--foreground-secondary)] font-medium"
        >
          {currentMessage}
        </motion.div>
      )}

      {/* Reasoning Details */}
      <ReasoningDetails latestReasoningData={latestReasoningData} />
    </div>
  );
}

function ReasoningDetails({
  latestReasoningData,
}: {
  latestReasoningData?: Record<string, unknown>;
}) {
  if (!latestReasoningData?.details) return null;

  const details = latestReasoningData.details as {
    key_points?: unknown[];
    corrections?: unknown[];
  };
  const isGiant = latestReasoningData?.phase === "giant";
  const isCell = latestReasoningData?.phase === "cell";

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="mt-3 bg-[var(--background)]/50 rounded-lg p-2 text-xs border border-[var(--border)]"
    >
      {isGiant && details.key_points && Array.isArray(details.key_points) && (
        <div className="flex items-center gap-2 text-[var(--accent)]">
          <Lightbulb className="w-3 h-3" />
          <span>
            Identified {details.key_points.length} key strategic points
          </span>
        </div>
      )}
      {isCell && details.corrections && Array.isArray(details.corrections) && (
        <div className="flex items-center gap-2 text-[var(--warning)]">
          <ShieldAlert className="w-3 h-3" />
          <span>Applied {details.corrections.length} corrections</span>
        </div>
      )}
    </motion.div>
  );
}
