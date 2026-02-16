"use client";

/**
 * Documents Page - Ultra Optimized
 *
 * Versione perfezionata con React Query, virtualizzazione e performance ottimali
 */

import React, { useState, useCallback, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2, CloudOff, Cloud, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

// Hooks ottimizzati
import {
  useDriveStatus,
  useDriveFilesInfinite,
  usePrefetchFolder,
  useDriveUpload,
  useDriveMutationsOptimized,
  useFileSelection,
  useFileKeyboardNavigation,
} from "@/hooks";

// Componenti
import {
  DocumentsErrorBoundary,
  DocumentsInlineError,
  logDocumentsError,
} from "./components/DocumentsErrorBoundary";
import { DriveToolbarOptimized } from "./components/DriveToolbarOptimized";
import { DriveBreadcrumb } from "./components/DriveBreadcrumb";
import { FileGridVirtualized } from "./components/FileGridVirtualized";
import { FileList } from "./components/FileList";
import { FileGridSkeleton } from "./components/FileGridSkeleton";
import { FileListSkeleton } from "./components/FileListSkeleton";
import { DepartmentHome } from "./components/DepartmentHome";
import { DriveSidebar } from "./components/DriveSidebar";
import { DriveInfoPanel } from "./components/DriveInfoPanel";

import {
  FileModal,
  CreateMenu,
  ContextMenu,
  MoveDialog,
  DropZone,
  UploadDialog,
  FileViewer,
} from "@/components/documents";

import type { FileItem } from "@/lib/api/drive/drive.types";

export default function DocumentsPageOptimized() {
  const router = useRouter();

  // State
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [sidebarView, setSidebarView] = useState<
    "my-drive" | "recent" | "starred" | "trash"
  >("my-drive");
  const [showInfoPanel, setShowInfoPanel] = useState(false);

  // Modal states
  const [modalMode, setModalMode] = useState<"folder" | "rename" | null>(null);
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null);
  const [createMenuPos, setCreateMenuPos] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [showMoveDialog, setShowMoveDialog] = useState(false);
  const [filesToMove, setFilesToMove] = useState<FileItem[]>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    file: FileItem;
  } | null>(null);

  // Data fetching
  const { data: driveStatus, isLoading: statusLoading } = useDriveStatus();

  const {
    data: filesData,
    isLoading: filesLoading,
    error: filesError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
  } = useDriveFilesInfinite(currentFolderId, searchQuery);

  const files = useMemo(() => {
    return filesData?.pages.flatMap((page) => page.files) || [];
  }, [filesData]);

  const breadcrumb = useMemo(() => {
    return (
      filesData?.pages[0]?.breadcrumb || [{ id: "root", name: "My Drive" }]
    );
  }, [filesData]);

  const isConnected = driveStatus?.connected ?? false;
  const isConfigured = driveStatus?.configured ?? false;
  const isAtRoot = currentFolderId === null && searchQuery === "";

  // File selection
  const {
    selectedIds,
    selectedFiles,
    lastSelectedIndex,
    handleSelect,
    handleDeselectAll,
    selectSingle,
  } = useFileSelection({ files });

  // Upload
  const { uploads, uploadMultiple, clearCompleted } = useDriveUpload();

  // Mutations
  const { createFolder, renameFile, deleteFile, moveFiles } =
    useDriveMutationsOptimized();

  // Prefetching
  const { prefetchFolder } = usePrefetchFolder();

  // Handlers
  const handleFileOpen = useCallback(
    (file: FileItem) => {
      if (file.is_folder) {
        setCurrentFolderId(file.id);
        setSearchQuery("");
        handleDeselectAll();
      } else {
        setPreviewFile(file);
      }
    },
    [handleDeselectAll],
  );

  const handleFileClick = useCallback(
    (file: FileItem, index: number, e: React.MouseEvent) => {
      handleSelect(file, index, e);
    },
    [handleSelect],
  );

  const handleFileDoubleClick = useCallback(
    (file: FileItem) => {
      handleFileOpen(file);
    },
    [handleFileOpen],
  );

  const handleContextMenu = useCallback(
    (file: FileItem, e: React.MouseEvent) => {
      e.preventDefault();
      if (!selectedIds.has(file.id)) {
        selectSingle(file);
      }
      setContextMenu({ x: e.clientX, y: e.clientY, file });
    },
    [selectedIds, selectSingle],
  );

  const handleNavigate = useCallback(
    (index: number) => {
      if (index === -1 || index === 0) {
        setCurrentFolderId(null);
      } else if (breadcrumb[index]) {
        setCurrentFolderId(breadcrumb[index].id);
      }
      setSearchQuery("");
      handleDeselectAll();
    },
    [breadcrumb, handleDeselectAll],
  );

  const handleUpload = useCallback(
    async (filesToUpload: File[]) => {
      setShowUploadDialog(false);
      await uploadMultiple(filesToUpload, currentFolderId, { parallel: 3 });
    },
    [currentFolderId, uploadMultiple],
  );

  const handleConnect = async () => {
    const { auth_url } = await api.drive.getAuthUrl();
    window.location.href = auth_url;
  };

  // Keyboard navigation
  const { handleKeyDown } = useFileKeyboardNavigation({
    files,
    selectedIds,
    lastSelectedIndex,
    onSelect: handleSelect,
    onOpen: handleFileOpen,
    onDelete: (toDelete) => {
      if (confirm(`Delete ${toDelete.length} item(s)?`)) {
        toDelete.forEach((f) => deleteFile.mutate(f.id));
      }
    },
    onRename: (file) => {
      setRenameTarget(file);
      setModalMode("rename");
    },
    enabled: isConnected && !isAtRoot,
  });

  // Effects
  useEffect(() => {
    const handleClick = () => {
      setContextMenu(null);
      setCreateMenuPos(null);
    };
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown as any);
    return () => window.removeEventListener("keydown", handleKeyDown as any);
  }, [handleKeyDown]);

  // Loading state
  if (statusLoading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        >
          <Loader2 className="h-10 w-10 text-blue-500" />
        </motion.div>
        <p className="text-slate-500">Loading documents...</p>
      </div>
    );
  }

  // Disconnected state
  if (!isConnected) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center space-y-8 bg-white dark:bg-[var(--background)] px-6">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="relative"
        >
          <div className="absolute inset-0 animate-pulse rounded-full bg-[#1a73e8]/20 blur-2xl" />
          <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-[#1a73e8] shadow-xl">
            <CloudOff className="h-12 w-12 text-white" />
          </div>
        </motion.div>
        <h2 className="text-3xl font-bold">Connect Google Drive</h2>
        <p className="max-w-md text-slate-500">
          Access your documents by connecting your Google Drive account.
        </p>
        {isConfigured && (
          <Button
            onClick={handleConnect}
            size="lg"
            className="bg-gradient-to-r from-blue-500 to-indigo-600 px-8"
          >
            <Cloud className="mr-3 h-5 w-5" />
            Connect Google Drive
          </Button>
        )}
      </div>
    );
  }

  // Main interface
  const selectedFile =
    selectedIds.size === 1
      ? files.find((f) => selectedIds.has(f.id)) || null
      : null;

  return (
    <DocumentsErrorBoundary onReset={refetch}>
      <div className="flex h-full bg-gradient-to-br from-slate-50/80 via-white to-blue-50/50 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950/30">
        {/* Sidebar */}
        {!isAtRoot && (
          <DriveSidebar
            activeView={sidebarView}
            onViewChange={setSidebarView}
            onNewClick={(e) => {
              e.stopPropagation();
              setCreateMenuPos({ x: e.clientX, y: e.clientY + 20 });
            }}
            onUploadClick={() => setShowUploadDialog(true)}
          />
        )}

        {/* Main Content */}
        <div className="flex flex-1 flex-col min-w-0">
          {/* Toolbar */}
          {(!isAtRoot || searchQuery) && (
            <>
              <DriveToolbarOptimized
                searchQuery={searchQuery}
                onSearchChange={setSearchQuery}
                viewMode={viewMode}
                onViewModeChange={setViewMode}
                onUploadClick={() => setShowUploadDialog(true)}
                onCreateClick={(e) =>
                  setCreateMenuPos({ x: e.clientX, y: e.clientY + 20 })
                }
                isConnected={isConnected}
                isSyncing={isFetchingNextPage}
                showInfoPanel={showInfoPanel}
                onToggleInfoPanel={() => setShowInfoPanel(!showInfoPanel)}
                hasSelection={selectedIds.size > 0}
                totalFiles={files.length}
                selectedCount={selectedIds.size}
              />
              <div className="border-b border-slate-200/60 bg-white dark:bg-[var(--background)] px-4 py-2">
                <DriveBreadcrumb
                  items={breadcrumb}
                  onNavigate={handleNavigate}
                />
              </div>
            </>
          )}

          {/* File Grid/List */}
          <DropZone
            onFilesDropped={handleUpload}
            disabled={!isConnected || isAtRoot}
          >
            <div
              className="flex-1 overflow-hidden bg-white dark:bg-[var(--background)]"
              onClick={handleDeselectAll}
            >
              {filesError ? (
                <DocumentsInlineError
                  message="Failed to load files. Please try again."
                  onRetry={refetch}
                />
              ) : filesLoading && !files.length ? (
                viewMode === "grid" ? (
                  <FileGridSkeleton />
                ) : (
                  <FileListSkeleton />
                )
              ) : isAtRoot ? (
                <DepartmentHome
                  files={files}
                  onFolderClick={handleFileOpen}
                  storageUsed={0}
                  storageTotal={30 * 1024 * 1024 * 1024 * 1024}
                />
              ) : viewMode === "grid" ? (
                <FileGridVirtualized
                  files={files}
                  selectedFiles={selectedIds}
                  onFileClick={handleFileClick}
                  onFileDoubleClick={handleFileDoubleClick}
                  onContextMenu={handleContextMenu}
                  onLoadMore={fetchNextPage}
                  hasNextPage={hasNextPage}
                  isFetchingNextPage={isFetchingNextPage}
                />
              ) : (
                <FileList
                  files={files}
                  selectedFiles={selectedIds}
                  onFileClick={handleFileClick}
                  onFileDoubleClick={handleFileDoubleClick}
                  onContextMenu={handleContextMenu}
                  hasNextPage={hasNextPage}
                  isFetchingNextPage={isFetchingNextPage}
                  onLoadMore={fetchNextPage}
                />
              )}
            </div>
          </DropZone>
        </div>

        {/* Info Panel */}
        {!isAtRoot && (
          <DriveInfoPanel
            file={selectedFile}
            isOpen={showInfoPanel && selectedFile !== null}
            onClose={() => setShowInfoPanel(false)}
            onPreview={setPreviewFile}
            onDownload={async (file) => {
              try {
                await api.drive.downloadFile(file.id, file.name);
              } catch {
                window.open(api.drive.getDownloadUrl(file.id), "_blank");
              }
            }}
            onDelete={(file) => {
              if (confirm(`Delete ${file.name}?`)) {
                deleteFile.mutate(file.id);
                setShowInfoPanel(false);
              }
            }}
          />
        )}

        {/* Modals */}
        <CreateMenu
          isOpen={!!createMenuPos}
          onClose={() => setCreateMenuPos(null)}
          position={createMenuPos || { x: 0, y: 0 }}
          onSelect={(mode) => setModalMode(mode === "folder" ? "folder" : null)}
        />

        <FileModal
          mode={modalMode as any}
          isOpen={!!modalMode}
          onClose={() => {
            setModalMode(null);
            setRenameTarget(null);
          }}
          initialName={renameTarget?.name || ""}
          loading={createFolder.isPending || renameFile.isPending}
          onSubmit={(name) => {
            if (modalMode === "rename" && renameTarget) {
              renameFile.mutate({ fileId: renameTarget.id, newName: name });
            } else if (modalMode === "folder") {
              createFolder.mutate({ name, parentId: currentFolderId });
            }
            setModalMode(null);
          }}
        />

        {contextMenu && (
          <ContextMenu
            position={{ x: contextMenu.x, y: contextMenu.y }}
            file={contextMenu.file}
            onClose={() => setContextMenu(null)}
            onPreview={setPreviewFile}
            onOpen={handleFileOpen}
            onRename={(file) => {
              setRenameTarget(file);
              setModalMode("rename");
            }}
            onDelete={(file) => deleteFile.mutate(file.id)}
            onMove={(file) => {
              setFilesToMove([file]);
              setShowMoveDialog(true);
            }}
            onCopy={() => {}}
            onDownload={async (file) => {
              try {
                await api.drive.downloadFile(file.id, file.name);
              } catch {
                window.open(api.drive.getDownloadUrl(file.id), "_blank");
              }
            }}
          />
        )}

        {showMoveDialog && (
          <MoveDialog
            isOpen={true}
            onClose={() => setShowMoveDialog(false)}
            onMove={(targetId) => {
              moveFiles.mutate({
                fileIds: filesToMove.map((f) => f.id),
                targetFolderId: targetId,
              });
              setShowMoveDialog(false);
            }}
            files={filesToMove}
            currentFolderId={currentFolderId}
            onLoadFolder={async (parentId) => {
              const results = await api.drive.listFiles({
                folder_id: parentId || undefined,
              });
              return results.files;
            }}
          />
        )}

        <UploadDialog
          isOpen={showUploadDialog}
          onClose={() => setShowUploadDialog(false)}
          onUpload={handleUpload}
          uploading={uploads.some((u) => u.status === "uploading")}
        />

        <FileViewer
          file={previewFile}
          isOpen={!!previewFile}
          onClose={() => setPreviewFile(null)}
          onDownload={async (file) => {
            try {
              await api.drive.downloadFile(file.id, file.name);
            } catch {
              window.open(api.drive.getDownloadUrl(file.id), "_blank");
            }
          }}
        />
      </div>
    </DocumentsErrorBoundary>
  );
}
