"use client";

import React, { useEffect, useRef } from "react";
import { Search, X } from "lucide-react";
import { DESK_FIELD } from "./deskStrip";

export interface SearchBoxProps {
  value: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  ariaLabel?: string;
  title?: string;
  className?: string;
  style?: React.CSSProperties;
  clearable?: boolean;
  onDebouncedChange?: (value: string) => void;
  debounceMs?: number;
  /**
   * `"desk"` puts the box on the R19 control boundary: square, 44px, a 1px
   * `--line-control` edge instead of a rounded fill. Opt-in — the default
   * branch is byte-identical to what shipped, and the `/` shortcut, the
   * Escape behaviour and the debounce are the same in both.
   */
  variant?: "default" | "desk";
}

const INPUT_BASE = "w-full pl-10 pr-4 py-2 rounded-lg focus:outline-none";

/**
 * Standard list-page search input: leading search icon, `/` focuses it from
 * anywhere on the page, Escape blurs and clears, optional inline clear
 * button and optional debounced change notification.
 */
export function SearchBox({
  value,
  onValueChange,
  placeholder,
  ariaLabel,
  title,
  className,
  style,
  clearable = false,
  onDebouncedChange,
  debounceMs = 300,
  variant = "default",
}: SearchBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const callbacksRef = useRef({ onValueChange, onDebouncedChange });
  callbacksRef.current = { onValueChange, onDebouncedChange };

  // Keyboard shortcut: '/' to focus search, Escape to blur + clear.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      const isEditing =
        tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if (e.key === "/" && !isEditing) {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
      if (e.key === "Escape" && document.activeElement === inputRef.current) {
        inputRef.current?.blur();
        callbacksRef.current.onValueChange("");
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Optional debounce — fires after debounceMs of inactivity.
  useEffect(() => {
    if (!callbacksRef.current.onDebouncedChange) return;
    const timer = setTimeout(() => {
      callbacksRef.current.onDebouncedChange?.(value);
    }, debounceMs);
    return () => clearTimeout(timer);
  }, [value, debounceMs]);

  const desk = variant === "desk";
  const base = desk ? `${DESK_FIELD} pl-[34px]` : INPUT_BASE;

  return (
    <div className="relative flex-1">
      <Search
        className={
          desk
            ? "absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--tx-secondary)]"
            : "absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
        }
        style={desk ? undefined : { color: "var(--bz-text-2)" }}
      />
      <input
        ref={inputRef}
        type="text"
        placeholder={placeholder}
        aria-label={ariaLabel}
        title={title}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className={className ? `${base} ${className}` : base}
        style={desk ? undefined : style}
      />
      {clearable && value && (
        <button
          type="button"
          onClick={() => onValueChange("")}
          className={
            desk
              ? "absolute right-3 top-1/2 -translate-y-1/2 text-[var(--tx-secondary)] transition-colors hover:text-[var(--tx-pure)]"
              : "absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
          }
          style={desk ? undefined : { color: "var(--bz-text-2)" }}
          aria-label="Clear search"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
