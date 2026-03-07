"use client";

/**
 * FileGridVirtualized Component
 *
 * Griglia file con virtualizzazione per performance eccellenti
 * anche con migliaia di file
 */

import React, { useRef, useMemo } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { motion } from "framer-motion";
import type { FileItem } from "@/lib/api/drive/drive.types";
import { getFileIcon, getDepartmentInfo } from "./file-icon";
import { MoreVertical, Users } from "lucide-react";
import { usePrefetchFolder } from "@/hooks/useDrive";
import { cn } from "@/lib/utils";

interface FileGridVirtualizedProps {
  files: FileItem[];
  selectedFiles: Set<string>;
  onFileClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onFileDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
  onLoadMore?: () => void;
  hasNextPage?: boolean;
  isFetchingNextPage?: boolean;
}

// Card height including gap
const ROW_HEIGHT = 180;
const OVERSCAN = 2;

export function FileGridVirtualized({
  files,
  selectedFiles,
  onFileClick,
  onFileDoubleClick,
  onContextMenu,
  onLoadMore,
  hasNextPage,
  isFetchingNextPage,
}: FileGridVirtualizedProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const { prefetchFolder } = usePrefetchFolder();

  // Separate folders and files
  const { folders, documents } = useMemo(
    () => ({
      folders: files.filter((f) => f.is_folder),
      documents: files.filter((f) => !f.is_folder),
    }),
    [files],
  );

  // Combine with headers: [foldersHeader, ...folders, filesHeader, ...files]
  const virtualItems = useMemo(() => {
    const items: Array<{
      type: "header" | "file";
      file?: FileItem;
      title?: string;
    }> = [];

    if (folders.length > 0) {
      items.push({ type: "header", title: "Cartelle" });
      folders.forEach((f) => items.push({ type: "file", file: f }));
    }

    if (documents.length > 0) {
      items.push({ type: "header", title: "File" });
      documents.forEach((f) => items.push({ type: "file", file: f }));
    }

    return items;
  }, [folders, documents]);

  // Grid columns responsive
  const [columns, setColumns] = React.useState(4);

  React.useEffect(() => {
    const updateColumns = () => {
      const width = window.innerWidth;
      if (width >= 1536) setColumns(7);
      else if (width >= 1280) setColumns(6);
      else if (width >= 1024) setColumns(5);
      else if (width >= 768) setColumns(4);
      else if (width >= 640) setColumns(3);
      else setColumns(2);
    };

    updateColumns();
    window.addEventListener("resize", updateColumns);
    return () => window.removeEventListener("resize", updateColumns);
  }, []);

  // Calculate rows for virtualization
  const rowCount = Math.ceil(virtualItems.length / columns);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: OVERSCAN,
  });

  // Load more on scroll
  const lastItemIndex = virtualizer.getVirtualItems().pop()?.index;
  React.useEffect(() => {
    if (
      lastItemIndex !== undefined &&
      lastItemIndex >= rowCount - 5 &&
      hasNextPage &&
      !isFetchingNextPage
    ) {
      onLoadMore?.();
    }
  }, [lastItemIndex, rowCount, hasNextPage, isFetchingNextPage, onLoadMore]);

  const virtualRows = virtualizer.getVirtualItems();

  if (files.length === 0) {
    return (
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
    );
  }

  return (
    <div
      ref={parentRef}
      className="h-full overflow-auto"
      style={{ contain: "strict" }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        <div className="p-5">
          {virtualRows.map((virtualRow) => {
            const startIndex = virtualRow.index * columns;
            const rowItems = virtualItems.slice(
              startIndex,
              startIndex + columns,
            );

            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 2xl:grid-cols-7 gap-3"
              >
                {rowItems.map((item, idx) => {
                  if (item.type === "header") {
                    return (
                      <div
                        key={item.title}
                        className="col-span-full mb-2 mt-4 first:mt-0"
                      >
                        <h3 className="text-[11px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                          {item.title}
                        </h3>
                      </div>
                    );
                  }

                  const file = item.file!;
                  const globalIndex = startIndex + idx;
                  const isSelected = selectedFiles.has(file.id);

                  return (
                    <VirtualFileCard
                      key={file.id}
                      file={file}
                      index={globalIndex}
                      isSelected={isSelected}
                      onClick={onFileClick}
                      onDoubleClick={onFileDoubleClick}
                      onContextMenu={onContextMenu}
                      onPrefetch={prefetchFolder}
                    />
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>

      {/* Loading indicator */}
      {isFetchingNextPage && (
        <div className="flex items-center justify-center py-8">
          <div className="flex items-center gap-3 text-[var(--foreground-muted)]">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
            <span className="text-sm">Loading more files...</span>
          </div>
        </div>
      )}
    </div>
  );
}

interface VirtualFileCardProps {
  file: FileItem;
  index: number;
  isSelected: boolean;
  onClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
  onPrefetch?: (folderId: string) => void;
}

function VirtualFileCard({
  file,
  index,
  isSelected,
  onClick,
  onDoubleClick,
  onContextMenu,
  onPrefetch,
}: VirtualFileCardProps) {
  const deptInfo = file.is_folder ? getDepartmentInfo(file.name) : null;

  const handleMouseEnter = () => {
    if (file.is_folder && onPrefetch) {
      onPrefetch(file.id);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: (index % 10) * 0.02 }}
      onClick={(e) => onClick(file, index, e)}
      onDoubleClick={() => onDoubleClick(file)}
      onContextMenu={(e) => onContextMenu(file, e)}
      onMouseEnter={handleMouseEnter}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
      className={cn(
        "group relative flex cursor-pointer flex-col items-center rounded-xl p-4",
        "transition-all duration-200 ease-out",
        isSelected
          ? "bg-blue-50/80 dark:bg-blue-950/40 ring-1 ring-blue-400/50 dark:ring-blue-500/40"
          : "bg-white/60 dark:bg-slate-800/40 hover:bg-slate-50 dark:hover:bg-slate-800/60 border border-slate-200/40 dark:border-slate-700/30",
      )}
    >
      {/* Quick actions */}
      <div className="absolute right-2 top-2 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onContextMenu(file, e);
          }}
          className="rounded-lg bg-white/80 dark:bg-slate-700/80 p-1.5 text-slate-400 backdrop-blur-sm transition-colors hover:bg-white hover:text-slate-600"
        >
          <MoreVertical className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Icon */}
      <div className="relative mb-3 transition-transform duration-200 group-hover:scale-[1.02]">
        {getFileIcon(file, "lg")}
      </div>

      {/* Name */}
      <span className="w-full truncate text-center text-[13px] font-medium text-slate-700 dark:text-slate-200">
        {file.name}
      </span>

      {/* Meta */}
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

      {/* Dept indicator */}
      {file.is_folder && deptInfo && (
        <span
          className="mt-1.5 text-[10px] font-medium uppercase tracking-wide"
          style={{ color: deptInfo.primary }}
        >
          {deptInfo.label}
        </span>
      )}

      {/* Selection checkmark */}
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
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M5 13l4 4L19 7"
            />
          </svg>
        </motion.div>
      )}
    </motion.div>
  );
}

const formatSize = (bytes: number | undefined) => {
  if (!bytes) return "--";
  const units = ["B", "KB", "MB", "GB"];
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

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
};
