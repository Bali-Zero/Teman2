"use client";

import { useEffect, useCallback } from "react";
import type { FileItem } from "@/lib/api/drive/drive.types";
import { driveLogger } from "@/lib/logging/drive-logger";

interface UseKeyboardNavigationOptions {
  files: FileItem[];
  selectedFiles: Set<string>;
  onSelect: (files: Set<string>) => void;
  onOpen: (file: FileItem) => void;
  onDelete?: (files: FileItem[]) => void;
  enabled?: boolean;
}

export function useKeyboardNavigation({
  files,
  selectedFiles,
  onSelect,
  onOpen,
  onDelete,
  enabled = true,
}: UseKeyboardNavigationOptions) {
  // Safety: ensure files is always an array
  const safeFiles = Array.isArray(files) ? files : [];

  const getSelectedIndex = useCallback(() => {
    if (selectedFiles.size === 0) return -1;
    const firstSelectedId = Array.from(selectedFiles)[0];
    return safeFiles.findIndex((f) => f.id === firstSelectedId);
  }, [safeFiles, selectedFiles]);

  const getLastSelectedIndex = useCallback(() => {
    if (selectedFiles.size === 0) return -1;
    const selectedIds = Array.from(selectedFiles);
    const lastSelectedId = selectedIds[selectedIds.length - 1];
    return safeFiles.findIndex((f) => f.id === lastSelectedId);
  }, [safeFiles, selectedFiles]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled || safeFiles.length === 0) return;

      // Don't intercept if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        (e.target as HTMLElement)?.isContentEditable
      ) {
        return;
      }

      const currentIndex = getLastSelectedIndex();

      switch (e.key) {
        case "ArrowUp":
        case "ArrowLeft": {
          e.preventDefault();
          if (safeFiles.length === 0) return;

          let newIndex = currentIndex - 1;
          if (newIndex < 0) newIndex = 0;

          driveLogger.logKeyboardNavigation("up", newIndex);

          if (e.shiftKey && currentIndex >= 0) {
            // Extend selection upward
            const start = Math.min(newIndex, getSelectedIndex());
            const end = Math.max(newIndex, currentIndex);
            const newSelection = new Set<string>();
            for (let i = start; i <= end; i++) {
              newSelection.add(safeFiles[i].id);
            }
            driveLogger.logKeyboardShortcut(e.key, "range_select_up", {
              shift: true,
            });
            onSelect(newSelection);
          } else {
            // Single selection
            onSelect(new Set([safeFiles[newIndex].id]));
          }
          break;
        }

        case "ArrowDown":
        case "ArrowRight": {
          e.preventDefault();
          if (safeFiles.length === 0) return;

          let newIndex = currentIndex + 1;
          if (newIndex >= safeFiles.length) newIndex = safeFiles.length - 1;
          if (currentIndex === -1) newIndex = 0;

          driveLogger.logKeyboardNavigation("down", newIndex);

          if (e.shiftKey && currentIndex >= 0) {
            // Extend selection downward
            const start = Math.min(getSelectedIndex(), newIndex);
            const end = Math.max(currentIndex, newIndex);
            const newSelection = new Set<string>();
            for (let i = start; i <= end; i++) {
              newSelection.add(safeFiles[i].id);
            }
            driveLogger.logKeyboardShortcut(e.key, "range_select_down", {
              shift: true,
            });
            onSelect(newSelection);
          } else {
            // Single selection
            onSelect(new Set([safeFiles[newIndex].id]));
          }
          break;
        }

        case "Enter": {
          e.preventDefault();
          driveLogger.logKeyboardShortcut("Enter", "open", {});
          if (selectedFiles.size === 1) {
            const selectedFile = safeFiles.find((f) => selectedFiles.has(f.id));
            if (selectedFile) {
              onOpen(selectedFile);
            }
          }
          break;
        }

        case " ": {
          // Space: Toggle selection on current item
          e.preventDefault();
          driveLogger.logKeyboardShortcut("Space", "toggle_selection", {});
          if (currentIndex >= 0 && currentIndex < safeFiles.length) {
            const file = safeFiles[currentIndex];
            const newSelection = new Set(selectedFiles);
            if (newSelection.has(file.id)) {
              newSelection.delete(file.id);
            } else {
              newSelection.add(file.id);
            }
            onSelect(newSelection);
          }
          break;
        }

        case "a":
        case "A": {
          // Cmd/Ctrl+A: Select all
          if (e.metaKey || e.ctrlKey) {
            e.preventDefault();
            driveLogger.logKeyboardShortcut("Cmd+A", "select_all", {
              meta: e.metaKey,
              ctrl: e.ctrlKey,
            });
            const allIds = new Set(safeFiles.map((f) => f.id));
            onSelect(allIds);
          }
          break;
        }

        case "Escape": {
          // Clear selection
          e.preventDefault();
          driveLogger.logKeyboardShortcut("Escape", "clear_selection", {});
          onSelect(new Set());
          break;
        }

        case "Delete":
        case "Backspace": {
          // Delete selected files
          if (onDelete && selectedFiles.size > 0) {
            e.preventDefault();
            driveLogger.logKeyboardShortcut(e.key, "delete", {});
            const filesToDelete = safeFiles.filter((f) =>
              selectedFiles.has(f.id),
            );
            onDelete(filesToDelete);
          }
          break;
        }

        case "Home": {
          // Jump to first item
          e.preventDefault();
          driveLogger.logKeyboardShortcut("Home", "jump_to_first", {});
          if (safeFiles.length > 0) {
            onSelect(new Set([safeFiles[0].id]));
          }
          break;
        }

        case "End": {
          // Jump to last item
          e.preventDefault();
          driveLogger.logKeyboardShortcut("End", "jump_to_last", {});
          if (safeFiles.length > 0) {
            onSelect(new Set([safeFiles[safeFiles.length - 1].id]));
          }
          break;
        }
      }
    },
    [
      enabled,
      safeFiles,
      selectedFiles,
      getSelectedIndex,
      getLastSelectedIndex,
      onSelect,
      onOpen,
      onDelete,
    ],
  );

  useEffect(() => {
    if (!enabled) return;

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, handleKeyDown]);
}
