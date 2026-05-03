"use client";

import React, { useState } from "react";

interface AccordionSectionProps {
  id: string;
  icon: React.ReactNode;
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  hasContent?: boolean;
}

export function AccordionSection({
  icon,
  title,
  defaultOpen = false,
  children,
  hasContent = true,
}: AccordionSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (!hasContent) return null;

  return (
    <div className="border-b border-white/5 last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{icon}</span>
          <span className="text-sm font-medium text-slate-200">{title}</span>
        </div>
        <svg
          className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

interface LayerToggleProps {
  label: string;
  icon: string;
  enabled: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}

export function LayerToggle({
  label,
  icon,
  enabled,
  onChange,
  disabled = false,
}: LayerToggleProps) {
  return (
    <div
      className={`flex items-center justify-between py-2 ${
        disabled ? "opacity-40" : ""
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="text-sm">{icon}</span>
        <span className="text-xs text-slate-300">{label}</span>
        {disabled && (
          <span className="text-[10px] text-slate-600 ml-1">soon</span>
        )}
      </div>
      <button
        disabled={disabled}
        onClick={() => !disabled && onChange(!enabled)}
        className={`relative w-9 h-5 rounded-full transition-colors duration-200 ${
          enabled ? "bg-accent-warm" : "bg-white/10"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200 ${
            enabled ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </button>
    </div>
  );
}
