'use client';

import { motion } from 'framer-motion';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { getFileIcon, getDepartmentInfo } from './file-icon';
import { MoreVertical, Star, ArrowUpDown, ChevronDown } from 'lucide-react';
import { useState } from 'react';

interface FileListProps {
  files: FileItem[];
  selectedFiles: Set<string>;
  onFileClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onFileDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
}

type SortField = 'name' | 'modified' | 'size';
type SortDirection = 'asc' | 'desc';

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.03,
    },
  },
};

const rowVariants = {
  hidden: { opacity: 0, x: -10 },
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

export function FileList({ files, selectedFiles, onFileClick, onFileDoubleClick, onContextMenu }: FileListProps) {
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  // Sort files - folders first, then by selected field
  const sortedFiles = [...files].sort((a, b) => {
    // Folders always first
    if (a.is_folder && !b.is_folder) return -1;
    if (!a.is_folder && b.is_folder) return 1;

    let comparison = 0;
    switch (sortField) {
      case 'name':
        comparison = a.name.localeCompare(b.name);
        break;
      case 'modified':
        comparison = new Date(a.modified_time || 0).getTime() - new Date(b.modified_time || 0).getTime();
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
        flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium uppercase tracking-wider
        transition-colors hover:bg-[var(--accent)]
        ${sortField === field ? 'text-emerald-600 dark:text-emerald-400' : 'text-[var(--foreground-muted)]'}
      `}
    >
      {children}
      {sortField === field && (
        <ChevronDown className={`h-3 w-3 transition-transform ${sortDirection === 'desc' ? 'rotate-180' : ''}`} />
      )}
    </button>
  );

  return (
    <div className="min-w-full">
      {/* Table Header */}
      <div className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--background-subtle)]/95 backdrop-blur-sm">
        <div className="grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-4 px-4 py-3">
          <span className="w-10" />
          <SortButton field="name">Nome</SortButton>
          <SortButton field="modified">
            <span className="hidden md:inline">Modificato</span>
          </SortButton>
          <SortButton field="size">Dimensione</SortButton>
          <span className="w-8" />
        </div>
      </div>

      {/* Table Body */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="divide-y divide-[var(--border)]"
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
              className={`
                group grid grid-cols-[auto_1fr_auto_auto_auto] items-center gap-4 px-4 py-3 cursor-pointer
                transition-all duration-150
                ${isSelected
                  ? 'bg-blue-500/10 hover:bg-blue-500/15'
                  : 'hover:bg-[var(--accent)]'
                }
              `}
            >
              {/* Icon */}
              <div className="flex w-10 justify-center">
                <div className="relative">
                  {getFileIcon(file, 'sm')}
                  {deptInfo && (
                    <div
                      className="absolute -bottom-1 -right-1 h-2 w-2 rounded-full border border-white shadow-sm"
                      style={{ backgroundColor: deptInfo.primary }}
                    />
                  )}
                </div>
              </div>

              {/* Name with department badge */}
              <div className="flex items-center gap-2 truncate">
                <span className="truncate text-sm font-medium text-[var(--foreground)]">
                  {file.name}
                </span>
                {deptInfo && (
                  <span
                    className="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white"
                    style={{ backgroundColor: deptInfo.primary }}
                  >
                    {deptInfo.label}
                  </span>
                )}
              </div>

              {/* Modified Date */}
              <span className="hidden text-sm text-[var(--foreground-muted)] md:block">
                {formatDate(file.modified_time)}
              </span>

              {/* Size */}
              <span className="w-20 text-right text-sm text-[var(--foreground-muted)]">
                {file.is_folder ? '--' : formatSize(file.size)}
              </span>

              {/* Actions */}
              <div className="flex w-8 items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  onClick={(e) => { e.stopPropagation(); }}
                  className="rounded p-1 hover:bg-[var(--background)] hover:text-amber-500"
                >
                  <Star className="h-4 w-4" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onContextMenu(file, e); }}
                  className="rounded p-1 hover:bg-[var(--background)]"
                >
                  <MoreVertical className="h-4 w-4" />
                </button>
              </div>

              {/* Selection indicator */}
              {isSelected && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="absolute left-2 flex h-4 w-4 items-center justify-center rounded-full bg-blue-500 text-white"
                >
                  <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </motion.div>
              )}
            </motion.div>
          );
        })}
      </motion.div>

      {/* Empty State */}
      {files.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-[var(--foreground-muted)]">
          <p className="text-lg font-medium">Nessun file trovato</p>
          <p className="text-sm">Questa cartella è vuota</p>
        </div>
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
    if (hours === 0) return 'Pochi minuti fa';
    return `${hours}h fa`;
  }
  if (diffDays === 1) return 'Ieri';
  if (diffDays < 7) return `${diffDays} giorni fa`;

  // Show full date for older items
  return date.toLocaleDateString('it-IT', {
    day: 'numeric',
    month: 'short',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
};
