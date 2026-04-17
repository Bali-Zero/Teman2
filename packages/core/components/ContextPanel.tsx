"use client";
import { useState, type ReactNode } from "react";

export interface ContextTab {
  id: string;
  label: string;
  render: () => ReactNode;
}

interface ContextPanelProps {
  open: boolean;
  tabs: ContextTab[];
  width?: number;
}

export function ContextPanel({ open, tabs, width = 360 }: ContextPanelProps) {
  const [active, setActive] = useState(tabs[0]?.id);
  if (!open || tabs.length === 0) return null;
  const current = tabs.find((t) => t.id === active) ?? tabs[0];
  return (
    <aside
      aria-label="Context panel"
      style={{
        width,
        borderLeft: "1px solid var(--color-border-subtle)",
        background: "var(--surface-raised)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        role="tablist"
        style={{
          display: "flex",
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={t.id === current.id}
            onClick={() => setActive(t.id)}
            style={{
              flex: 1,
              padding: "var(--space-3)",
              background: "transparent",
              border: "none",
              color: "var(--color-text-primary)",
              cursor: "pointer",
              borderBottom:
                t.id === current.id
                  ? "2px solid var(--accent-copper)"
                  : "2px solid transparent",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div
        role="tabpanel"
        style={{ flex: 1, padding: "var(--space-4)", overflow: "auto" }}
      >
        {current.render()}
      </div>
    </aside>
  );
}
