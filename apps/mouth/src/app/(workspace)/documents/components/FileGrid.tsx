'use client';

import { motion } from 'framer-motion';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { getFileIcon, getDepartmentInfo, DEPARTMENT_COLORS } from './file-icon';
import { MoreVertical, Star, Clock, Users } from 'lucide-react';

interface FileGridProps {
  files: FileItem[];
  selectedFiles: Set<string>;
  onFileClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onFileDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
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
}: FileGridProps) {
  // Separate folders and files for better organization
  const folders = files.filter((f) => f.is_folder);
  const documents = files.filter((f) => !f.is_folder);

  return (
    <div className="p-6">
      {/* Folders Section */}
      {folders.length > 0 && (
        <div className="mb-8">
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--foreground-muted)] uppercase tracking-wider">
            <span className="h-px flex-1 bg-gradient-to-r from-[var(--border)] to-transparent" />
            Cartelle
            <span className="h-px flex-1 bg-gradient-to-l from-[var(--border)] to-transparent" />
          </h3>
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6"
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
              />
            ))}
          </motion.div>
        </div>
      )}

      {/* Files Section */}
      {documents.length > 0 && (
        <div>
          <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-[var(--foreground-muted)] uppercase tracking-wider">
            <span className="h-px flex-1 bg-gradient-to-r from-[var(--border)] to-transparent" />
            Documenti
            <span className="h-px flex-1 bg-gradient-to-l from-[var(--border)] to-transparent" />
          </h3>
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6"
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
              />
            ))}
          </motion.div>
        </div>
      )}

      {/* Empty State */}
      {files.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--foreground-muted)]">
          <div className="mb-4 rounded-full bg-[var(--background-subtle)] p-6">
            <Users className="h-12 w-12 opacity-50" />
          </div>
          <p className="text-lg font-medium">Questa cartella è vuota</p>
          <p className="text-sm">
            Trascina file qui o usa il pulsante "Nuovo" per creare contenuti
          </p>
        </div>
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
}

function FileCard({
  file,
  index,
  isSelected,
  onClick,
  onDoubleClick,
  onContextMenu,
}: FileCardProps) {
  const deptInfo = file.is_folder ? getDepartmentInfo(file.name) : null;

  return (
    <motion.div
      variants={itemVariants}
      onClick={(e) => onClick(file, index, e)}
      onDoubleClick={() => onDoubleClick(file)}
      onContextMenu={(e) => onContextMenu(file, e)}
      whileHover={{ scale: 1.02, y: -4 }}
      whileTap={{ scale: 0.98 }}
      className={`
        group relative flex cursor-pointer flex-col items-center rounded-2xl border-2 p-5
        transition-all duration-200 ease-out
        ${
          isSelected
            ? 'border-blue-500 bg-blue-500/10 shadow-lg shadow-blue-500/20'
            : 'border-transparent bg-[var(--background-subtle)] hover:border-[var(--border)] hover:bg-[var(--accent)] hover:shadow-xl'
        }
        ${deptInfo ? 'hover:shadow-lg' : ''}
      `}
      style={
        deptInfo
          ? ({
              '--tw-shadow-color': `${deptInfo.primary}20`,
            } as React.CSSProperties)
          : undefined
      }
    >
      {/* Department badge for department folders */}
      {deptInfo && (
        <div
          className="absolute -top-2 left-1/2 -translate-x-1/2 rounded-full px-3 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-md"
          style={{ backgroundColor: deptInfo.primary }}
        >
          {deptInfo.label}
        </div>
      )}

      {/* Quick actions overlay */}
      <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={(e) => {
            e.stopPropagation();
          }}
          className="rounded-full bg-white/80 p-1.5 text-gray-600 shadow-sm backdrop-blur-sm transition-colors hover:bg-white hover:text-amber-500 dark:bg-gray-800/80 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <Star className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onContextMenu(file, e);
          }}
          className="rounded-full bg-white/80 p-1.5 text-gray-600 shadow-sm backdrop-blur-sm transition-colors hover:bg-white dark:bg-gray-800/80 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <MoreVertical className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Icon container with glow effect for departments */}
      <div
        className={`
          relative mb-4 transition-transform duration-300 group-hover:scale-110
          ${deptInfo ? 'drop-shadow-lg' : ''}
        `}
      >
        {/* Glow effect for department folders */}
        {deptInfo && (
          <div
            className="absolute inset-0 blur-xl opacity-30 scale-150"
            style={{ backgroundColor: deptInfo.primary }}
          />
        )}
        <div className="relative">{getFileIcon(file, 'lg')}</div>
      </div>

      {/* File name */}
      <span className="w-full truncate text-center text-sm font-medium text-[var(--foreground)]">
        {file.name}
      </span>

      {/* Meta info */}
      <div className="mt-1 flex items-center gap-2 text-xs text-[var(--foreground-muted)]">
        {file.is_folder ? (
          <span className="flex items-center gap-1">
            <Users className="h-3 w-3" />
            Cartella
          </span>
        ) : (
          <>
            <span>{formatSize(file.size)}</span>
            {file.modified_time && (
              <>
                <span className="text-[var(--border)]">•</span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {formatRelativeTime(file.modified_time)}
                </span>
              </>
            )}
          </>
        )}
      </div>

      {/* Selection indicator */}
      {isSelected && (
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-white shadow-lg"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
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

  if (diffDays === 0) return 'Oggi';
  if (diffDays === 1) return 'Ieri';
  if (diffDays < 7) return `${diffDays}g fa`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}s fa`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}m fa`;
  return `${Math.floor(diffDays / 365)}a fa`;
};
