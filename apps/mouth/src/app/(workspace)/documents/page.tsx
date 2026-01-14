'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useDriveFiles, useDriveMutations, useDriveStatus } from '@/hooks/useDrive';
import { DriveToolbar } from './components/DriveToolbar';
import { DriveBreadcrumb } from './components/DriveBreadcrumb';
import { FileGrid } from './components/FileGrid';
import { FileList } from './components/FileList';
import { DepartmentHome } from './components/DepartmentHome';
import { FileModal, CreateMenu, ContextMenu, MoveDialog, DropZone, UploadProgress, UploadDialog, FileViewer } from '@/components/documents';
import { Loader2, CloudOff, Cloud, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { motion } from 'framer-motion';
import type { FileItem, BreadcrumbItem, DocType } from '@/lib/api/drive/drive.types';

export default function DocumentsPage() {
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
    error
  } = useDriveFiles(currentFolderId, searchQuery);

  const {
    createFolder,
    createDoc,
    renameFile,
    deleteFile,
    moveFiles
  } = useDriveMutations();

  // Derived Data
  const files = data?.files || [];
  const breadcrumb = data?.breadcrumb || [];
  const isConnected = driveStatus?.connected ?? false;
  const isConfigured = driveStatus?.configured ?? false;
  const isAtRoot = currentFolderId === null && searchQuery === '';

  // Selection State
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [lastSelectedIndex, setLastSelectedIndex] = useState<number>(-1);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; file: FileItem } | null>(null);

  // Modal State
  const [modalMode, setModalMode] = useState<'folder' | 'document' | 'spreadsheet' | 'presentation' | 'rename' | null>(null);
  const [renameTarget, setRenameTarget] = useState<FileItem | null>(null);
  const [createMenuPos, setCreateMenuPos] = useState<{x: number, y: number} | null>(null);
  const [showMoveDialog, setShowMoveDialog] = useState(false);
  const [filesToMove, setFilesToMove] = useState<FileItem[]>([]);
  const [showUploadDialog, setShowUploadDialog] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);

  // Upload State
  const [uploads, setUploads] = useState<Array<{
    id: string;
    name: string;
    progress: number;
    status: 'uploading' | 'completed' | 'error';
    error?: string;
    abortController?: AbortController;
  }>>([]);

  // Handlers
  const handleNavigate = (index: number) => {
    if (index === -1) {
      setCurrentFolderId(null);
    } else {
      setCurrentFolderId(breadcrumb[index].id);
    }
    setSearchQuery('');
  };

  const handleFileClick = (file: FileItem, index: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (e.metaKey || e.ctrlKey) {
      const next = new Set(selectedFiles);
      if (next.has(file.id)) next.delete(file.id);
      else next.add(file.id);
      setSelectedFiles(next);
      setLastSelectedIndex(index);
    } else if (e.shiftKey && lastSelectedIndex !== -1) {
      const start = Math.min(lastSelectedIndex, index);
      const end = Math.max(lastSelectedIndex, index);
      const next = new Set<string>();
      for (let i = start; i <= end; i++) next.add(files[i].id);
      setSelectedFiles(next);
    } else {
      if (file.is_folder) {
        setCurrentFolderId(file.id);
        setSearchQuery('');
        setSelectedFiles(new Set());
      } else {
        // Open file preview instead of Google Drive
        setPreviewFile(file);
      }
    }
  };

  const handleFolderClick = (folder: FileItem) => {
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

  // Upload handler
  const handleUpload = async (filesToUpload: File[]) => {
    setShowUploadDialog(false);

    for (const file of filesToUpload) {
      const uploadId = `${Date.now()}-${file.name}`;
      const abortController = new AbortController();

      // Add to upload list
      setUploads(prev => [...prev, {
        id: uploadId,
        name: file.name,
        progress: 0,
        status: 'uploading',
        abortController,
      }]);

      try {
        await api.drive.uploadFile(file, currentFolderId || 'root', (progress) => {
          setUploads(prev => prev.map(u =>
            u.id === uploadId ? { ...u, progress: progress.percentage } : u
          ));
        });

        // Mark as completed
        setUploads(prev => prev.map(u =>
          u.id === uploadId ? { ...u, status: 'completed', progress: 100 } : u
        ));

        // Refresh file list
        queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });

        // Auto-dismiss after 3 seconds
        setTimeout(() => {
          setUploads(prev => prev.filter(u => u.id !== uploadId));
        }, 3000);

      } catch (error) {
        setUploads(prev => prev.map(u =>
          u.id === uploadId ? {
            ...u,
            status: 'error',
            error: error instanceof Error ? error.message : 'Errore di upload'
          } : u
        ));
      }
    }
  };

  const handleCancelUpload = (uploadId: string) => {
    const upload = uploads.find(u => u.id === uploadId);
    if (upload?.abortController) {
      upload.abortController.abort();
    }
    setUploads(prev => prev.filter(u => u.id !== uploadId));
  };

  const handleDismissUpload = (uploadId: string) => {
    setUploads(prev => prev.filter(u => u.id !== uploadId));
  };

  // Handle files dropped via DropZone
  const handleFilesDropped = (droppedFiles: File[]) => {
    handleUpload(droppedFiles);
  };

  // Close context menu on click elsewhere
  useEffect(() => {
    const handleClick = () => {
      setContextMenu(null);
      setCreateMenuPos(null);
    };
    window.addEventListener('click', handleClick);
    return () => window.removeEventListener('click', handleClick);
  }, []);

  if (statusLoading) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[var(--background)]">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        >
          <Loader2 className="h-10 w-10 text-emerald-500" />
        </motion.div>
        <p className="text-[var(--foreground-muted)]">Caricamento documenti...</p>
      </div>
    );
  }

  if (!isConnected) {
    return (
      <div className="flex min-h-[80vh] flex-col items-center justify-center space-y-8 bg-gradient-to-b from-[var(--background)] to-[var(--background-subtle)] px-6">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="relative"
        >
          <div className="absolute inset-0 animate-pulse rounded-full bg-emerald-500/20 blur-2xl" />
          <div className="relative flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 shadow-xl">
            <CloudOff className="h-12 w-12 text-white" />
          </div>
        </motion.div>

        <div className="text-center">
          <h2 className="mb-2 text-3xl font-bold text-[var(--foreground)]">
            Connetti Google Drive
          </h2>
          <p className="max-w-md text-[var(--foreground-muted)]">
            Accedi ai tuoi documenti aziendali collegando il tuo account Google Drive.
            Tutti i file saranno organizzati per dipartimento.
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
              className="bg-gradient-to-r from-emerald-600 to-teal-500 px-8 py-6 text-lg text-white shadow-xl shadow-emerald-500/25 hover:from-emerald-700 hover:to-teal-600"
            >
              <Cloud className="mr-3 h-5 w-5" />
              Connetti Google Drive
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
            { label: '30TB', desc: 'Storage disponibile' },
            { label: '6', desc: 'Dipartimenti' },
            { label: '100%', desc: 'Sicuro' },
          ].map((stat, i) => (
            <div key={i} className="rounded-xl bg-[var(--background)] p-4 shadow-lg">
              <div className="text-2xl font-bold text-emerald-500">{stat.label}</div>
              <div className="text-sm text-[var(--foreground-muted)]">{stat.desc}</div>
            </div>
          ))}
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--background)]">
      {/* Only show toolbar when not at root OR when searching */}
      {(!isAtRoot || searchQuery) && (
        <>
          <DriveToolbar
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            onUploadClick={() => setShowUploadDialog(true)}
            onCreateClick={(e) => {
              e.stopPropagation();
              setCreateMenuPos({ x: e.clientX, y: e.clientY + 20 });
            }}
            isConnected={isConnected}
          />

          {/* Breadcrumb Area */}
          <div className="border-b border-[var(--border)] bg-[var(--background)] px-4 py-2">
            <DriveBreadcrumb items={breadcrumb} onNavigate={handleNavigate} />
          </div>
        </>
      )}

      {/* Main Content - Wrapped with DropZone for drag & drop uploads */}
      <DropZone onFilesDropped={handleFilesDropped} disabled={!isConnected || isAtRoot}>
        <div className="flex-1 overflow-auto" onClick={() => setSelectedFiles(new Set())}>
          {filesLoading ? (
            <div className="flex h-full items-center justify-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
              >
                <Loader2 className="h-10 w-10 text-emerald-500" />
              </motion.div>
            </div>
          ) : isAtRoot ? (
            // Show Department Home at root level
            <DepartmentHome
              files={files}
              onFolderClick={handleFolderClick}
              storageUsed={0} // TODO: Get from API
              storageTotal={30 * 1024 * 1024 * 1024 * 1024} // 30TB
            />
          ) : (
            // Show normal file view in subfolders
            viewMode === 'grid' ? (
              <FileGrid
                files={files}
                selectedFiles={selectedFiles}
                onFileClick={handleFileClick}
                onFileDoubleClick={(f) => f.is_folder && setCurrentFolderId(f.id)}
                onContextMenu={handleContextMenu}
              />
            ) : (
              <FileList
                files={files}
                selectedFiles={selectedFiles}
                onFileClick={handleFileClick}
                onFileDoubleClick={(f) => f.is_folder && setCurrentFolderId(f.id)}
                onContextMenu={handleContextMenu}
              />
            )
          )}
        </div>
      </DropZone>

      {/* Modals & Menus */}
      <CreateMenu
        isOpen={!!createMenuPos}
        onClose={() => setCreateMenuPos(null)}
        position={createMenuPos || {x: 0, y: 0}}
        onSelect={(mode) => setModalMode(mode)}
      />

      <FileModal
        mode={modalMode as any}
        isOpen={!!modalMode}
        onClose={() => { setModalMode(null); setRenameTarget(null); }}
        initialName={renameTarget?.name || ''}
        loading={createFolder.isPending || createDoc.isPending || renameFile.isPending}
        onSubmit={(name, docType) => {
          if (modalMode === 'rename' && renameTarget) {
            renameFile.mutate({ fileId: renameTarget.id, newName: name }, { onSuccess: () => setModalMode(null) });
          } else if (modalMode === 'folder') {
            createFolder.mutate({ name, parentId: currentFolderId }, { onSuccess: () => setModalMode(null) });
          } else if (docType) {
            createDoc.mutate({ name, parentId: currentFolderId, docType }, { onSuccess: () => setModalMode(null) });
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
            if (confirm(`Eliminare ${file.name}?`)) {
              deleteFile.mutate(file.id);
            }
          }}
          onMove={(file) => {
            setFilesToMove([file]);
            setShowMoveDialog(true);
          }}
          onCopy={() => { /* TODO: Copy */ }}
          onDownload={async (file) => {
            try {
              await api.drive.downloadFile(file.id, file.name);
            } catch (error) {
              logger.error('Download failed:', error);
              // Fallback to window.open if fetch fails
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
            const ids = filesToMove.map(f => f.id);
            moveFiles.mutate({ fileIds: ids, targetFolderId: targetId });
            setShowMoveDialog(false);
          }}
          files={filesToMove}
          currentFolderId={currentFolderId}
          onLoadFolder={async (parentId) => {
            const results = await api.drive.listFiles({ folder_id: parentId || undefined });
            return results.files;
          }}
        />
      )}

      {/* Upload Dialog */}
      <UploadDialog
        isOpen={showUploadDialog}
        onClose={() => setShowUploadDialog(false)}
        onUpload={handleUpload}
        uploading={uploads.some(u => u.status === 'uploading')}
      />

      {/* Upload Progress Indicator */}
      <UploadProgress
        uploads={uploads}
        onCancel={handleCancelUpload}
        onDismiss={handleDismissUpload}
      />

      {/* File Preview Viewer */}
      <FileViewer
        file={previewFile}
        isOpen={!!previewFile}
        onClose={() => setPreviewFile(null)}
        onDownload={async (file) => {
          try {
            await api.drive.downloadFile(file.id, file.name);
          } catch (error) {
            logger.error('Download failed:', error);
            window.open(api.drive.getDownloadUrl(file.id), '_blank');
          }
        }}
      />
    </div>
  );
}
