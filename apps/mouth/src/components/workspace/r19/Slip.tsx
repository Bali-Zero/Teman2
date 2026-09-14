"use client";

import React from "react";
import { cn } from "@/lib/utils";

/**
 * The slip: a 44px-tall confirmation at the bottom of the desk, with an Undo
 * that is a real 44px target. `tone="you"` turns the left rule copper when the
 * slip is asking for something; the default forest rule means it is done.
 *
 * This is the SHAPE only. The toast system that mounts it, and the six-second
 * window, belong to the shell window — a primitive does not own a timer.
 *
 * The shell must not let it cover mobile controls: give it a bottom offset of
 * at least 64px under 768, so it never sits on top of a thumb-reachable
 * control at the foot of a small viewport.
 */
export function Slip({
  children,
  tone = "ok",
  onUndo,
  undoLabel = "Undo",
  onDismiss,
  className,
  style,
}: {
  children: React.ReactNode;
  tone?: "ok" | "you";
  onUndo?: () => void;
  undoLabel?: string;
  onDismiss?: () => void;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex min-h-11 max-w-[320px] items-center gap-2.5 rounded",
        "border border-[var(--bz-border)] border-l-[3px] bg-[var(--bz-card)]",
        "py-2.5 pl-2.5 pr-3.5 text-[12px] shadow-[var(--bz-shadow-card)]",
        tone === "you"
          ? "border-l-[var(--bz-copper)]"
          : "border-l-[var(--state-success)]",
        className,
      )}
      style={style}
    >
      <div className="min-w-0 flex-1">{children}</div>
      {onUndo ? (
        <button
          type="button"
          onClick={onUndo}
          className={cn(
            "ml-auto min-h-11 shrink-0 px-2.5 text-[12px] font-[650] text-[var(--bz-copper-text)]",
            "underline underline-offset-[3px]",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--bz-copper)]",
          )}
        >
          {undoLabel}
        </button>
      ) : null}
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="shrink-0 text-[var(--tx-secondary)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--bz-copper)]"
        >
          ×
        </button>
      ) : null}
    </div>
  );
}
