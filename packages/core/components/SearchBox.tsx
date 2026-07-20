"use client";

import React, { useEffect, useRef } from "react";

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
}

const INPUT_BASE = "w-full pl-10 pr-4 py-2 rounded-lg focus:outline-none";

const SearchIcon = ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </svg>
);

const ClearIcon = ({ className, ...props }: React.SVGProps<SVGSVGElement>) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path d="m18 6-12 12" />
    <path d="m6 6 12 12" />
  </svg>
);

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

  return (
    <div className="relative flex-1">
      <SearchIcon
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4"
        style={{ color: "var(--bz-text-2)" }}
      />
      <input
        ref={inputRef}
        type="text"
        placeholder={placeholder}
        aria-label={ariaLabel}
        title={title}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
        className={className ? `${INPUT_BASE} ${className}` : INPUT_BASE}
        style={style}
      />
      {clearable && value && (
        <button
          type="button"
          onClick={() => onValueChange("")}
          className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors"
          style={{ color: "var(--bz-text-2)" }}
          aria-label="Clear search"
        >
          <ClearIcon className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
