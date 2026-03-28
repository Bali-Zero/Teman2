'use client';

import React from 'react';
import { motion } from 'framer-motion';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { getFileIcon, getDepartmentInfo, DEPARTMENT_COLORS } from './file-icon';
import { MoreVertical, Clock, Users } from 'lucide-react';
import { usePrefetchFolder } from '@/hooks/useDrive';

interface FileGridProps {
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

// Animation variants for staggered grid
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 20, scale: 0.95 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: 'spring' as const,
      stiffness: 300,
      damping: 24,
    },
  },
};

export function FileGrid({
  files,
  selectedFiles,
  onFileClick,
  onFileDoubleClick,
  onContextMenu,
  hasNextPage,
  isFetchingNextPage,
  onLoadMore,
}: FileGridProps) {
  const { prefetchFolder } = usePrefetchFolder();

  // Infinite scroll using Intersection Observer
  const sentinelRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
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

  // Separate folders and files for better organization
  const folders = safeFiles.filter((f) => f.is_folder);
  const documents = safeFiles.filter((f) => !f.is_folder);

  return (
    <div className="p-5">
      {/* Folders Section */}
      {folders.length > 0 && (
        <div className="mb-6">
          <h3 className="mb-4 text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
            Cartelle
          </h3>
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7"
          >
            {folders.map((file, index) => (
              <FileCard
                key={file.id}
                file={file}
                index={index}
                isSelected={selectedFiles.has(file.id)}
                onClick={onFileClick}
                onDoubleClick={onFileDoubleClick}
                onContextMenu={onContextMenu}
                onPrefetch={prefetchFolder}
              />
            ))}
          </motion.div>
        </div>
      )}

      {/* Files Section */}
      {documents.length > 0 && (
        <div>
          <h3 className="mb-4 text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
            File
          </h3>
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7"
          >
            {documents.map((file, index) => (
              <FileCard
                key={file.id}
                file={file}
                index={folders.length + index}
                isSelected={selectedFiles.has(file.id)}
                onClick={onFileClick}
                onDoubleClick={onFileDoubleClick}
                onContextMenu={onContextMenu}
                onPrefetch={prefetchFolder}
              />
            ))}
          </motion.div>
        </div>
      )}

      {/* Empty State - Clean minimal design */}
      {safeFiles.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16">
          <div className="mb-4 rounded-2xl bg-slate-50 dark:bg-slate-800/50 p-6">
            <Users className="h-10 w-10 text-slate-300 dark:text-slate-600" />
          </div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
            Questa cartella è vuota
          </p>
          <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
            Trascina file qui o clicca "Nuovo" per creare contenuti
          </p>
        </div>
      )}

      {/* Infinite Scroll Sentinel & Loading Indicator */}
      {safeFiles.length > 0 && (
        <>
          <div ref={sentinelRef} className="h-1" aria-hidden="true" />
          {isFetchingNextPage && (
            <div className="flex items-center justify-center py-8">
              <div className="flex items-center gap-3 text-[var(--foreground-muted)]">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
                <span className="text-sm">Loading more files...</span>
              </div>
            </div>
          )}
          {!hasNextPage && safeFiles.length >= 50 && (
            <div className="flex items-center justify-center py-6 text-sm text-[var(--foreground-muted)]">
              All files loaded
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface FileCardProps {
  file: FileItem;
  index: number;
  isSelected: boolean;
  onClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
  onPrefetch?: (folderId: string) => void;
}

function FileCard({
  file,
  index,
  isSelected,
  onClick,
  onDoubleClick,
  onContextMenu,
  onPrefetch,
}: FileCardProps) {
  const deptInfo = file.is_folder ? getDepartmentInfo(file.name) : null;

  // Prefetch folder contents on hover for instant navigation
  const handleMouseEnter = () => {
    if (file.is_folder && onPrefetch) {
      onPrefetch(file.id);
    }
  };

  return (
    <motion.div
      variants={itemVariants}
      onClick={(e) => onClick(file, index, e)}
      onDoubleClick={() => onDoubleClick(file)}
      onContextMenu={(e) => onContextMenu(file, e)}
      onMouseEnter={handleMouseEnter}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      className={`
        group relative flex cursor-pointer flex-col items-center rounded-xl p-4
        transition-all duration-200 ease-out
        ${
          isSelected
            ? 'bg-blue-50/80 dark:bg-blue-950/40 ring-1 ring-blue-400/50 dark:ring-blue-500/40'
            : 'bg-white/60 dark:bg-slate-800/40 hover:bg-slate-50 dark:hover:bg-slate-800/60 border border-slate-200/40 dark:border-slate-700/30 hover:border-slate-300/60 dark:hover:border-slate-600/50'
        }
      `}
    >
      {/* Quick actions - Clean minimal style */}
      <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onContextMenu(file, e);
          }}
          className="rounded-lg bg-white/80 dark:bg-slate-700/80 p-1.5 text-slate-400 backdrop-blur-sm transition-colors hover:bg-white hover:text-slate-600 dark:hover:bg-slate-600 dark:hover:text-slate-200"
          aria-label={`Azioni per ${file.name}`}
        >
          <MoreVertical className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Icon container - Clean and minimal */}
      <div className="relative mb-3 transition-transform duration-200 group-hover:scale-[1.02]">
        {getFileIcon(file, 'lg')}
      </div>

      {/* File name - Clean typography */}
      <span className="w-full truncate text-center text-[13px] font-medium text-slate-700 dark:text-slate-200">
        {file.name}
      </span>

      {/* Meta info for files */}
      {!file.is_folder && (
        <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-slate-400 dark:text-slate-500">
          <span>{formatSize(file.size)}</span>
          {file.modified_time && (
            <>
              <span className="text-slate-300 dark:text-slate-600">·</span>
              <span>{formatRelativeTime(file.modified_time)}</span>
            </>
          )}
        </div>
      )}

      {/* Folder type indicator */}
      {file.is_folder && deptInfo && (
        <span
          className="mt-1.5 text-[10px] font-medium uppercase tracking-wide"
          style={{ color: deptInfo.primary }}
        >
          {deptInfo.label}
        </span>
      )}

      {/* Selection indicator - Subtle checkmark */}
      {isSelected && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-white shadow-sm"
        >
          <svg
            className="h-3 w-3"
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

const formatRelativeTime = (dateStr: string) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
};
