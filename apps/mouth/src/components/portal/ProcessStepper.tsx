"use client";

import React from "react";
import { CheckCircle, Circle, Loader, User } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProcessTimelineStep } from "@/lib/api/portal/portal.types";

interface ProcessStepperProps {
  steps: ProcessTimelineStep[];
  className?: string;
}

export function ProcessStepper({ steps, className }: ProcessStepperProps) {
  if (steps.length === 0) return null;

  return (
    <div className={cn("relative", className)}>
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1;

        return (
          <div key={`${step.status}-${index}`} className="flex gap-3">
            {/* Vertical line + dot — WS3 slice 4 (Day Edition): state colors
                read --state-* (WS2 operative-light AA overrides); neutral
                surfaces read --glass-rim (was rgba(255,255,255,0.05),
                invisible on paper). */}
            <div className="flex flex-col items-center">
              {step.completed ? (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{
                    background:
                      "color-mix(in srgb, var(--state-success) 15%, transparent)",
                  }}
                >
                  <CheckCircle
                    className="w-4 h-4"
                    style={{ color: "var(--state-success)" }}
                  />
                </div>
              ) : step.is_current ? (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 animate-pulse"
                  style={{
                    background:
                      "color-mix(in srgb, var(--state-info) 15%, transparent)",
                  }}
                >
                  <Loader
                    className="w-4 h-4 animate-spin"
                    style={{ color: "var(--state-info)" }}
                  />
                </div>
              ) : (
                <div
                  className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: "var(--glass-rim)" }}
                >
                  <Circle
                    className="w-3 h-3"
                    style={{ color: "var(--bz-text-3)" }}
                  />
                </div>
              )}
              {!isLast && (
                <div
                  className="w-0.5 flex-1 min-h-[24px]"
                  style={{
                    background: step.completed
                      ? "color-mix(in srgb, var(--state-success) 30%, transparent)"
                      : "var(--glass-rim)",
                  }}
                />
              )}
            </div>

            {/* Content */}
            <div className={cn("pb-4 flex-1 min-w-0", isLast && "pb-0")}>
              <p
                className={cn(
                  "text-sm font-medium",
                  step.is_current && "text-[var(--state-info)]",
                  step.completed && "text-[var(--bz-text-1)]",
                  !step.completed &&
                    !step.is_current &&
                    "text-[var(--text-tertiary,var(--bz-text-3))]",
                )}
              >
                {step.label}
              </p>
              {step.changed_at && (
                <p
                  className="text-xs mt-0.5"
                  style={{ color: "var(--text-tertiary, var(--bz-text-3))" }}
                >
                  {new Date(step.changed_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                  {step.changed_by && step.changed_by !== "system" && (
                    <span className="ml-1.5">
                      <User
                        className="w-3 h-3 inline -mt-0.5"
                        style={{ color: "var(--bz-text-3)" }}
                      />{" "}
                      {step.changed_by.split("@")[0]}
                    </span>
                  )}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
