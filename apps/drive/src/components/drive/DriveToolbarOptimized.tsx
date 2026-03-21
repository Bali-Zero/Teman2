"use client";

/**
 * DriveToolbarOptimized Component
 *
 * Toolbar ottimizzata con:
 * - Ricerca debounced
 * - Filtri avanzati
 * - Keyboard shortcuts
 * - Stato di sincronizzazione
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  Search,
  Grid3X3,
  List,
  Filter,
  ArrowUpDown,
  RefreshCw,
  X,
  Cloud,
  CloudOff,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useDebounce } from "@/lib/hooks/optimized/useDebounce";

interface DriveToolbarOptimizedProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  viewMode: "grid" | "list";
  onViewModeChange: (mode: "grid" | "list") => void;
  onUploadClick: () => void;
  onCreateClick: (e: React.MouseEvent) => void;
  isConnected: boolean;
  isSyncing?: boolean;
  lastSyncTime?: Date;
  showInfoPanel: boolean;
  onToggleInfoPanel: () => void;
  hasSelection: boolean;
  totalFiles?: number;
  selectedCount?: number;
  sortField?: "name" | "modified" | "size";
  sortDirection?: "asc" | "desc";
  onSortChange?: (field: "name" | "modified" | "size") => void;
  fileTypeFilter?: string;
  onFileTypeFilterChange?: (type: string) => void;
}

const FILE_TYPES = [
  { value: "all", label: "All Files" },
  { value: "folder", label: "Folders" },
  { value: "document", label: "Documents" },
  { value: "spreadsheet", label: "Spreadsheets" },
  { value: "presentation", label: "Presentations" },
  { value: "image", label: "Images" },
  { value: "video", label: "Videos" },
  { value: "pdf", label: "PDFs" },
];

export function DriveToolbarOptimized({
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  onUploadClick,
  onCreateClick,
  isConnected,
  isSyncing,
  lastSyncTime,
  showInfoPanel,
  onToggleInfoPanel,
  hasSelection,
  totalFiles,
  selectedCount,
  sortField = "name",
  sortDirection = "asc",
  onSortChange,
  fileTypeFilter = "all",
  onFileTypeFilterChange,
}: DriveToolbarOptimizedProps) {
  const [localQuery, setLocalQuery] = useState(searchQuery);
  const [showFilters, setShowFilters] = useState(false);
  const debouncedQuery = useDebounce(localQuery, 200);
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Update parent when debounced query changes
  useEffect(() => {
    onSearchChange(debouncedQuery);
  }, [debouncedQuery, onSearchChange]);

  // Sync local query with prop
  useEffect(() => {
    setLocalQuery(searchQuery);
  }, [searchQuery]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + K to focus search
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
      // Escape to clear search
      if (e.key === "Escape" && localQuery) {
        setLocalQuery("");
        onSearchChange("");
      }
      // Ctrl/Cmd + Shift + V to toggle view
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === "v") {
        e.preventDefault();
        onViewModeChange(viewMode === "grid" ? "list" : "grid");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [localQuery, onSearchChange, onViewModeChange, viewMode]);

  const handleClearSearch = useCallback(() => {
    setLocalQuery("");
    onSearchChange("");
    inputRef.current?.focus();
  }, [onSearchChange]);

  const getConnectionStatus = () => {
    if (isSyncing)
      return {
        icon: Loader2,
        text: "Syncing...",
        className: "text-[#d4845a] animate-spin",
      };
    if (!isConnected)
      return {
        icon: CloudOff,
        text: "Disconnected",
        className: "text-red-500",
      };
    return {
      icon: CheckCircle2,
      text: "Connected",
      className: "text-green-500",
    };
  };

  const status = getConnectionStatus();
  const StatusIcon = status.icon;

  return (
    <div className="border-b border-slate-200/60 dark:border-slate-700/40 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md">
      {/* Main Toolbar */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Search - Enhanced with better UX */}
        <div className="relative flex-1 max-w-xl">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            ref={inputRef}
            type="text"
            value={localQuery}
            onChange={(e) => setLocalQuery(e.target.value)}
            placeholder="Search files... (Ctrl+K)"
            className="w-full pl-10 pr-10 py-2 rounded-lg bg-slate-100/80 dark:bg-slate-800/80 border-0 text-sm focus:ring-2 focus:ring-[#d4845a]/20 placeholder:text-slate-400 transition-all"
          />
          {localQuery && (
            <button
              onClick={handleClearSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 hidden lg:inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-sans font-medium text-slate-400 bg-slate-200/50 dark:bg-slate-700/50 rounded">
            <span>Ctrl</span>
            <span>K</span>
          </kbd>
        </div>

        {/* Connection Status */}
        <div
          className={cn(
            "flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800",
            status.className,
          )}
        >
          <StatusIcon className="h-4 w-4" />
          <span className="hidden sm:inline text-xs font-medium">
            {status.text}
          </span>
        </div>

        <div className="flex-1" />

        {/* Actions */}
        <div className="flex items-center gap-1.5">
          {/* Filter Toggle */}
          {onFileTypeFilterChange && (
            <Button
              variant={showFilters ? "secondary" : "ghost"}
              size="icon"
              onClick={() => setShowFilters(!showFilters)}
              className={cn(
                "relative",
                fileTypeFilter !== "all" && "text-[#d4845a]",
              )}
            >
              <Filter className="h-4 w-4" />
              {fileTypeFilter !== "all" && (
                <span className="absolute -top-0.5 -right-0.5 h-2 w-2 bg-[#d4845a] rounded-full" />
              )}
            </Button>
          )}

          {/* View Mode Toggle */}
          <div className="flex items-center rounded-lg bg-slate-100 dark:bg-slate-800 p-1">
            <button
              onClick={() => onViewModeChange("grid")}
              className={cn(
                "p-1.5 rounded-md transition-all",
                viewMode === "grid"
                  ? "bg-white dark:bg-slate-700 shadow-sm text-[#d4845a]"
                  : "text-slate-400 hover:text-slate-600",
              )}
              title="Grid view (Ctrl+Shift+V)"
            >
              <Grid3X3 className="h-4 w-4" />
            </button>
            <button
              onClick={() => onViewModeChange("list")}
              className={cn(
                "p-1.5 rounded-md transition-all",
                viewMode === "list"
                  ? "bg-white dark:bg-slate-700 shadow-sm text-[#d4845a]"
                  : "text-slate-400 hover:text-slate-600",
              )}
              title="List view (Ctrl+Shift+V)"
            >
              <List className="h-4 w-4" />
            </button>
          </div>

          {/* Info Panel Toggle */}
          <Button
            variant={showInfoPanel ? "secondary" : "ghost"}
            size="sm"
            onClick={onToggleInfoPanel}
            className={cn(
              "hidden md:flex",
              hasSelection && !showInfoPanel && "text-[#d4845a]",
            )}
          >
            Info
          </Button>

          {/* New Button */}
          <Button
            onClick={onCreateClick}
            size="sm"
            className="text-white gap-1.5"
            style={{ background: "var(--bz-accent)" }}
          >
            <span className="hidden sm:inline">New</span>
            <span className="sm:hidden">+</span>
          </Button>
        </div>
      </div>

      {/* Filter Bar */}
      {showFilters && onFileTypeFilterChange && (
        <div className="flex items-center gap-4 px-4 py-2 border-t border-slate-200/60 dark:border-slate-700/40 bg-slate-50/50 dark:bg-slate-900/50">
          <span className="text-xs font-medium text-slate-500 uppercase">
            Filter by:
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            {FILE_TYPES.map((type) => (
              <button
                key={type.value}
                onClick={() => onFileTypeFilterChange(type.value)}
                className={cn(
                  "px-3 py-1 text-xs font-medium rounded-full transition-all",
                  fileTypeFilter === type.value
                    ? "bg-[#d4845a]/15 text-[#d4845a]"
                    : "bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-100",
                )}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Status Bar */}
      <div className="flex items-center justify-between px-4 py-1.5 border-t border-slate-200/60 dark:border-slate-700/40 bg-slate-50/30 dark:bg-slate-900/30 text-xs text-slate-500">
        <div className="flex items-center gap-4">
          {totalFiles !== undefined && (
            <span>
              {totalFiles.toLocaleString()} item{totalFiles !== 1 ? "s" : ""}
            </span>
          )}
          {selectedCount !== undefined && selectedCount > 0 && (
            <span className="text-[#d4845a] font-medium">
              {selectedCount} selected
            </span>
          )}
          {lastSyncTime && (
            <span className="hidden sm:inline">
              Last synced: {lastSyncTime.toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Sort Controls */}
        {onSortChange && (
          <div className="flex items-center gap-2">
            <ArrowUpDown className="h-3 w-3" />
            <select
              value={`${sortField}-${sortDirection}`}
              onChange={(e) => {
                const [field, dir] = e.target.value.split("-");
                onSortChange(field as "name" | "modified" | "size");
              }}
              className="bg-transparent border-0 text-xs focus:ring-0 cursor-pointer"
            >
              <option value="name-asc">Name (A-Z)</option>
              <option value="name-desc">Name (Z-A)</option>
              <option value="modified-desc">Last modified</option>
              <option value="modified-asc">Oldest first</option>
              <option value="size-desc">Largest first</option>
              <option value="size-asc">Smallest first</option>
            </select>
          </div>
        )}
      </div>
    </div>
  );
}
