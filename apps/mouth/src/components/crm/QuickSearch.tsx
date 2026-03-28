"use client";

/**
 * QuickSearch Component
 *
 * Command palette per ricerca veloce clienti
 * Accesso rapido con Cmd+K / Ctrl+K
 */

import React, { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  X,
  User,
  FileText,
  Briefcase,
  Calendar,
  ArrowRight,
  Command,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useQuickSearch } from "@/hooks/useCrmSearch";
import { cn } from "@/lib/utils";
import type { Client } from "@/lib/api/crm/crm.types";

interface QuickSearchProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/**
 * Highlight matching text in search results
 */
function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;

  const parts = text.split(new RegExp(`(${query})`, "gi"));
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark
            key={i}
            className="bg-[var(--accent)]/20 text-[var(--accent)] rounded px-0.5"
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

/**
 * Client result item
 */
function ClientResult({
  client,
  query,
  isSelected,
  onSelect,
  index,
}: {
  client: Client;
  query: string;
  isSelected: boolean;
  onSelect: (client: Client) => void;
  index: number;
}) {
  const ref = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isSelected && ref.current) {
      ref.current.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [isSelected]);

  return (
    <button
      ref={ref}
      onClick={() => onSelect(client)}
      className={cn(
        "w-full text-left px-4 py-3 flex items-center gap-3 transition-colors",
        "hover:bg-[var(--background-secondary)]",
        isSelected && "bg-[var(--background-secondary)]",
      )}
    >
      <div className="w-10 h-10 rounded-full bg-[var(--accent)]/10 flex items-center justify-center flex-shrink-0">
        <User className="w-5 h-5 text-[var(--accent)]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-[var(--foreground)] truncate">
          <HighlightMatch text={client.full_name} query={query} />
        </p>
        <p className="text-sm text-[var(--foreground-muted)] truncate">
          {client.email && (
            <span className="mr-2">
              <HighlightMatch text={client.email} query={query} />
            </span>
          )}
          {client.phone && (
            <span>
              <HighlightMatch text={client.phone} query={query} />
            </span>
          )}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "px-2 py-0.5 text-xs rounded-full",
            client.status === "active" && "bg-green-500/20 text-green-500",
            client.status === "lead" && "bg-blue-500/20 text-blue-500",
            client.status === "completed" && "bg-purple-500/20 text-purple-500",
            client.status === "lost" && "bg-red-500/20 text-red-500",
            client.status === "inactive" && "bg-gray-500/20 text-gray-500",
          )}
        >
          {client.status}
        </span>
        <ArrowRight
          className={cn(
            "w-4 h-4 text-[var(--foreground-muted)] transition-opacity",
            isSelected ? "opacity-100" : "opacity-0",
          )}
        />
      </div>
    </button>
  );
}

/**
 * Empty state
 */
function EmptyState({ query }: { query: string }) {
  return (
    <div className="py-12 text-center">
      <Search className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
      <p className="text-[var(--foreground)] font-medium mb-1">
        No results found
      </p>
      <p className="text-sm text-[var(--foreground-muted)]">
        {query.length < 2
          ? "Type at least 2 characters to search"
          : `No clients match "${query}"`}
      </p>
    </div>
  );
}

/**
 * Quick search command palette
 */
export function QuickSearch({
  open: controlledOpen,
  onOpenChange,
}: QuickSearchProps = {}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [internalOpen, setInternalOpen] = React.useState(false);

  const isControlled = controlledOpen !== undefined;
  const isOpen = isControlled ? controlledOpen : internalOpen;
  const setOpen = isControlled ? onOpenChange! : setInternalOpen;

  const {
    query,
    setQuery,
    results,
    isLoading,
    selectedIndex,
    selectNext,
    selectPrev,
    selectedClient,
  } = useQuickSearch({ limit: 10 });

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Handle keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen(!isOpen);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, setOpen]);

  const handleSelect = (client: Client) => {
    setOpen(false);
    setQuery("");
    router.push(`/clients/${client.id}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        selectNext();
        break;
      case "ArrowUp":
        e.preventDefault();
        selectPrev();
        break;
      case "Enter":
        e.preventDefault();
        if (selectedClient) {
          handleSelect(selectedClient);
        }
        break;
      case "Escape":
        setOpen(false);
        break;
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setOpen}>
      <DialogContent className="max-w-2xl p-0 gap-0 overflow-hidden">
        <DialogHeader className="sr-only">
          <DialogTitle>Quick Search</DialogTitle>
        </DialogHeader>

        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-[var(--border)]">
          <Search className="w-5 h-5 text-[var(--foreground-muted)]" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search clients..."
            aria-label="Search clients"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent border-none outline-none text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]"
          />
          {isLoading && (
            <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          )}
          <div className="flex items-center gap-1 text-xs text-[var(--foreground-muted)] bg-[var(--background-secondary)] px-2 py-1 rounded">
            <Command className="w-3 h-3" />
            <span>K</span>
          </div>
        </div>

        {/* Results */}
        <div className="max-h-[400px] overflow-y-auto">
          {results.length > 0 ? (
            <div className="py-2">
              <div className="px-4 py-2 text-xs font-medium text-[var(--foreground-muted)] uppercase tracking-wider">
                Clients ({results.length})
              </div>
              {results.map((client, index) => (
                <ClientResult
                  key={client.id}
                  client={client}
                  query={query}
                  isSelected={index === selectedIndex}
                  onSelect={handleSelect}
                  index={index}
                />
              ))}
            </div>
          ) : query.length >= 2 ? (
            <EmptyState query={query} />
          ) : (
            <div className="py-8 text-center text-[var(--foreground-muted)]">
              <p className="text-sm">Start typing to search clients...</p>
              <div className="flex items-center justify-center gap-4 mt-4 text-xs">
                <div className="flex items-center gap-1">
                  <span className="px-1.5 py-0.5 bg-[var(--background-secondary)] rounded">
                    ↑↓
                  </span>
                  <span>Navigate</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="px-1.5 py-0.5 bg-[var(--background-secondary)] rounded">
                    ↵
                  </span>
                  <span>Select</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="px-1.5 py-0.5 bg-[var(--background-secondary)] rounded">
                    esc
                  </span>
                  <span>Close</span>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[var(--border)] bg-[var(--background-secondary)] text-xs text-[var(--foreground-muted)] flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <User className="w-3 h-3" />
              Clients
            </span>
          </div>
          <span>
            Press{" "}
            <kbd className="px-1.5 py-0.5 bg-[var(--background)] rounded">
              Cmd
            </kbd>{" "}
            +{" "}
            <kbd className="px-1.5 py-0.5 bg-[var(--background)] rounded">
              K
            </kbd>{" "}
            to open
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Trigger button for quick search
 */
export function QuickSearchTrigger({ className }: { className?: string }) {
  const [open, setOpen] = React.useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={cn(
          "flex items-center gap-2 px-3 py-2 text-sm text-[var(--foreground-muted)]",
          "bg-[var(--background-secondary)] hover:bg-[var(--background-elevated)]",
          "border border-[var(--border)] rounded-lg transition-colors",
          className,
        )}
      >
        <Search className="w-4 h-4" />
        <span className="hidden sm:inline">Search...</span>
        <span className="hidden md:flex items-center gap-0.5 ml-2 text-xs">
          <kbd className="px-1.5 py-0.5 bg-[var(--background)] rounded">⌘</kbd>
          <kbd className="px-1.5 py-0.5 bg-[var(--background)] rounded">K</kbd>
        </span>
      </button>
      <QuickSearch open={open} onOpenChange={setOpen} />
    </>
  );
}
