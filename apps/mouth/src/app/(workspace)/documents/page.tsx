'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useDriveFiles, useDriveMutations, useDriveStatus } from '@/hooks/useDrive';
import { DriveToolbar } from './components/DriveToolbar';
import { DriveBreadcrumb } from './components/DriveBreadcrumb';
import { FileGrid } from './components/FileGrid';
import { FileList } from './components/FileList';
import { FileModal, CreateMenu, ContextMenu, MoveDialog } from '@/components/documents';
import { Loader2, CloudOff, Cloud } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { FileItem, BreadcrumbItem, DocType } from '@/lib/api/drive/drive.types';

export default function DocumentsPage() {
  // Navigation State
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // React Query Hooks
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
      } else if (file.web_view_link) {
        window.open(file.web_view_link, '_blank');
      }
    }
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
    return <div className="flex h-screen items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-gray-400" /></div>;
  }

  if (!isConnected) {
     return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center space-y-6">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-blue-500/10">
                <CloudOff className="h-10 w-10 text-blue-500" />
            </div>
            <h2 className="text-2xl font-bold">Connetti Google Drive</h2>
            {isConfigured && (
                <Button onClick={handleConnect} className="bg-blue-600 hover:bg-blue-700">
                    <Cloud className="mr-2 h-4 w-4" /> Connetti
                </Button>
            )}
        </div>
     );
  }

  return (
    <div className="flex flex-col h-full bg-[var(--background)]">
      <DriveToolbar 
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        onUploadClick={() => {/* TODO: Implement upload */}}
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

      {/* Main Content */}
      <div className="flex-1 overflow-auto" onClick={() => setSelectedFiles(new Set())}>
        {filesLoading ? (
             <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
             </div>
        ) : (
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
            onDownload={(file) => {
                window.open(api.drive.getDownloadUrl(file.id), '_blank');
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
    </div>
  );
}
