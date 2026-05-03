"use client";

import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, Loader2 } from "lucide-react";
import { Activity, ThinkingPhrase } from "./types";

interface ThinkingActivitiesProps {
  activities: Activity[];
  currentPhrase: ThinkingPhrase;
  currentPhaseName: string | null;
  phraseIndex: number;
  interjectionIndex: number;
  interjections: string[];
}

export function ThinkingActivities({
  activities,
  currentPhrase,
  currentPhaseName,
  phraseIndex,
  interjectionIndex,
  interjections,
}: ThinkingActivitiesProps) {
  return (
    <AnimatePresence mode="wait">
      {activities.length > 0 ? (
        <motion.div
          key="activities"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-2.5"
        >
          {activities.map(
            (activity, idx) =>
              activity && (
                <motion.div
                  key={activity.key}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  className={`
                    flex items-center gap-2.5 text-xs p-2 rounded-lg
                    ${
                      activity.isCompleted
                        ? "bg-[var(--success)]/10 text-[var(--success)]"
                        : activity.isCurrent
                          ? "bg-[var(--accent)]/10 text-[var(--accent)]"
                          : "text-[var(--foreground-muted)]"
                    }
                  `}
                >
                  {activity.isCompleted ? (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ type: "spring" }}
                    >
                      <CheckCircle2 className="w-4 h-4" />
                    </motion.div>
                  ) : activity.isCurrent ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{
                        duration: 1,
                        repeat: Infinity,
                        ease: "linear",
                      }}
                    >
                      <Loader2 className="w-4 h-4" />
                    </motion.div>
                  ) : (
                    activity.icon
                  )}
                  <span className="font-medium">{activity.label}</span>
                  {activity.isCompleted && (
                    <motion.span
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="text-[10px] ml-auto opacity-70"
                    >
                      Done
                    </motion.span>
                  )}
                </motion.div>
              ),
          )}
        </motion.div>
      ) : (
        /* Rotating thinking phrases + Indonesian interjection */
        <div className="space-y-2">
          <motion.div
            key={`phrase-${phraseIndex}`}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex items-center gap-2.5 text-sm text-[var(--foreground-muted)] p-2 rounded-lg bg-[var(--background)]/50"
          >
            <motion.div
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ duration: 0.5, repeat: Infinity, repeatDelay: 2 }}
              className="text-[var(--accent)]"
            >
              {currentPhrase.icon}
            </motion.div>
            <span>
              {currentPhaseName
                ? `${currentPhaseName === "giant" ? "Analyzing complex regulations..." : currentPhaseName === "cell" ? "Calibrating with local data..." : "Finalizing answer..."}`
                : currentPhrase.text}
            </span>
          </motion.div>
          {/* Indonesian interjection - casual friendly touch */}
          <motion.div
            key={`interjection-${interjectionIndex}`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-xs text-[var(--foreground-muted)]/70 italic pl-2"
          >
            {interjections[interjectionIndex]}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
