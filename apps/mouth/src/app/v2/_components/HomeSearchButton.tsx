"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { SearchModal } from "@/components/blog/SearchBar";

/**
 * Search button for the homepage NavShell. Opens a full-screen
 * SearchModal (the same one used by blog pages). Keyboard shortcut:
 * Cmd/Ctrl + K.
 */
export function HomeSearchButton() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Search articles"
        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide transition-colors hover:opacity-90"
        style={{
          background: "rgba(255,255,255,0.06)",
          border: "1px solid rgba(255,255,255,0.12)",
          color: "var(--text-secondary)",
        }}
      >
        <Search size={12} strokeWidth={2.2} />
        <span className="hidden md:inline">Search</span>
        <kbd
          className="hidden md:inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono rounded"
          style={{
            background: "rgba(255,255,255,0.08)",
            color: "var(--text-tertiary)",
          }}
        >
          ⌘K
        </kbd>
      </button>
      <SearchModal isOpen={open} onClose={() => setOpen(false)} />
    </>
  );
}
