"use client";

import * as React from "react";
import { X } from "lucide-react";

interface ExitIntentProps {
  title: string;
  description: string;
  ctaLabel: string;
  ctaHref: string;
  /** sessionStorage key; set per page to avoid cross-landing collisions. */
  storageKey: string;
  /** Minimum ms on page before the popup can fire. Default 30s. */
  minDwellMs?: number;
  /** Disable on narrow viewports (no mouseleave semantic on touch). */
  minViewportPx?: number;
  onShow?: () => void;
  onDismiss?: (reason: "cta" | "close") => void;
}

export function ExitIntent({
  title,
  description,
  ctaLabel,
  ctaHref,
  storageKey,
  minDwellMs = 30_000,
  minViewportPx = 1024,
  onShow,
  onDismiss,
}: Readonly<ExitIntentProps>) {
  const [open, setOpen] = React.useState(false);
  const shownRef = React.useRef(false);
  const mountedAt = React.useRef<number>(0);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.innerWidth < minViewportPx) return;
    if (window.sessionStorage.getItem(storageKey) === "seen") return;

    mountedAt.current = Date.now();

    const fire = () => {
      if (shownRef.current) return;
      if (Date.now() - mountedAt.current < minDwellMs) return;
      shownRef.current = true;
      window.sessionStorage.setItem(storageKey, "seen");
      setOpen(true);
      onShow?.();
    };

    const onMouseOut = (e: MouseEvent) => {
      if (e.relatedTarget) return;
      if (e.clientY > 0) return;
      fire();
    };

    document.addEventListener("mouseout", onMouseOut);
    return () => document.removeEventListener("mouseout", onMouseOut);
  }, [storageKey, minDwellMs, minViewportPx, onShow]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        onDismiss?.("close");
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onDismiss]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="exit-intent-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.6)" }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          setOpen(false);
          onDismiss?.("close");
        }
      }}
    >
      <div
        className="relative max-w-md w-full rounded-2xl p-6 sm:p-8"
        style={{
          backgroundColor: "var(--bz-base, #0c0c0e)",
          border: "1px solid rgba(255,255,255,0.1)",
        }}
      >
        <button
          type="button"
          aria-label="Close"
          onClick={() => {
            setOpen(false);
            onDismiss?.("close");
          }}
          className="absolute top-3 right-3 p-1 rounded-full hover:bg-white/10"
        >
          <X size={18} aria-hidden="true" />
        </button>
        <h2 id="exit-intent-title" className="text-xl font-bold mb-2">
          {title}
        </h2>
        <p
          className="text-sm mb-6"
          style={{ color: "var(--tx-secondary, rgba(255,255,255,0.65))" }}
        >
          {description}
        </p>
        <a
          href={ctaHref}
          onClick={() => {
            setOpen(false);
            onDismiss?.("cta");
          }}
          className="inline-flex items-center justify-center w-full px-6 py-3 rounded-xl font-semibold"
          style={{
            backgroundColor: "var(--bz-accent, #d4845a)",
            color: "#fff",
          }}
        >
          {ctaLabel}
        </a>
      </div>
    </div>
  );
}
