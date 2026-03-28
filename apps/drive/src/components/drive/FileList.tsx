'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { getFileIcon, getDepartmentInfo } from './file-icon';
import { MoreVertical, ChevronDown } from 'lucide-react';
import { usePrefetchFolder } from '@/hooks/useDrive';

interface FileListProps {
  files: FileItem[];
  selectedFiles: Set<string>;
  onFileClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onFileDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
  // Infinite scroll props
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
  onLoadMore?: () => void;
}

type SortField = 'name' | 'modified' | 'size';
type SortDirection = 'asc' | 'desc';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.02,
    },
  },
};

const rowVariants = {
  hidden: { opacity: 0, x: -8 },
  visible: {
    opacity: 1,
    x: 0,
    transition: {
      type: 'spring' as const,
      stiffness: 400,
      damping: 30,
    },
  },
};

export function FileList({
  files,
  selectedFiles,
  onFileClick,
  onFileDoubleClick,
  onContextMenu,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
}: FileListProps) {
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const { prefetchFolder } = usePrefetchFolder();
  const sentinelRef = useRef<HTMLDivElement>(null);

  // Infinite scroll using Intersection Observer
  useEffect(() => {
    if (!sentinelRef.current || !onLoadMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          onLoadMore();
        }
      },
      { rootMargin: '200px', threshold: 0 }
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, onLoadMore]);

  // Safety: ensure files is always an array
  const safeFiles = Array.isArray(files) ? files : [];

  // Sort files - folders first, then by selected field
  const sortedFiles = [...safeFiles].sort((a, b) => {
    // Folders always first
    if (a.is_folder && !b.is_folder) return -1;
    if (!a.is_folder && b.is_folder) return 1;

    let comparison = 0;
    switch (sortField) {
      case 'name':
        comparison = a.name.localeCompare(b.name);
        break;
      case 'modified':
        comparison =
          new Date(a.modified_time || 0).getTime() - new Date(b.modified_time || 0).getTime();
        break;
      case 'size':
        comparison = (a.size || 0) - (b.size || 0);
        break;
    }
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const SortButton = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <button
      onClick={() => handleSort(field)}
      className={`
        flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium uppercase tracking-wider
        transition-colors hover:bg-slate-100 dark:hover:bg-slate-800
        ${sortField === field ? 'text-blue-600 dark:text-blue-400' : 'text-slate-500 dark:text-slate-400'}
      `}
    >
      {children}
      {sortField === field && (
        <ChevronDown
          className={`h-3 w-3 transition-transform duration-200 ${sortDirection === 'desc' ? 'rotate-180' : ''}`}
        />
      )}
    </button>
  );

  return (
    <div className="min-w-full">
      {/* Table Header - Elegant minimal */}
      <div className="sticky top-0 z-10 border-b border-slate-200/60 dark:border-slate-700/40 bg-slate-50/80 dark:bg-slate-900/80 backdrop-blur-md">
        <div className="grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-4 px-5 py-2">
          <span className="w-10" />
          <SortButton field="name">Nome</SortButton>
          <SortButton field="modified">
            <span className="hidden md:inline">Modificato</span>
          </SortButton>
          <SortButton field="size">Dim.</SortButton>
          <span className="w-8" />
        </div>
      </div>

      {/* Table Body */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="divide-y divide-slate-100 dark:divide-slate-800/50"
      >
        {sortedFiles.map((file, index) => {
          const isSelected = selectedFiles.has(file.id);
          const deptInfo = file.is_folder ? getDepartmentInfo(file.name) : null;

          return (
            <motion.div
              key={file.id}
              variants={rowVariants}
              onClick={(e) => onFileClick(file, index, e)}
              onDoubleClick={() => onFileDoubleClick(file)}
              onContextMenu={(e) => onContextMenu(file, e)}
              onMouseEnter={() => file.is_folder && prefetchFolder(file.id)}
              className={`
                group relative grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-4 px-5 py-2.5 cursor-pointer
                transition-all duration-150
                ${
                  isSelected
                    ? 'bg-blue-50/80 dark:bg-blue-950/40 hover:bg-blue-100/80 dark:hover:bg-blue-950/50'
                    : 'hover:bg-slate-50 dark:hover:bg-slate-800/50'
                }
              `}
            >
              {/* Icon */}
              <div className="flex w-10 justify-center">
                <div className="relative">
                  {getFileIcon(file, 'sm')}
                  {deptInfo && (
                    <div
                      className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full border-2 border-white dark:border-slate-900 shadow-sm"
                      style={{ backgroundColor: deptInfo.primary }}
                    />
                  )}
                </div>
              </div>

              {/* Name with department badge */}
              <div className="flex items-center gap-2 truncate">
                <span className="truncate text-[13px] font-medium text-slate-700 dark:text-slate-200">
                  {file.name}
                </span>
                {deptInfo && (
                  <span
                    className="shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide"
                    style={{
                      backgroundColor: `${deptInfo.primary}15`,
                      color: deptInfo.primary,
                    }}
                  >
                    {deptInfo.label}
                  </span>
                )}
              </div>

              {/* Modified Date */}
              <span className="hidden text-[13px] text-slate-400 dark:text-slate-500 md:block">
                {formatDate(file.modified_time)}
              </span>

              {/* Size */}
              <span className="w-20 text-right text-[13px] text-slate-400 dark:text-slate-500">
                {file.is_folder ? '--' : formatSize(file.size)}
              </span>

              {/* Actions - Minimal */}
              <div className="flex w-8 items-center justify-end opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onContextMenu(file, e);
                  }}
                  className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-slate-600 dark:hover:text-slate-300"
                  aria-label={`Azioni per ${file.name}`}
                >
                  <MoreVertical className="h-4 w-4" />
                </button>
              </div>

              {/* Selection indicator - Elegant checkmark */}
              {isSelected && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="absolute left-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-white shadow-sm"
                >
                  <svg
                    className="h-2.5 w-2.5"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </motion.div>
              )}
            </motion.div>
          );
        })}
      </motion.div>

      {/* Empty State - Elegant minimal */}
      {safeFiles.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
            Nessun file trovato
          </p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">Questa cartella è vuota</p>
        </div>
      )}

      {/* Infinite Scroll Sentinel & Loading Indicator */}
      {safeFiles.length > 0 && (
        <>
          <div ref={sentinelRef} className="h-1" aria-hidden="true" />
          {isFetchingNextPage && (
            <div className="flex items-center justify-center py-8">
              <div className="flex items-center gap-3 text-slate-400">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                <span className="text-[13px]">Caricamento...</span>
              </div>
            </div>
          )}
          {!hasNextPage && safeFiles.length >= 50 && (
            <div className="flex items-center justify-center py-6 text-[13px] text-slate-400">
              Tutti i file caricati
            </div>
          )}
        </>
      )}
    </div>
  );
}

const formatSize = (bytes: number | undefined) => {
  if (!bytes) return '--';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${units[unitIndex]}`;
};

const formatDate = (dateStr: string | undefined) => {
  if (!dateStr) return '--';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  // Show relative time for recent dates
  if (diffDays === 0) {
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    if (hours === 0) return 'Adesso';
    return `${hours}h fa`;
  }
  if (diffDays === 1) return 'Ieri';
  if (diffDays < 7) return `${diffDays}g fa`;

  // Show full date for older items
  return date.toLocaleDateString('it-IT', {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
};
