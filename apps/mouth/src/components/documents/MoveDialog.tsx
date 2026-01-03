'use client';

import { useState, useEffect, useCallback } from 'react';
import { X, Folder, FolderOpen, ChevronRight, Loader2, Home } from 'lucide-react';
import type { FileItem } from '@/lib/api/drive/drive.types';

interface FolderNode {
  id: string;
  name: string;
  children?: FolderNode[];
  isLoading?: boolean;
  isExpanded?: boolean;
}

interface MoveDialogProps {
  isOpen: boolean;
  files: FileItem[];
  currentFolderId: string | null;
  onClose: () => void;
  onMove: (targetFolderId: string) => void;
  onLoadFolder: (folderId: string | null) => Promise<FileItem[]>;
  loading?: boolean;
}

export function MoveDialog({
  isOpen,
  files,
  currentFolderId,
  onClose,
  onMove,
  onLoadFolder,
  loading = false,
}: MoveDialogProps) {
  const [folders, setFolders] = useState<FolderNode[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [isLoadingRoot, setIsLoadingRoot] = useState(false);

  // File IDs being moved (to disable as destinations)
  const movingFileIds = new Set(files.map((f) => f.id));

  // Load root folders on open
  useEffect(() => {
    if (isOpen) {
      setSelectedFolderId(null);
      loadRootFolders();
    }
  }, [isOpen]);

  const loadRootFolders = async () => {
    setIsLoadingRoot(true);
    try {
      const items = await onLoadFolder(null);
      const folderItems = items
        .filter((f) => f.is_folder)
        .map((f) => ({
          id: f.id,
          name: f.name,
          isExpanded: false,
        }));
      setFolders(folderItems);
    } catch (error) {
      console.error('Failed to load folders:', error);
    } finally {
      setIsLoadingRoot(false);
    }
  };

  const loadChildren = async (folderId: string) => {
    // Update loading state
    setFolders((prev) =>
      updateNodeInTree(prev, folderId, (node) => ({
        ...node,
        isLoading: true,
        isExpanded: true,
      }))
    );

    try {
      const items = await onLoadFolder(folderId);
      const children = items
        .filter((f) => f.is_folder)
        .map((f) => ({
          id: f.id,
          name: f.name,
          isExpanded: false,
        }));

      setFolders((prev) =>
        updateNodeInTree(prev, folderId, (node) => ({
          ...node,
          children,
          isLoading: false,
        }))
      );
    } catch (error) {
      console.error('Failed to load children:', error);
      setFolders((prev) =>
        updateNodeInTree(prev, folderId, (node) => ({
          ...node,
          isLoading: false,
        }))
      );
    }
  };

  const updateNodeInTree = (
    nodes: FolderNode[],
    targetId: string,
    updater: (node: FolderNode) => FolderNode
  ): FolderNode[] => {
    return nodes.map((node) => {
      if (node.id === targetId) {
        return updater(node);
      }
      if (node.children) {
        return {
          ...node,
          children: updateNodeInTree(node.children, targetId, updater),
        };
      }
      return node;
    });
  };

  const toggleFolder = (folder: FolderNode) => {
    if (folder.isExpanded) {
      // Collapse
      setFolders((prev) =>
        updateNodeInTree(prev, folder.id, (node) => ({
          ...node,
          isExpanded: false,
        }))
      );
    } else {
      // Expand and load if needed
      if (!folder.children) {
        loadChildren(folder.id);
      } else {
        setFolders((prev) =>
          updateNodeInTree(prev, folder.id, (node) => ({
            ...node,
            isExpanded: true,
          }))
        );
      }
    }
  };

  const handleMove = () => {
    if (selectedFolderId === null && currentFolderId === null) {
      // Can't move to root if already in root
      return;
    }
    if (selectedFolderId === currentFolderId) {
      // Can't move to same folder
      return;
    }
    onMove(selectedFolderId || 'root');
  };

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const renderFolderTree = (nodes: FolderNode[], depth = 0): React.ReactNode => {
    return nodes.map((folder) => {
      const isDisabled = movingFileIds.has(folder.id) || folder.id === currentFolderId;
      const isSelected = folder.id === selectedFolderId;

      return (
        <div key={folder.id}>
          <div
            className={`flex items-center gap-1 rounded-lg px-2 py-1.5 ${
              isDisabled
                ? 'cursor-not-allowed opacity-50'
                : isSelected
                  ? 'bg-emerald-100 dark:bg-emerald-900/30'
                  : 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            style={{ paddingLeft: `${depth * 16 + 8}px` }}
            onClick={() => {
              if (isDisabled) return;
              setSelectedFolderId(folder.id);
            }}
          >
            {/* Expand/collapse button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleFolder(folder);
              }}
              className="rounded p-0.5 hover:bg-gray-200 dark:hover:bg-gray-600"
              disabled={isDisabled}
            >
              {folder.isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin text-gray-400" />
              ) : (
                <ChevronRight
                  className={`h-4 w-4 text-gray-400 transition-transform ${
                    folder.isExpanded ? 'rotate-90' : ''
                  }`}
                />
              )}
            </button>

            {/* Folder icon */}
            {folder.isExpanded ? (
              <FolderOpen className="h-5 w-5 text-amber-500" />
            ) : (
              <Folder className="h-5 w-5 text-amber-500" />
            )}

            {/* Folder name */}
            <span
              className={`ml-1 truncate text-sm ${
                isSelected
                  ? 'font-medium text-emerald-700 dark:text-emerald-300'
                  : 'text-gray-700 dark:text-gray-200'
              }`}
            >
              {folder.name}
            </span>
          </div>

          {/* Children */}
          {folder.isExpanded && folder.children && (
            <div>{renderFolderTree(folder.children, depth + 1)}</div>
          )}
        </div>
      );
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 flex w-full max-w-md flex-col rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-800">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            Sposta {files.length > 1 ? `${files.length} elementi` : files[0]?.name}
          </h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Folder tree */}
        <div className="max-h-80 min-h-[200px] overflow-y-auto px-4 py-2">
          {/* Root option */}
          <div
            className={`flex items-center gap-2 rounded-lg px-2 py-1.5 ${
              currentFolderId === null
                ? 'cursor-not-allowed opacity-50'
                : selectedFolderId === null
                  ? 'bg-emerald-100 dark:bg-emerald-900/30'
                  : 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700'
            }`}
            onClick={() => {
              if (currentFolderId !== null) {
                setSelectedFolderId(null);
              }
            }}
          >
            <Home className="h-5 w-5 text-gray-500" />
            <span
              className={`text-sm ${
                selectedFolderId === null
                  ? 'font-medium text-emerald-700 dark:text-emerald-300'
                  : 'text-gray-700 dark:text-gray-200'
              }`}
            >
              Root (Team Drive)
            </span>
          </div>

          {/* Loading state */}
          {isLoadingRoot ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : (
            renderFolderTree(folders)
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 border-t border-gray-200 px-6 py-4 dark:border-gray-700">
          <button
            onClick={onClose}
            disabled={loading}
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:text-gray-200 dark:hover:bg-gray-700"
          >
            Annulla
          </button>
          <button
            onClick={handleMove}
            disabled={loading || (selectedFolderId === currentFolderId)}
            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 dark:bg-emerald-500 dark:hover:bg-emerald-600"
          >
            {loading && (
              <Loader2 className="h-4 w-4 animate-spin" />
            )}
            Sposta qui
          </button>
        </div>
      </div>
    </div>
  );
}
