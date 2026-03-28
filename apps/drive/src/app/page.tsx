'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useDriveFiles, useDriveMutations, useDriveStatus } from '@/hooks/useDrive';
import { useKeyboardNavigation } from '@/hooks/useKeyboardNavigation';
import { DriveToolbar } from '@/components/drive/DriveToolbar';
import { DriveBreadcrumb } from '@/components/drive/DriveBreadcrumb';
import { FileGrid } from '@/components/drive/FileGrid';
import { FileList } from '@/components/drive/FileList';
import { FileGridSkeleton } from '@/components/drive/FileGridSkeleton';
import { FileListSkeleton } from '@/components/drive/FileListSkeleton';
import { DepartmentHome } from '@/components/drive/DepartmentHome';
import { DriveSidebar } from '@/components/drive/DriveSidebar';
import { DriveInfoPanel } from '@/components/drive/DriveInfoPanel';
import {
  FileModal,
  CreateMenu,
  ContextMenu,
  MoveDialog,
  DropZone,
  UploadProgress,
  UploadDialog,
  FileViewer,
} from '@/components/documents';
import { Loader2, CloudOff, Cloud, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { driveLogger } from '@/lib/logging/drive-logger';
import { motion } from 'framer-motion';
import type { FileItem, BreadcrumbItem, DocType } from '@/lib/api/drive/drive.types';

export default function DrivePage() {
  const BZ_ROOT_FOLDER_ID = '1hkOeV03YM5-sHbQhswYz809jsrnwC0At';

  // Navigation State
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // React Query Hooks
  const queryClient = useQueryClient();
  const { data: driveStatus, isLoading: statusLoading } = useDriveStatus();
  const {
    data,
    isLoading: filesLoading,
    error,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = useDriveFiles(currentFolderId, searchQuery);

  const { createFolder, createDoc, renameFile, deleteFile, moveFiles } = useDriveMutations();

  // Derived Data
  const files = data?.files || [];
  const breadcrumb = data?.breadcrumb || [];
  const isConnected = driveStatus?.connected ?? false;
  const isConfigured = driveStatus?.configured ?? false;
  const isAtRoot = currentFolderId === null && searchQuery === '';

  // Auto-navigate to BZ root folder when connected (Service Account — no OAuth needed)
  useEffect(() => {
    if (!statusLoading && isConnected && currentFolderId === null) {
      const rootId = driveStatus?.root_folder_id ?? BZ_ROOT_FOLDER_ID;
      setCurrentFolderId(rootId);
    }
  }, [statusLoading, isConnected, driveStatus?.root_folder_id]);

  // Selection State
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number>(-1);
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    file: FileItem;
  } | null>(null);

  // Modal State
  const [modalMode, setModalMode] = useState<
    'folder' | 'document' | 'spreadsheet' | 'presentation' | 'rename' | null
  >(null);
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null);
  const [createMenuPos, setCreateMenuPos] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [showMoveDialog, setShowMoveDialog] = useState(false);
  const [filesToMove, setFilesToMove] = useState<FileItem[]>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);

  // UI State
  const [showInfoPanel, setShowInfoPanel] = useState(false);
  const [sidebarView, setSidebarView] = useState<'my-drive' | 'recent' | 'starred' | 'trash'>(
    'my-drive'
  );

  // Upload State
  const [uploads, setUploads] = useState<
    Array<{
      id: string;
      name: string;
      progress: number;
      status: 'uploading' | 'completed' | 'error';
      error?: string;
      abortController?: AbortController;
    }>
  >([]);

  // Handlers
  const handleNavigate = (index: number) => {
    const targetId = index === -1 ? null : breadcrumb[index].id;
    const targetName = index === -1 ? 'Root' : breadcrumb[index].name;
    driveLogger.logBreadcrumbClick(targetId, targetName, index);

    if (index === -1) {
      setCurrentFolderId(null);
    } else {
      setCurrentFolderId(breadcrumb[index].id);
    }
    setSearchQuery('');
  };

  // Single click = select, Double click = open (Google Drive behavior)
  const handleFileClick = (file: FileItem, index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (e.metaKey || e.ctrlKey) {
      const next = new Set(selectedFiles);
      const wasSelected = next.has(file.id);
      if (wasSelected) {
        next.delete(file.id);
        driveLogger.logFileDeselected(file.id, file.name);
      } else {
        next.add(file.id);
        driveLogger.logFileSelected(file.id, file.name, true);
      }
      setSelectedFiles(next);
      setLastSelectedIndex(index);
    } else if (e.shiftKey && lastSelectedIndex !== -1) {
      const start = Math.min(lastSelectedIndex, index);
      const end = Math.max(lastSelectedIndex, index);
      const next = new Set<string>();
      for (let i = start; i <= end; i++) next.add(files[i].id);
      setSelectedFiles(next);
      driveLogger.logSelectionChange(next.size, files.length);
    } else {
      setSelectedFiles(new Set([file.id]));
      setLastSelectedIndex(index);
      driveLogger.logFileSelected(file.id, file.name, false);
    }
  };

  const handleFileDoubleClick = (file: FileItem) => {
    driveLogger.logFileOpened(file.id, file.name, file.is_folder);

    if (file.is_folder) {
      setCurrentFolderId(file.id);
      setSearchQuery('');
      setSelectedFiles(new Set());
    } else {
      setPreviewFile(file);
      driveLogger.logFilePreviewed(file.id, file.name, file.mime_type);
    }
  };

  const handleFolderClick = (folder: FileItem) => {
    driveLogger.logFolderNavigation(folder.id, folder.name, false);
    setCurrentFolderId(folder.id);
    setSearchQuery('');
    setSelectedFiles(new Set());
  };

  const handleContextMenu = (file: FileItem, e: React.MouseEvent) => {
    e.preventDefault();
    if (!selectedFiles.has(file.id)) {
      setSelectedFiles(new Set([file.id]));
    }
    setContextMenu({ x: e.clientX, y: e.clientY, file });
  };

  const handleConnect = async () => {
    const { auth_url } = await api.drive.getAuthUrl();
    window.location.href = auth_url;
  };

  const handleUpload = async (filesToUpload: File[]) => {
    setShowUploadDialog(false);

    const uploadPromises = filesToUpload.map(async (file) => {
      const uploadId = `${Date.now()}-${Math.random()}-${file.name}`;
      const abortController = new AbortController();

      setUploads((prev) => [
        ...prev,
        {
          id: uploadId,
          name: file.name,
          progress: 0,
          status: 'uploading',
          abortController,
        },
      ]);

      try {
        await api.drive.uploadFile(file, currentFolderId || 'root', (progress) => {
          setUploads((prev) =>
            prev.map((u) => (u.id === uploadId ? { ...u, progress: progress.percentage } : u))
          );
        });

        setUploads((prev) =>
          prev.map((u) => (u.id === uploadId ? { ...u, status: 'completed', progress: 100 } : u))
        );

        setTimeout(() => {
          setUploads((prev) => prev.filter((u) => u.id !== uploadId));
        }, 3000);

        return { success: true, uploadId };
      } catch (error) {
        setUploads((prev) =>
          prev.map((u) =>
            u.id === uploadId
              ? {
                  ...u,
                  status: 'error',
                  error: error instanceof Error ? error.message : 'Upload error',
                }
              : u
          )
        );
        return { success: false, uploadId };
      }
    });

    await Promise.allSettled(uploadPromises);
    queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });
  };

  const handleCancelUpload = (uploadId: string) => {
    const upload = uploads.find((u) => u.id === uploadId);
    if (upload?.abortController) {
      upload.abortController.abort();
    }
    setUploads((prev) => prev.filter((u) => u.id !== uploadId));
  };

  const handleDismissUpload = (uploadId: string) => {
    setUploads((prev) => prev.filter((u) => u.id !== uploadId));
  };

  const handleFilesDropped = (droppedFiles: File[]) => {
    handleUpload(droppedFiles);
  };

  useEffect(() => {
    const handleClick = () => {
      setContextMenu(null);
      setCreateMenuPos(null);
    };
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, []);

  useKeyboardNavigation({
    files,
    selectedFiles,
    onSelect: (newSelection) => {
      setSelectedFiles(newSelection);
      driveLogger.logSelectionChange(newSelection.size, files.length);
    },
    onOpen: handleFileDoubleClick,
    onDelete: (filesToDelete) => {
      const names = filesToDelete.map((f) => f.name).join(', ');
      if (confirm(`Delete ${filesToDelete.length > 1 ? 'these files' : ''}: ${names}?`)) {
        driveLogger.logFileDeleted(
          filesToDelete.map((f) => f.id),
          filesToDelete.map((f) => f.name)
        );
        filesToDelete.forEach((f) => deleteFile.mutate(f.id));
        setSelectedFiles(new Set());
      }
    },
    enabled: isConnected && !isAtRoot,
  });

  if (statusLoading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[#141416]">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        >
          <Loader2 className="h-10 w-10 text-[#d4845a]" />
        </motion.div>
        <p className="text-slate-400">Loading Bali Zero Drive...</p>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center space-y-8 bg-[#141416] px-6">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="relative"
        >
          <div
            className="absolute inset-0 animate-pulse rounded-full blur-2xl"
            style={{ background: 'rgba(212,132,90,0.15)' }}
          />
          <div
            className="relative flex h-24 w-24 items-center justify-center rounded-full shadow-xl"
            style={{ background: 'var(--bz-accent)' }}
          >
            <CloudOff className="h-12 w-12 text-white" />
          </div>
        </motion.div>

        <div className="text-center">
          <h2 className="mb-2 text-3xl font-bold text-white">Connetti Google Drive</h2>
          <p className="max-w-md text-[#9aa0a6]">
            Accedi ai tuoi documenti aziendali collegando il tuo account Google Drive. Tutti i file
            saranno organizzati per dipartimento.
          </p>
        </div>

        {isConfigured && (
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            <Button
              onClick={handleConnect}
              size="lg"
              className="px-8 py-6 text-lg text-white shadow-lg transition-all rounded-2xl hover:shadow-xl"
              style={{ background: 'var(--bz-accent)' }}
            >
              <Cloud className="mr-3 h-5 w-5" />
              Connect Google Drive
              <Sparkles className="ml-3 h-5 w-5" />
            </Button>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="mt-8 grid max-w-2xl grid-cols-3 gap-6 text-center"
        >
          {[
            { label: '30TB', desc: 'Available storage' },
            { label: '6', desc: 'Departments' },
            { label: '100%', desc: 'Secure' },
          ].map((stat, i) => (
            <div key={i} className="rounded-lg border border-[#3c3c3c] bg-[#1e1e20] p-4 shadow-sm">
              <div className="text-2xl font-bold" style={{ color: 'var(--bz-accent)' }}>
                {stat.label}
              </div>
              <div className="text-sm text-[#9aa0a6]">{stat.desc}</div>
            </div>
          ))}
        </motion.div>
      </div>
    );
  }

  const selectedFile =
    selectedFiles.size === 1 ? files.find((f) => selectedFiles.has(f.id)) || null : null;

  return (
    <div className="flex h-screen bg-[#141416]">
      {/* Left Sidebar */}
      {!isAtRoot && (
        <DriveSidebar
          activeView={sidebarView}
          onViewChange={(view) => {
            driveLogger.logSidebarNavigation(view);
            setSidebarView(view);
          }}
          onNewClick={(e) => {
            e.stopPropagation();
            driveLogger.logNewButtonClicked();
            setCreateMenuPos({ x: e.clientX, y: e.clientY + 20 });
          }}
          onUploadClick={() => {
            driveLogger.logUploadButtonClicked();
            setShowUploadDialog(true);
          }}
        />
      )}

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col min-w-0">
        {(!isAtRoot || searchQuery) && (
          <>
            <DriveToolbar
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              viewMode={viewMode}
              onViewModeChange={(newMode) => {
                driveLogger.logViewModeChange(viewMode, newMode);
                setViewMode(newMode);
              }}
              onUploadClick={() => {
                driveLogger.logUploadButtonClicked();
                setShowUploadDialog(true);
              }}
              onCreateClick={(e) => {
                e.stopPropagation();
                driveLogger.logNewButtonClicked();
                setCreateMenuPos({ x: e.clientX, y: e.clientY + 20 });
              }}
              isConnected={isConnected}
              showInfoPanel={showInfoPanel}
              onToggleInfoPanel={() => {
                driveLogger.logInfoPanelToggle(!showInfoPanel);
                setShowInfoPanel(!showInfoPanel);
              }}
              hasSelection={selectedFiles.size > 0}
            />

            <div className="border-b border-[#3c3c3c] bg-[#1e1e20] px-4 py-2">
              <DriveBreadcrumb items={breadcrumb} onNavigate={handleNavigate} />
            </div>
          </>
        )}

        <DropZone onFilesDropped={handleFilesDropped} disabled={!isConnected || isAtRoot}>
          <div
            className="flex-1 overflow-auto bg-[#141416]"
            onClick={() => setSelectedFiles(new Set())}
          >
            {filesLoading ? (
              viewMode === 'grid' ? (
                <FileGridSkeleton />
              ) : (
                <FileListSkeleton />
              )
            ) : isAtRoot ? (
              <DepartmentHome
                files={files}
                onFolderClick={handleFolderClick}
                storageUsed={0}
                storageTotal={30 * 1024 * 1024 * 1024 * 1024}
              />
            ) : viewMode === 'grid' ? (
              <FileGrid
                files={files}
                selectedFiles={selectedFiles}
                onFileClick={handleFileClick}
                onFileDoubleClick={handleFileDoubleClick}
                onContextMenu={handleContextMenu}
                hasNextPage={hasNextPage}
                isFetchingNextPage={isFetchingNextPage}
                onLoadMore={() => fetchNextPage()}
              />
            ) : (
              <FileList
                files={files}
                selectedFiles={selectedFiles}
                onFileClick={handleFileClick}
                onFileDoubleClick={handleFileDoubleClick}
                onContextMenu={handleContextMenu}
                hasNextPage={hasNextPage}
                isFetchingNextPage={isFetchingNextPage}
                onLoadMore={() => fetchNextPage()}
              />
            )}
          </div>
        </DropZone>
      </div>

      {/* Right Info Panel */}
      {!isAtRoot && (
        <DriveInfoPanel
          file={selectedFile}
          isOpen={showInfoPanel && selectedFile !== null}
          onClose={() => {
            driveLogger.logInfoPanelToggle(false);
            setShowInfoPanel(false);
          }}
          onPreview={(file) => {
            driveLogger.logFilePreviewed(file.id, file.name, file.mime_type);
            setPreviewFile(file);
          }}
          onDownload={async (file) => {
            driveLogger.logFileDownloaded(file.id, file.name);
            try {
              await api.drive.downloadFile(file.id, file.name);
            } catch (err) {
              driveLogger.logError(
                'Download failed',
                err instanceof Error ? err : new Error(String(err)),
                { fileId: file.id }
              );
              window.open(api.drive.getDownloadUrl(file.id), '_blank');
            }
          }}
          onDelete={(file) => {
            if (confirm(`Delete ${file.name}?`)) {
              driveLogger.logFileDeleted([file.id], [file.name]);
              deleteFile.mutate(file.id);
              setShowInfoPanel(false);
            }
          }}
        />
      )}

      {/* Modals & Menus */}
      <CreateMenu
        isOpen={!!createMenuPos}
        onClose={() => setCreateMenuPos(null)}
        position={createMenuPos || { x: 0, y: 0 }}
        onSelect={(mode) => setModalMode(mode)}
      />

      <FileModal
        mode={modalMode as 'folder' | 'document' | 'spreadsheet' | 'presentation' | 'rename'}
        isOpen={!!modalMode}
        onClose={() => {
          setModalMode(null);
          setRenameTarget(null);
        }}
        initialName={renameTarget?.name || ''}
        loading={createFolder.isPending || createDoc.isPending || renameFile.isPending}
        onSubmit={(name, docType) => {
          if (modalMode === 'rename' && renameTarget) {
            renameFile.mutate(
              { fileId: renameTarget.id, newName: name },
              { onSuccess: () => setModalMode(null) }
            );
          } else if (modalMode === 'folder') {
            createFolder.mutate(
              { name, parentId: currentFolderId },
              { onSuccess: () => setModalMode(null) }
            );
          } else if (docType) {
            createDoc.mutate(
              { name, parentId: currentFolderId, docType },
              { onSuccess: () => setModalMode(null) }
            );
          }
        }}
      />

      {contextMenu && (
        <ContextMenu
          position={{ x: contextMenu.x, y: contextMenu.y }}
          file={contextMenu.file}
          onClose={() => setContextMenu(null)}
          onPreview={(file) => setPreviewFile(file)}
          onOpen={(file) => {
            if (file.is_folder) {
              setCurrentFolderId(file.id);
            } else {
              window.open(file.web_view_link, '_blank');
            }
          }}
          onRename={(file) => {
            setRenameTarget(file);
            setModalMode('rename');
          }}
          onDelete={(file) => {
            if (confirm(`Delete ${file.name}?`)) {
              deleteFile.mutate(file.id);
            }
          }}
          onMove={(file) => {
            setFilesToMove([file]);
            setShowMoveDialog(true);
          }}
          onCopy={(file) => {
            const link = file.web_view_link || `https://drive.google.com/file/d/${file.id}/view`;
            navigator.clipboard.writeText(link);
          }}
          onDownload={async (file) => {
            try {
              await api.drive.downloadFile(file.id, file.name);
            } catch (err) {
              logger.error('Download failed', {
                metadata: { error: String(err) },
              });
              window.open(api.drive.getDownloadUrl(file.id), '_blank');
            }
          }}
        />
      )}

      {showMoveDialog && (
        <MoveDialog
          isOpen={true}
          onClose={() => setShowMoveDialog(false)}
          onMove={(targetId) => {
            const ids = filesToMove.map((f) => f.id);
            moveFiles.mutate({ fileIds: ids, targetFolderId: targetId });
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
        uploading={uploads.some((u) => u.status === 'uploading')}
      />

      <UploadProgress
        uploads={uploads}
        onCancel={handleCancelUpload}
        onDismiss={handleDismissUpload}
      />

      <FileViewer
        file={previewFile}
        isOpen={!!previewFile}
        onClose={() => setPreviewFile(null)}
        onDownload={async (file) => {
          try {
            await api.drive.downloadFile(file.id, file.name);
          } catch (err) {
            logger.error(
              'Download failed',
              {
                component: 'DrivePage',
                action: 'downloadFile',
                metadata: { fileId: file.id, fileName: file.name },
              },
              err instanceof Error ? err : new Error(String(err))
            );
            window.open(api.drive.getDownloadUrl(file.id), '_blank');
          }
        }}
      />
    </div>
  );
}
