'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Grid,
  List,
  Plus,
  Upload,
  Loader2,
  Cloud,
  CloudOff,
  FolderPlus,
  FileText,
  Table,
  Presentation,
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
    <div className="sticky top-0 z-20 border-b border-[var(--border)] bg-[var(--background)]/95 backdrop-blur-sm">
      <div className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
        {/* Search Bar */}
        <motion.div
          animate={{
            width: isSearchFocused ? '100%' : 'auto',
            maxWidth: isSearchFocused ? '600px' : '320px',
          }}
          transition={{ duration: 0.2 }}
          className="relative flex-1"
        >
          <div
            className={`
              relative flex items-center rounded-xl border-2 bg-[var(--background-subtle)] transition-all duration-200
              ${
                isSearchFocused
                  ? 'border-[#1a73e8] shadow-lg shadow-[#1a73e8]/10'
                  : 'border-transparent hover:border-[#dadce0]'
              }
            `}
          >
            <Search
              className={`
              ml-4 h-5 w-5 transition-colors
              ${isSearchFocused ? 'text-[#1a73e8]' : 'text-[var(--foreground-muted)]'}
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
              className="h-11 w-full bg-transparent px-3 text-sm text-[var(--foreground)] placeholder-[var(--foreground-muted)] focus:outline-none"
            />

            {/* Keyboard shortcut hint or clear button */}
            <AnimatePresence mode="wait">
              {searchQuery ? (
                <motion.button
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  onClick={() => onSearchChange('')}
                  className="mr-3 rounded-full p-1 hover:bg-[var(--accent)]"
                >
                  <X className="h-4 w-4 text-[var(--foreground-muted)]" />
                </motion.button>
              ) : (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="mr-3 flex items-center gap-1 rounded-md bg-[var(--background)] px-2 py-1 text-xs text-[var(--foreground-muted)]"
                >
                  <kbd className="font-mono">⌘</kbd>
                  <kbd className="font-mono">K</kbd>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {/* Connection status */}
          {!isConnected && onConnect && (
            <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }}>
              <Button
                variant="outline"
                size="sm"
                onClick={onConnect}
                disabled={isConnecting}
                className="border-amber-500/30 bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 dark:text-amber-400"
              >
                {isConnecting ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CloudOff className="mr-2 h-4 w-4" />
                )}
                Connetti Drive
              </Button>
            </motion.div>
          )}

          {/* View mode toggle */}
          <div className="flex rounded-lg border border-[#dadce0] bg-white dark:bg-[var(--background-subtle)] p-1">
            <button
              onClick={() => onViewModeChange('grid')}
              className={`
                relative flex items-center justify-center rounded-md p-2 transition-all duration-200
                ${
                  viewMode === 'grid'
                    ? 'text-[#1a73e8]'
                    : 'text-[#5f6368] hover:text-[#202124] hover:bg-[#f5f5f5]'
                }
              `}
              title="Vista griglia"
            >
              {viewMode === 'grid' && (
                <motion.div
                  layoutId="viewModeIndicator"
                  className="absolute inset-0 rounded-md bg-[#e8f0fe]"
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                />
              )}
              <Grid className="relative z-10 h-4 w-4" />
            </button>
            <button
              onClick={() => onViewModeChange('list')}
              className={`
                relative flex items-center justify-center rounded-md p-2 transition-all duration-200
                ${
                  viewMode === 'list'
                    ? 'text-[#1a73e8]'
                    : 'text-[#5f6368] hover:text-[#202124] hover:bg-[#f5f5f5]'
                }
              `}
              title="Vista lista"
            >
              {viewMode === 'list' && (
                <motion.div
                  layoutId="viewModeIndicator"
                  className="absolute inset-0 rounded-md bg-[#e8f0fe]"
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                />
              )}
              <List className="relative z-10 h-4 w-4" />
            </button>
          </div>

          {/* Info panel toggle */}
          {onToggleInfoPanel && (
            <button
              onClick={onToggleInfoPanel}
              className={`
                flex items-center justify-center rounded-full p-2 transition-all duration-200
                ${
                  showInfoPanel
                    ? 'bg-[#e8f0fe] text-[#1a73e8]'
                    : 'text-[#5f6368] hover:bg-[#f5f5f5]'
                }
                ${!hasSelection ? 'opacity-50 cursor-not-allowed' : ''}
              `}
              title={showInfoPanel ? 'Nascondi dettagli' : 'Mostra dettagli'}
              disabled={!hasSelection}
            >
              <Info className="h-5 w-5" />
            </button>
          )}

          <div className="mx-1 h-6 w-px bg-[#dadce0]" />

          {/* Upload Button */}
          <Button
            variant="outline"
            onClick={onUploadClick}
            className="border-[var(--border)] hover:border-blue-500/50 hover:bg-blue-500/10"
          >
            <Upload className="mr-2 h-4 w-4" />
            <span className="hidden sm:inline">Carica</span>
          </Button>

          {/* Create Button */}
          <Button
            onClick={onCreateClick}
            className="bg-white border border-[#dadce0] text-[#3c4043] shadow-sm hover:bg-[#f8f9fa] hover:shadow-md transition-all"
          >
            <Plus className="mr-2 h-4 w-4 text-[#1a73e8]" />
            <span className="hidden sm:inline">Nuovo</span>
            <ChevronDown className="ml-1 h-3 w-3 opacity-70" />
          </Button>
        </div>
      </div>
    </div>
  );
}
