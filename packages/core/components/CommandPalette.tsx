"use client";
import { useEffect, useMemo, useState } from "react";

export interface CommandAction {
  id: string;
  label: string;
  group?: string;
  run: () => void | Promise<void>;
}

interface CommandPaletteProps {
  open: boolean;
  actions: CommandAction[];
  onClose: () => void;
}

export function CommandPalette({
  open,
  actions,
  onClose,
}: CommandPaletteProps) {
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return actions;
    return actions.filter((a) => a.label.toLowerCase().includes(needle));
  }, [q, actions]);

  useEffect(() => {
    if (open) {
      setQ("");
      setIdx(0);
    }
  }, [open]);

  if (!open) return null;

  function run(a: CommandAction) {
    Promise.resolve(a.run()).finally(onClose);
  }

  return (
    <div
      role="dialog"
      aria-label="Command palette"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        paddingTop: "15vh",
        zIndex: 400,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(560px, 90vw)",
          background: "var(--surface-raised)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-xl)",
        }}
      >
        <input
          role="combobox"
          aria-expanded
          autoFocus
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setIdx(0);
          }}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown")
              setIdx((i) => Math.min(i + 1, filtered.length - 1));
            if (e.key === "ArrowUp") setIdx((i) => Math.max(i - 1, 0));
            if (e.key === "Enter" && filtered[idx]) run(filtered[idx]);
            if (e.key === "Escape") onClose();
          }}
          placeholder="Digita un'azione…"
          style={{
            width: "100%",
            padding: "var(--space-4)",
            border: "none",
            background: "transparent",
            color: "var(--color-text-primary)",
            fontSize: "var(--font-size-lg)",
          }}
        />
        <ul
          style={{
            listStyle: "none",
            margin: 0,
            padding: 0,
            maxHeight: "50vh",
            overflow: "auto",
          }}
        >
          {filtered.map((a, i) => (
            <li
              key={a.id}
              aria-selected={i === idx}
              onClick={() => run(a)}
              style={{
                padding: "var(--space-3) var(--space-4)",
                cursor: "pointer",
                background:
                  i === idx ? "var(--surface-selected)" : "transparent",
              }}
            >
              {a.group ? (
                <span
                  style={{
                    color: "var(--color-text-secondary)",
                    marginRight: "var(--space-2)",
                  }}
                >
                  {a.group}
                </span>
              ) : null}
              {a.label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
