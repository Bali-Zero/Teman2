'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Grid,
  List,
  Plus,
  Upload,
  Loader2,
  CloudOff,
  ChevronDown,
  X,
  Info,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState, useRef, useEffect } from 'react';

interface DriveToolbarProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  viewMode: 'grid' | 'list';
  onViewModeChange: (mode: 'grid' | 'list') => void;
  onUploadClick: () => void;
  onCreateClick: (e: React.MouseEvent) => void;
  isConnected: boolean;
  isConnecting?: boolean;
  onConnect?: () => void;
  showInfoPanel?: boolean;
  onToggleInfoPanel?: () => void;
  hasSelection?: boolean;
}

export function DriveToolbar({
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  onUploadClick,
  onCreateClick,
  isConnected,
  isConnecting,
  onConnect,
  showInfoPanel,
  onToggleInfoPanel,
  hasSelection,
}: DriveToolbarProps) {
  const [isSearchFocused, setIsSearchFocused] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
      if (e.key === 'Escape' && isSearchFocused) {
        searchInputRef.current?.blur();
        onSearchChange('');
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isSearchFocused, onSearchChange]);

  return (
    <div className="sticky top-0 z-20 border-b border-slate-200/60 dark:border-slate-700/40 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md">
      <div className="flex flex-col gap-3 px-5 py-3 md:flex-row md:items-center md:justify-between">
        {/* Search Bar - Elegant minimal */}
        <motion.div
          animate={{
            width: isSearchFocused ? '100%' : 'auto',
            maxWidth: isSearchFocused ? '520px' : '280px',
          }}
          transition={{ duration: 0.2 }}
          className="relative flex-1"
        >
          <div
            className={`
              relative flex items-center rounded-xl border bg-slate-50/80 dark:bg-slate-800/50 transition-all duration-200
              ${
                isSearchFocused
                  ? 'border-[var(--bz-accent)]/40 shadow-sm shadow-[var(--bz-accent)]/10 bg-white dark:bg-slate-800'
                  : 'border-slate-200/60 dark:border-slate-700/40 hover:border-slate-300 dark:hover:border-slate-600'
              }
            `}
          >
            <Search
              className={`
              ml-3.5 h-4 w-4 transition-colors
              ${isSearchFocused ? 'text-[var(--bz-accent)]' : 'text-slate-400'}
            `}
            />
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Cerca file e cartelle..."
              value={searchQuery}
              onChange={(e) => onSearchChange(e.target.value)}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setIsSearchFocused(false)}
              className="h-10 w-full bg-transparent px-3 text-[13px] text-slate-700 dark:text-slate-200 placeholder-slate-400 focus:outline-none"
            />

            {/* Keyboard shortcut hint or clear button */}
            <AnimatePresence mode="wait">
              {searchQuery ? (
                <motion.button
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  onClick={() => onSearchChange('')}
                  className="mr-2.5 rounded-full p-1 hover:bg-slate-100 dark:hover:bg-slate-700"
                  aria-label="Cancella ricerca"
                >
                  <X className="h-3.5 w-3.5 text-slate-400" />
                </motion.button>
              ) : (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="mr-2.5 flex items-center gap-0.5 rounded-md bg-slate-100/80 dark:bg-slate-700/50 px-1.5 py-0.5 text-[10px] text-slate-400"
                >
                  <kbd className="font-mono">⌘</kbd>
                  <kbd className="font-mono">K</kbd>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Actions - Clean minimal */}
        <div className="flex items-center gap-1.5">
          {/* Connection status */}
          {!isConnected && onConnect && (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <Button
                variant="outline"
                size="sm"
                onClick={onConnect}
                disabled={isConnecting}
                className="h-9 border-amber-400/40 bg-amber-50 dark:bg-amber-950/30 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-950/50"
              >
                {isConnecting ? (
                  <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <CloudOff className="mr-2 h-3.5 w-3.5" />
                )}
                Connetti Drive
              </Button>
            </motion.div>
          )}

          {/* View mode toggle - Elegant pill */}
          <div className="flex rounded-lg bg-slate-100/80 dark:bg-slate-800/50 p-0.5">
            <button
              onClick={() => onViewModeChange('grid')}
              className={`
                relative flex items-center justify-center rounded-md px-2.5 py-1.5 transition-all duration-200
                ${
                  viewMode === 'grid'
                    ? 'text-[var(--bz-accent)]'
                    : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                }
              `}
              title="Vista griglia"
              aria-label="Vista griglia"
            >
              {viewMode === 'grid' && (
                <motion.div
                  layoutId="viewModeIndicator"
                  className="absolute inset-0 rounded-md bg-white dark:bg-slate-700 shadow-sm"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
              <Grid className="relative z-10 h-4 w-4" />
            </button>
            <button
              onClick={() => onViewModeChange('list')}
              className={`
                relative flex items-center justify-center rounded-md px-2.5 py-1.5 transition-all duration-200
                ${
                  viewMode === 'list'
                    ? 'text-[var(--bz-accent)]'
                    : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-300'
                }
              `}
              title="Vista lista"
              aria-label="Vista lista"
            >
              {viewMode === 'list' && (
                <motion.div
                  layoutId="viewModeIndicator"
                  className="absolute inset-0 rounded-md bg-white dark:bg-slate-700 shadow-sm"
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
              <List className="relative z-10 h-4 w-4" />
            </button>
          </div>

          {/* Info panel toggle - Minimal */}
          {onToggleInfoPanel && (
            <button
              onClick={onToggleInfoPanel}
              className={`
                flex items-center justify-center rounded-lg p-2 transition-all duration-200
                ${
                  showInfoPanel
                    ? 'bg-[var(--bz-accent)]/10 text-[var(--bz-accent)]'
                    : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-600 dark:hover:text-slate-300'
                }
                ${!hasSelection ? 'opacity-40 cursor-not-allowed' : ''}
              `}
              title={showInfoPanel ? 'Nascondi dettagli' : 'Mostra dettagli'}
              aria-label={showInfoPanel ? 'Nascondi dettagli' : 'Mostra dettagli'}
              disabled={!hasSelection}
            >
              <Info className="h-4 w-4" />
            </button>
          )}

          <div className="mx-1.5 h-5 w-px bg-slate-200/60 dark:bg-slate-700/40" />

          {/* Upload Button - Subtle */}
          <Button
            variant="outline"
            size="sm"
            onClick={onUploadClick}
            className="h-9 border-slate-200/80 dark:border-slate-700/60 text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            <Upload className="h-3.5 w-3.5 sm:mr-1.5" />
            <span className="hidden sm:inline text-[13px]">Carica</span>
          </Button>

          {/* Create Button - Primary action */}
          <Button
            size="sm"
            onClick={onCreateClick}
            className="h-9 text-white shadow-sm hover:shadow-md transition-all"
            style={{ background: 'var(--bz-accent)' }}
          >
            <Plus className="h-3.5 w-3.5 sm:mr-1.5" />
            <span className="hidden sm:inline text-[13px] font-medium">Nuovo</span>
            <ChevronDown className="ml-0.5 h-3 w-3 opacity-70" />
          </Button>
        </div>
      </div>
    </div>
  );
}
