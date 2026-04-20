"use client";

import { useCallback } from "react";

type VibrationPattern = number | number[];

/**
 * Wraps navigator.vibrate with two safety nets:
 *   1. No-op if the API is unavailable (Safari <16, non-mobile Safari, etc.)
 *   2. No-op if the user prefers reduced motion
 *
 * Spec: docs/superpowers/specs/2026-04-20-visa-check-ui-design.md
 *       §Mobile-first specifics (3 haptic moments)
 *       §Motion invariants (reduced-motion respected)
 */
export function useHaptic(): (pattern: VibrationPattern) => void {
  return useCallback((pattern: VibrationPattern) => {
    if (typeof window === "undefined") return;
    if (
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return;
    }
    if (typeof navigator === "undefined" || typeof navigator.vibrate !== "function") {
      return;
    }
    navigator.vibrate(pattern);
  }, []);
}
