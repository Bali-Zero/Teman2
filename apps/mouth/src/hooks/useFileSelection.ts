/**
 * useFileSelection Hook
 *
 * Hook ottimizzato per la gestione selezione file multipla
 * con keyboard navigation e range selection
 */

import { useState, useCallback, useRef } from "react";
import type { FileItem } from "@/lib/api/drive/drive.types";

interface UseFileSelectionOptions {
  files: FileItem[];
  onSelectionChange?: (
    selectedIds: Set<string>,
    selectedFiles: FileItem[],
  ) => void;
}

interface UseFileSelectionReturn {
  selectedIds: Set<string>;
  selectedFiles: FileItem[];
  lastSelectedIndex: number;
  handleSelect: (
    file: FileItem,
    index: number,
    event: React.MouseEvent | React.KeyboardEvent,
  ) => void;
  handleSelectAll: () => void;
  handleDeselectAll: () => void;
  handleRangeSelect: (startIndex: number, endIndex: number) => void;
  isSelected: (fileId: string) => boolean;
  selectSingle: (file: FileItem) => void;
}

export function useFileSelection({
  files,
  onSelectionChange,
}: UseFileSelectionOptions): UseFileSelectionReturn {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number>(-1);
  const lastSelectionTime = useRef<number>(0);

  // Get selected file objects
  const selectedFiles = files.filter((f) => selectedIds.has(f.id));

  // Notify parent of selection change
  const notifyChange = useCallback(
    (newIds: Set<string>) => {
      const newFiles = files.filter((f) => newIds.has(f.id));
      onSelectionChange?.(newIds, newFiles);
    },
    [files, onSelectionChange],
  );

  // Handle selection with all modifier keys
  const handleSelect = useCallback(
    (
      file: FileItem,
      index: number,
      event: React.MouseEvent | React.KeyboardEvent,
    ) => {
      const isCtrl = event.ctrlKey || event.metaKey;
      const isShift = event.shiftKey;
      const isDoubleClick = "detail" in event && event.detail === 2;

      // Prevent double-click from triggering selection change
      if (isDoubleClick) return;

      const now = Date.now();
      const timeSinceLast = now - lastSelectionTime.current;
      lastSelectionTime.current = now;

      setSelectedIds((prev) => {
        const next = new Set(prev);

        if (isShift && lastSelectedIndex !== -1) {
          // Range selection
          const start = Math.min(lastSelectedIndex, index);
          const end = Math.max(lastSelectedIndex, index);

          // If Ctrl+Shift, add to selection; otherwise replace
          if (!isCtrl) {
            next.clear();
          }

          for (let i = start; i <= end; i++) {
            if (files[i]) {
              next.add(files[i].id);
            }
          }
        } else if (isCtrl) {
          // Toggle selection
          if (next.has(file.id)) {
            next.delete(file.id);
          } else {
            next.add(file.id);
          }
        } else {
          // Single selection (clear others unless rapid double-click)
          if (timeSinceLast < 300 && prev.has(file.id) && prev.size === 1) {
            // Possible double-click start, keep selection
          } else {
            next.clear();
            next.add(file.id);
          }
        }

        notifyChange(next);
        return next;
      });

      setLastSelectedIndex(index);
    },
    [files, lastSelectedIndex, notifyChange],
  );

  // Select all files
  const handleSelectAll = useCallback(() => {
    const allIds = new Set(files.map((f) => f.id));
    setSelectedIds(allIds);
    notifyChange(allIds);
  }, [files, notifyChange]);

  // Deselect all
  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set());
    notifyChange(new Set());
    setLastSelectedIndex(-1);
  }, [notifyChange]);

  // Range selection helper
  const handleRangeSelect = useCallback(
    (startIndex: number, endIndex: number) => {
      const next = new Set<string>();
      const start = Math.min(startIndex, endIndex);
      const end = Math.max(startIndex, endIndex);

      for (let i = start; i <= end; i++) {
        if (files[i]) {
          next.add(files[i].id);
        }
      }

      setSelectedIds(next);
      notifyChange(next);
    },
    [files, notifyChange],
  );

  // Check if file is selected
  const isSelected = useCallback(
    (fileId: string) => {
      return selectedIds.has(fileId);
    },
    [selectedIds],
  );

  // Select single file (replaces selection)
  const selectSingle = useCallback(
    (file: FileItem) => {
      const next = new Set([file.id]);
      setSelectedIds(next);
      notifyChange(next);

      const index = files.findIndex((f) => f.id === file.id);
      setLastSelectedIndex(index);
    },
    [files, notifyChange],
  );

  return {
    selectedIds,
    selectedFiles,
    lastSelectedIndex,
    handleSelect,
    handleSelectAll,
    handleDeselectAll,
    handleRangeSelect,
    isSelected,
    selectSingle,
  };
}

// ============================================================================
// KEYBOARD NAVIGATION
// ============================================================================

interface UseKeyboardNavigationOptions {
  files: FileItem[];
  selectedIds: Set<string>;
  lastSelectedIndex: number;
  onSelect: (file: FileItem, index: number, event: React.KeyboardEvent) => void;
  onOpen: (file: FileItem) => void;
  onDelete?: (files: FileItem[]) => void;
  onRename?: (file: FileItem) => void;
  enabled?: boolean;
}

export function useFileKeyboardNavigation({
  files,
  selectedIds,
  lastSelectedIndex,
  onSelect,
  onOpen,
  onDelete,
  onRename,
  enabled = true,
}: UseKeyboardNavigationOptions) {
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (!enabled) return;

      const currentIndex = lastSelectedIndex !== -1 ? lastSelectedIndex : 0;
      let newIndex = currentIndex;

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          newIndex = Math.min(currentIndex + 1, files.length - 1);
          break;

        case "ArrowUp":
          event.preventDefault();
          newIndex = Math.max(currentIndex - 1, 0);
          break;

        case "Home":
          event.preventDefault();
          newIndex = 0;
          break;

        case "End":
          event.preventDefault();
          newIndex = files.length - 1;
          break;

        case "Enter":
          event.preventDefault();
          if (files[currentIndex]) {
            onOpen(files[currentIndex]);
          }
          return;

        case " ":
          event.preventDefault();
          if (files[currentIndex]) {
            onSelect(files[currentIndex], currentIndex, {
              ...event,
              ctrlKey: true,
            } as React.KeyboardEvent);
          }
          return;

        case "Delete":
        case "Backspace":
          if (onDelete && selectedIds.size > 0) {
            event.preventDefault();
            const toDelete = files.filter((f) => selectedIds.has(f.id));
            onDelete(toDelete);
          }
          return;

        case "F2":
          if (onRename && selectedIds.size === 1) {
            event.preventDefault();
            const toRename = files.find((f) => selectedIds.has(f.id));
            if (toRename) onRename(toRename);
          }
          return;

        case "a":
          if (event.ctrlKey || event.metaKey) {
            event.preventDefault();
            // Select all handled by parent
          }
          return;

        case "Escape":
          event.preventDefault();
          // Deselect all handled by parent
          return;

        default:
          return;
      }

      // Navigate and select
      if (newIndex !== currentIndex && files[newIndex]) {
        if (event.shiftKey) {
          // Range selection
          const start = Math.min(
            lastSelectedIndex !== -1 ? lastSelectedIndex : 0,
            newIndex,
          );
          const end = Math.max(
            lastSelectedIndex !== -1 ? lastSelectedIndex : 0,
            newIndex,
          );
          for (let i = start; i <= end; i++) {
            onSelect(files[i], i, event);
          }
        } else {
          onSelect(files[newIndex], newIndex, event);
        }
      }
    },
    [
      enabled,
      files,
      lastSelectedIndex,
      onDelete,
      onOpen,
      onRename,
      onSelect,
      selectedIds.size,
    ],
  );

  return { handleKeyDown };
}
