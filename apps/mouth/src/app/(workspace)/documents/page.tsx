'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  File,
  Search,
  ChevronRight,
  FileText,
  Image,
  FileSpreadsheet,
  FileCode,
  Grid,
  List,
  ExternalLink,
  Loader2,
  Cloud,
  CloudOff,
  Home,
  RefreshCw,
  FolderOpen,
  Plus,
  Upload,
  Trash2,
  FolderInput,
  Check,
  Folder,
  Presentation,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { FileItem, BreadcrumbItem, DocType } from '@/lib/api/drive/drive.types';
import {
  ContextMenu,
  DropZone,
  UploadProgress,
  FileModal,
  CreateMenu,
  MoveDialog,
} from '@/components/documents';

type ViewMode = 'grid' | 'list';
type ModalMode = 'folder' | 'document' | 'spreadsheet' | 'presentation' | 'rename' | null;

interface UploadItem {
  id: string;
  name: string;
  progress: number;
  status: 'uploading' | 'completed' | 'error';
  error?: string;
  abortController?: AbortController;
}

export default function DocumentsPage() {
  const [isConnected, setIsConnected] = useState(false);
  const [isConfigured, setIsConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [breadcrumb, setBreadcrumb] = useState<BreadcrumbItem[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [connecting, setConnecting] = useState(false);

  // CRUD State
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    file: FileItem;
  } | null>(null);
  const [createMenuPosition, setCreateMenuPosition] = useState<{ x: number; y: number } | null>(
    null
  );
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [renameFile, setRenameFile] = useState<FileItem | null>(null);
  const [showMoveDialog, setShowMoveDialog] = useState(false);
  const [filesToMove, setFilesToMove] = useState<FileItem[]>([]);
  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const [operationLoading, setOperationLoading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const lastSelectedIndex = useRef<number>(-1);

  // Check connection status
  const checkStatus = useCallback(async () => {
    try {
      const status = await api.drive.getStatus();
      setIsConnected(status.connected);
      setIsConfigured(status.configured);
    } catch (error) {
      console.error('Failed to check Google Drive status:', error);
      setIsConnected(false);
    }
  }, []);

  // Load files
  const loadFiles = useCallback(async (folderId: string | null = null) => {
    setLoading(true);
    try {
      const response = await api.drive.listFiles({
        folder_id: folderId || undefined,
      });
      setFiles(response.files);
      setBreadcrumb(response.breadcrumb);
      setNextPageToken(response.next_page_token);
      setCurrentFolderId(folderId);
      setSelectedFiles(new Set());
    } catch (error) {
      console.error('Failed to load files:', error);
      setFiles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load more files (pagination)
  const loadMore = async () => {
    if (!nextPageToken) return;
    try {
      const response = await api.drive.listFiles({
        folder_id: currentFolderId || undefined,
        page_token: nextPageToken,
      });
      setFiles([...files, ...response.files]);
      setNextPageToken(response.next_page_token);
    } catch (error) {
      console.error('Failed to load more files:', error);
    }
  };

  // Search files
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setLoading(true);
    try {
      const results = await api.drive.searchFiles(searchQuery);
      setFiles(results);
      setBreadcrumb([]);
      setCurrentFolderId(null);
      setNextPageToken(null);
      setSelectedFiles(new Set());
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  // Clear search
  const clearSearch = () => {
    setSearchQuery('');
    setIsSearching(false);
    loadFiles(null);
  };

  // Navigate to folder
  const openFolder = (file: FileItem) => {
    if (file.is_folder) {
      setIsSearching(false);
      setSearchQuery('');
      loadFiles(file.id);
    }
  };

  // Navigate via breadcrumb
  const navigateToBreadcrumb = (index: number) => {
    if (index === -1) {
      loadFiles(null);
    } else {
      loadFiles(breadcrumb[index].id);
    }
  };

  // Connect to Google Drive
  const handleConnect = async () => {
    setConnecting(true);
    try {
      const { auth_url } = await api.drive.getAuthUrl();
      window.location.href = auth_url;
    } catch (error) {
      console.error('Failed to get auth URL:', error);
      setConnecting(false);
    }
  };

  // ============== Selection Handlers ==============

  const handleFileClick = (file: FileItem, index: number, e: React.MouseEvent) => {
    e.stopPropagation();

    if (e.metaKey || e.ctrlKey) {
      // Toggle selection
      setSelectedFiles((prev) => {
        const next = new Set(prev);
        if (next.has(file.id)) {
          next.delete(file.id);
        } else {
          next.add(file.id);
        }
        return next;
      });
      lastSelectedIndex.current = index;
    } else if (e.shiftKey && lastSelectedIndex.current !== -1) {
      // Range selection
      const start = Math.min(lastSelectedIndex.current, index);
      const end = Math.max(lastSelectedIndex.current, index);
      const newSelection = new Set<string>();
      for (let i = start; i <= end; i++) {
        newSelection.add(files[i].id);
      }
      setSelectedFiles(newSelection);
    } else {
      // Single selection or deselect
      if (selectedFiles.size === 1 && selectedFiles.has(file.id)) {
        setSelectedFiles(new Set());
      } else {
        setSelectedFiles(new Set([file.id]));
      }
      lastSelectedIndex.current = index;
    }
  };

  const handleFileDoubleClick = (file: FileItem) => {
    if (file.is_folder) {
      openFolder(file);
    } else if (file.web_view_link) {
      window.open(file.web_view_link, '_blank');
    }
  };

  const handleContextMenu = (file: FileItem, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // If right-clicking on a non-selected file, select only that file
    if (!selectedFiles.has(file.id)) {
      setSelectedFiles(new Set([file.id]));
    }

    setContextMenu({ x: e.clientX, y: e.clientY, file });
  };

  const clearSelection = () => {
    setSelectedFiles(new Set());
    setContextMenu(null);
  };

  // ============== CRUD Operations ==============

  const handleCreateFolder = async (name: string) => {
    setOperationLoading(true);
    try {
      const result = await api.drive.createFolder({
        name,
        parent_id: currentFolderId || 'root',
      });
      if (result.success) {
        loadFiles(currentFolderId);
      }
    } catch (error) {
      console.error('Failed to create folder:', error);
    } finally {
      setOperationLoading(false);
      setModalMode(null);
    }
  };

  const handleCreateDoc = async (name: string, docType?: DocType) => {
    if (!docType) return;
    setOperationLoading(true);
    try {
      const result = await api.drive.createDoc({
        name,
        parent_id: currentFolderId || 'root',
        doc_type: docType,
      });
      if (result.success && result.file?.web_view_link) {
        window.open(result.file.web_view_link, '_blank');
        loadFiles(currentFolderId);
      }
    } catch (error) {
      console.error('Failed to create document:', error);
    } finally {
      setOperationLoading(false);
      setModalMode(null);
    }
  };

  const handleRename = async (newName: string) => {
    if (!renameFile) return;
    setOperationLoading(true);
    try {
      const result = await api.drive.renameFile(renameFile.id, newName);
      if (result.success) {
        loadFiles(currentFolderId);
      }
    } catch (error) {
      console.error('Failed to rename:', error);
    } finally {
      setOperationLoading(false);
      setModalMode(null);
      setRenameFile(null);
    }
  };

  const handleDelete = async (file: FileItem) => {
    if (!confirm(`Sei sicuro di voler eliminare "${file.name}"?`)) return;
    setOperationLoading(true);
    try {
      const result = await api.drive.deleteFile(file.id);
      if (result.success) {
        loadFiles(currentFolderId);
        setSelectedFiles(new Set());
      }
    } catch (error) {
      console.error('Failed to delete:', error);
    } finally {
      setOperationLoading(false);
    }
  };

  const handleBulkDelete = async () => {
    const count = selectedFiles.size;
    if (!confirm(`Sei sicuro di voler eliminare ${count} elementi?`)) return;
    setOperationLoading(true);
    try {
      const result = await api.drive.deleteFiles(Array.from(selectedFiles));
      if (result.success || result.failed.length < count) {
        loadFiles(currentFolderId);
        setSelectedFiles(new Set());
      }
    } catch (error) {
      console.error('Failed to delete files:', error);
    } finally {
      setOperationLoading(false);
    }
  };

  const handleMove = async (targetFolderId: string) => {
    setOperationLoading(true);
    try {
      const fileIds = filesToMove.map((f) => f.id);
      const result = await api.drive.moveFiles(
        fileIds,
        targetFolderId === 'root' ? '' : targetFolderId
      );
      if (result.success || result.failed.length < fileIds.length) {
        loadFiles(currentFolderId);
        setSelectedFiles(new Set());
      }
    } catch (error) {
      console.error('Failed to move files:', error);
    } finally {
      setOperationLoading(false);
      setShowMoveDialog(false);
      setFilesToMove([]);
    }
  };

  const handleCopy = async (file: FileItem) => {
    setOperationLoading(true);
    try {
      const result = await api.drive.copyFile(file.id, `${file.name} (copia)`);
      if (result.success) {
        loadFiles(currentFolderId);
      }
    } catch (error) {
      console.error('Failed to copy:', error);
    } finally {
      setOperationLoading(false);
    }
  };

  const handleDownload = (file: FileItem) => {
    const url = api.drive.getDownloadUrl(file.id);
    window.open(url, '_blank');
  };

  // ============== Upload Handlers ==============

  const handleFilesDropped = async (droppedFiles: File[]) => {
    for (const file of droppedFiles) {
      uploadFile(file);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      for (const file of Array.from(files)) {
        uploadFile(file);
      }
    }
    // Reset input
    e.target.value = '';
  };

  const uploadFile = async (file: File) => {
    const uploadId = `upload-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    setUploads((prev) => [
      ...prev,
      {
        id: uploadId,
        name: file.name,
        progress: 0,
        status: 'uploading',
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

      // Refresh file list after upload completes
      loadFiles(currentFolderId);
    } catch (error) {
      setUploads((prev) =>
        prev.map((u) =>
          u.id === uploadId
            ? { ...u, status: 'error', error: error instanceof Error ? error.message : 'Upload failed' }
            : u
        )
      );
    }
  };

  const cancelUpload = (uploadId: string) => {
    // For now just mark as error since we don't have abort controller
    setUploads((prev) =>
      prev.map((u) =>
        u.id === uploadId ? { ...u, status: 'error', error: 'Annullato' } : u
      )
    );
  };

  const dismissUpload = (uploadId: string) => {
    setUploads((prev) => prev.filter((u) => u.id !== uploadId));
  };

  // Load folders for move dialog
  const loadFolderChildren = async (folderId: string | null): Promise<FileItem[]> => {
    try {
      const response = await api.drive.listFiles({
        folder_id: folderId || undefined,
      });
      return response.files.filter((f) => f.is_folder);
    } catch (error) {
      console.error('Failed to load folders:', error);
      return [];
    }
  };

  // ============== UI Helpers ==============

  const getDepartmentColors = (
    folderName: string
  ): { from: string; to: string; shadow: string } => {
    const name = folderName.toLowerCase();

    if (
      name.includes('legal') ||
      name.includes('visa') ||
      name.includes('immigration') ||
      name.includes('kitas')
    ) {
      return { from: '#60A5FA', to: '#3B82F6', shadow: 'rgba(59, 130, 246, 0.4)' };
    }
    if (
      name.includes('tax') ||
      name.includes('pajak') ||
      name.includes('npwp') ||
      name.includes('spt')
    ) {
      return { from: '#4ADE80', to: '#22C55E', shadow: 'rgba(34, 197, 94, 0.4)' };
    }
    if (
      name.includes('business') ||
      name.includes('pt pma') ||
      name.includes('company') ||
      name.includes('corporate')
    ) {
      return { from: '#C084FC', to: '#A855F7', shadow: 'rgba(168, 85, 247, 0.4)' };
    }
    if (
      name.includes('member') ||
      name.includes('hr') ||
      name.includes('team') ||
      name.includes('staff')
    ) {
      return { from: '#FBBF24', to: '#F59E0B', shadow: 'rgba(245, 158, 11, 0.4)' };
    }
    if (name.includes('client') || name.includes('customer') || name.includes('klien')) {
      return { from: '#22D3EE', to: '#06B6D4', shadow: 'rgba(6, 182, 212, 0.4)' };
    }
    if (
      name.includes('finance') ||
      name.includes('accounting') ||
      name.includes('invoice') ||
      name.includes('payment')
    ) {
      return { from: '#34D399', to: '#10B981', shadow: 'rgba(16, 185, 129, 0.4)' };
    }
    if (
      name.includes('shared') ||
      name.includes('_shared') ||
      name.includes('general') ||
      name.includes('common')
    ) {
      return { from: '#FB923C', to: '#F97316', shadow: 'rgba(249, 115, 22, 0.4)' };
    }
    if (
      ['sahira', 'nina', 'anton', 'adit', 'krisna', 'ruslana', 'veronika'].some((n) =>
        name.includes(n)
      )
    ) {
      return { from: '#FB7185', to: '#F43F5E', shadow: 'rgba(244, 63, 94, 0.4)' };
    }
    if (name.includes('bali zero') || name.includes('balizero')) {
      return { from: '#38BDF8', to: '#0EA5E9', shadow: 'rgba(14, 165, 233, 0.4)' };
    }
    return { from: '#38BDF8', to: '#0EA5E9', shadow: 'rgba(14, 165, 233, 0.4)' };
  };

  const MacOSFolder = ({ name }: { name: string }) => {
    const colors = getDepartmentColors(name);
    return (
      <div
        className="relative h-14 w-16 transition-transform group-hover:scale-105"
        style={{ filter: `drop-shadow(0 4px 8px ${colors.shadow})` }}
      >
        <svg
          viewBox="0 0 64 56"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-full w-full"
        >
          <path
            d="M4 12C4 9.79086 5.79086 8 8 8H24L28 14H56C58.2091 14 60 15.7909 60 18V48C60 50.2091 58.2091 52 56 52H8C5.79086 52 4 50.2091 4 48V12Z"
            fill={`url(#folderGradient-${name.replace(/\s/g, '')})`}
          />
          <path
            d="M4 20C4 17.7909 5.79086 16 8 16H56C58.2091 16 60 17.7909 60 20V48C60 50.2091 58.2091 52 56 52H8C5.79086 52 4 50.2091 4 48V20Z"
            fill={`url(#folderFront-${name.replace(/\s/g, '')})`}
          />
          <path
            d="M8 16H56C58.2091 16 60 17.7909 60 20V24H4V20C4 17.7909 5.79086 16 8 16Z"
            fill="white"
            fillOpacity="0.25"
          />
          <defs>
            <linearGradient
              id={`folderGradient-${name.replace(/\s/g, '')}`}
              x1="32"
              y1="8"
              x2="32"
              y2="52"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor={colors.from} />
              <stop offset="1" stopColor={colors.to} />
            </linearGradient>
            <linearGradient
              id={`folderFront-${name.replace(/\s/g, '')}`}
              x1="32"
              y1="16"
              x2="32"
              y2="52"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor={colors.from} />
              <stop offset="1" stopColor={colors.to} />
            </linearGradient>
          </defs>
        </svg>
      </div>
    );
  };

  const getFileIcon = (file: FileItem, size: 'sm' | 'lg' = 'lg') => {
    const mimeType = file.mime_type || '';
    const sizeClass = size === 'sm' ? 'h-5 w-5' : 'h-12 w-12';

    if (file.is_folder) {
      return <Folder className={`${sizeClass} text-amber-500`} />;
    }
    if (mimeType.includes('image')) {
      return <Image className={`${sizeClass} text-pink-500`} />;
    }
    if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) {
      return <FileSpreadsheet className={`${sizeClass} text-green-500`} />;
    }
    if (mimeType.includes('presentation')) {
      return <Presentation className={`${sizeClass} text-yellow-500`} />;
    }
    if (mimeType.includes('document') || mimeType.includes('word')) {
      return <FileText className={`${sizeClass} text-blue-500`} />;
    }
    if (mimeType.includes('pdf')) {
      return <FileText className={`${sizeClass} text-red-500`} />;
    }
    if (
      mimeType.includes('code') ||
      mimeType.includes('javascript') ||
      mimeType.includes('json')
    ) {
      return <FileCode className={`${sizeClass} text-purple-500`} />;
    }
    return <File className={`${sizeClass} text-gray-400`} />;
  };

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

  const formatDate = (dateStr: string | undefined) => {
    if (!dateStr) return '--';
    return new Date(dateStr).toLocaleDateString('it-IT', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  // ============== Effects ==============

  useEffect(() => {
    checkStatus().then(() => {
      if (isConnected) {
        loadFiles(null);
      }
    });
  }, [checkStatus, isConnected, loadFiles]);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('success') === 'google_drive_connected') {
      checkStatus().then(() => {
        if (isConnected) {
          loadFiles(null);
        }
      });
      window.history.replaceState({}, document.title, '/documents');
    }
  }, [checkStatus, isConnected, loadFiles]);

  // Close context menu on scroll
  useEffect(() => {
    const handleScroll = () => setContextMenu(null);
    window.addEventListener('scroll', handleScroll, true);
    return () => window.removeEventListener('scroll', handleScroll, true);
  }, []);

  // ============== Render ==============

  if (!isConnected) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center space-y-6">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-blue-500/10">
          <CloudOff className="h-10 w-10 text-blue-500" />
        </div>
        <div className="space-y-2 text-center">
          <h2 className="text-2xl font-bold text-[var(--foreground)]">Connetti Google Drive</h2>
          <p className="max-w-md text-[var(--foreground-muted)]">
            Collega il tuo Google Drive per accedere ai documenti del team direttamente da Zantara.
          </p>
        </div>
        {isConfigured ? (
          <Button onClick={handleConnect} disabled={connecting} className="bg-blue-600 hover:bg-blue-700">
            {connecting ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Cloud className="mr-2 h-4 w-4" />
            )}
            Connetti Google Drive
          </Button>
        ) : (
          <div className="text-center text-sm text-[var(--foreground-muted)]">
            <p>Google Drive non configurato.</p>
            <p>Contatta l&apos;amministratore per abilitare l&apos;integrazione.</p>
          </div>
        )}
      </div>
    );
  }

  return (
    <DropZone onFilesDropped={handleFilesDropped} disabled={loading}>
      <div className="space-y-4" onClick={clearSelection}>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-2xl font-bold text-[var(--foreground)]">
              <FolderOpen className="h-6 w-6 text-yellow-500" />
              Documenti
            </h1>
            <p className="text-sm text-[var(--foreground-muted)]">Google Drive del team Bali Zero</p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => loadFiles(currentFolderId)}
              disabled={loading}
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant={viewMode === 'grid' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('grid')}
            >
              <Grid className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setViewMode('list')}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-between gap-4 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-2">
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700"
              onClick={(e) => {
                e.stopPropagation();
                const rect = e.currentTarget.getBoundingClientRect();
                setCreateMenuPosition({ x: rect.left, y: rect.bottom + 4 });
              }}
            >
              <Plus className="mr-1 h-4 w-4" />
              Nuovo
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              <Upload className="mr-1 h-4 w-4" />
              Carica
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileInputChange}
            />
          </div>

          {/* Selection actions */}
          {selectedFiles.size > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-[var(--foreground-muted)]">
                {selectedFiles.size} selezionati
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={(e) => {
                  e.stopPropagation();
                  const selected = files.filter((f) => selectedFiles.has(f.id));
                  setFilesToMove(selected);
                  setShowMoveDialog(true);
                }}
              >
                <FolderInput className="mr-1 h-4 w-4" />
                Sposta
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="text-red-600 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-900/20"
                onClick={(e) => {
                  e.stopPropagation();
                  handleBulkDelete();
                }}
              >
                <Trash2 className="mr-1 h-4 w-4" />
                Elimina
              </Button>
            </div>
          )}
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--foreground-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cerca documenti..."
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] py-2 pl-10 pr-4 text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
          </div>
          <Button type="submit" disabled={!searchQuery.trim()}>
            Cerca
          </Button>
          {isSearching && (
            <Button type="button" variant="ghost" onClick={clearSearch}>
              Cancella
            </Button>
          )}
        </form>

        {/* Breadcrumb */}
        {!isSearching && (
          <nav className="flex items-center gap-1 overflow-x-auto pb-2 text-sm">
            <button
              onClick={() => navigateToBreadcrumb(-1)}
              className="flex items-center gap-1 rounded px-2 py-1 text-[var(--foreground-muted)] hover:bg-[var(--background-secondary)] hover:text-[var(--foreground)]"
            >
              <Home className="h-4 w-4" />
              Home
            </button>
            {breadcrumb.map((item, index) => (
              <React.Fragment key={item.id}>
                <ChevronRight className="h-4 w-4 text-[var(--foreground-muted)]" />
                <button
                  onClick={() => navigateToBreadcrumb(index)}
                  className="max-w-[150px] truncate rounded px-2 py-1 text-[var(--foreground-muted)] hover:bg-[var(--background-secondary)] hover:text-[var(--foreground)]"
                >
                  {item.name}
                </button>
              </React.Fragment>
            ))}
          </nav>
        )}

        {/* Files */}
        {loading && files.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          </div>
        ) : files.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--foreground-muted)]">
            <FolderOpen className="mb-4 h-16 w-16 opacity-50" />
            <p>{isSearching ? 'Nessun risultato trovato' : 'Questa cartella è vuota'}</p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="mr-2 h-4 w-4" />
              Carica file
            </Button>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-3 gap-4 p-4 md:grid-cols-5 lg:grid-cols-7">
            {files.map((file, index) => {
              const isSelected = selectedFiles.has(file.id);
              return (
                <div
                  key={file.id}
                  onClick={(e) => handleFileClick(file, index, e)}
                  onDoubleClick={() => handleFileDoubleClick(file)}
                  onContextMenu={(e) => handleContextMenu(file, e)}
                  className={`group relative flex cursor-pointer flex-col items-center rounded-xl p-3 text-center transition-all ${
                    isSelected
                      ? 'bg-emerald-100 ring-2 ring-emerald-500 dark:bg-emerald-900/30'
                      : 'hover:bg-white/5'
                  }`}
                >
                  {/* Selection checkbox */}
                  <div
                    className={`absolute left-2 top-2 flex h-5 w-5 items-center justify-center rounded border transition-opacity ${
                      isSelected
                        ? 'border-emerald-500 bg-emerald-500 opacity-100'
                        : 'border-gray-300 bg-white opacity-0 group-hover:opacity-100 dark:border-gray-600 dark:bg-gray-700'
                    }`}
                  >
                    {isSelected && <Check className="h-3 w-3 text-white" />}
                  </div>

                  {/* Icon */}
                  <div className="mb-2">
                    {file.is_folder ? (
                      <MacOSFolder name={file.name} />
                    ) : file.thumbnail_link ? (
                      <img
                        src={file.thumbnail_link}
                        alt={file.name}
                        className="h-14 w-14 rounded-lg object-cover shadow-md"
                      />
                    ) : (
                      getFileIcon(file)
                    )}
                  </div>

                  {/* Name */}
                  <div className="w-full">
                    <span className="inline-block max-w-full truncate rounded-md bg-[var(--foreground)]/10 px-2 py-0.5 text-sm font-medium text-[var(--foreground)] backdrop-blur-sm">
                      {file.name}
                    </span>
                  </div>

                  {/* Size */}
                  <p className="mt-1 text-xs text-[var(--foreground-muted)]">
                    {file.is_folder ? '' : formatSize(file.size)}
                  </p>

                  {/* External link */}
                  {file.web_view_link && !file.is_folder && (
                    <a
                      href={file.web_view_link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="absolute right-2 top-2 rounded-lg bg-black/40 p-1.5 opacity-0 backdrop-blur-sm transition-opacity hover:bg-black/60 group-hover:opacity-100"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <ExternalLink className="h-3.5 w-3.5 text-white" />
                    </a>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-[var(--border)]">
            <table className="w-full">
              <thead className="bg-[var(--background-secondary)]">
                <tr>
                  <th className="w-10 px-4 py-3"></th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-[var(--foreground-muted)]">
                    Nome
                  </th>
                  <th className="hidden px-4 py-3 text-left text-sm font-medium text-[var(--foreground-muted)] md:table-cell">
                    Modificato
                  </th>
                  <th className="hidden px-4 py-3 text-left text-sm font-medium text-[var(--foreground-muted)] md:table-cell">
                    Dimensione
                  </th>
                  <th className="w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {files.map((file, index) => {
                  const isSelected = selectedFiles.has(file.id);
                  return (
                    <tr
                      key={file.id}
                      onClick={(e) => handleFileClick(file, index, e)}
                      onDoubleClick={() => handleFileDoubleClick(file)}
                      onContextMenu={(e) => handleContextMenu(file, e)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? 'bg-emerald-50 dark:bg-emerald-900/20'
                          : 'bg-[var(--background-elevated)] hover:bg-[var(--background-secondary)]'
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div
                          className={`flex h-5 w-5 items-center justify-center rounded border ${
                            isSelected
                              ? 'border-emerald-500 bg-emerald-500'
                              : 'border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-700'
                          }`}
                        >
                          {isSelected && <Check className="h-3 w-3 text-white" />}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {getFileIcon(file, 'sm')}
                          <span className="max-w-[300px] truncate text-[var(--foreground)]">
                            {file.name}
                          </span>
                        </div>
                      </td>
                      <td className="hidden px-4 py-3 text-sm text-[var(--foreground-muted)] md:table-cell">
                        {formatDate(file.modified_time)}
                      </td>
                      <td className="hidden px-4 py-3 text-sm text-[var(--foreground-muted)] md:table-cell">
                        {file.is_folder ? '--' : formatSize(file.size)}
                      </td>
                      <td className="px-4 py-3">
                        {file.web_view_link && !file.is_folder && (
                          <a
                            href={file.web_view_link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded p-1 hover:bg-[var(--background-secondary)]"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="h-4 w-4 text-[var(--foreground-muted)]" />
                          </a>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Load More */}
        {nextPageToken && (
          <div className="flex justify-center pt-4">
            <Button variant="outline" onClick={loadMore} disabled={loading}>
              {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Carica altri
            </Button>
          </div>
        )}
      </div>

      {/* Context Menu */}
      {contextMenu && (
        <ContextMenu
          file={contextMenu.file}
          position={{ x: contextMenu.x, y: contextMenu.y }}
          onClose={() => setContextMenu(null)}
          onOpen={(file) => handleFileDoubleClick(file)}
          onRename={(file) => {
            setRenameFile(file);
            setModalMode('rename');
          }}
          onDelete={(file) => handleDelete(file)}
          onMove={(file) => {
            setFilesToMove([file]);
            setShowMoveDialog(true);
          }}
          onCopy={(file) => handleCopy(file)}
          onDownload={(file) => handleDownload(file)}
        />
      )}

      {/* Create Menu */}
      {createMenuPosition && (
        <CreateMenu
          isOpen={true}
          onClose={() => setCreateMenuPosition(null)}
          onSelect={(mode) => setModalMode(mode)}
          position={createMenuPosition}
        />
      )}

      {/* File Modal (Create/Rename) */}
      <FileModal
        mode={modalMode === 'rename' ? 'rename' : modalMode || 'folder'}
        isOpen={modalMode !== null}
        onClose={() => {
          setModalMode(null);
          setRenameFile(null);
        }}
        onSubmit={(name, docType) => {
          if (modalMode === 'rename') {
            handleRename(name);
          } else if (modalMode === 'folder') {
            handleCreateFolder(name);
          } else if (docType) {
            handleCreateDoc(name, docType);
          }
        }}
        initialName={renameFile?.name || ''}
        loading={operationLoading}
      />

      {/* Move Dialog */}
      <MoveDialog
        isOpen={showMoveDialog}
        files={filesToMove}
        currentFolderId={currentFolderId}
        onClose={() => {
          setShowMoveDialog(false);
          setFilesToMove([]);
        }}
        onMove={handleMove}
        onLoadFolder={loadFolderChildren}
        loading={operationLoading}
      />

      {/* Upload Progress */}
      <UploadProgress uploads={uploads} onCancel={cancelUpload} onDismiss={dismissUpload} />
    </DropZone>
  );
}
