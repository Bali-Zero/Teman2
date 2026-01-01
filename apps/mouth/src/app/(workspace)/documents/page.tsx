'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  FolderOpen,
  File,
  Search,
  ArrowLeft,
  ChevronRight,
  FileText,
  Image,
  FileSpreadsheet,
  FileCode,
  FolderPlus,
  Upload,
  Grid,
  List,
  ExternalLink,
  Loader2,
  Cloud,
  CloudOff,
  Home,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { FileItem, BreadcrumbItem, ConnectionStatus } from '@/lib/api/drive/drive.types';

type ViewMode = 'grid' | 'list';

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
      // Home
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

  // Disconnect from Google Drive
  const handleDisconnect = async () => {
    try {
      await api.drive.disconnect();
      setIsConnected(false);
      setFiles([]);
      setBreadcrumb([]);
    } catch (error) {
      console.error('Failed to disconnect:', error);
    }
  };

  // Get file icon
  const getFileIcon = (file: FileItem) => {
    if (file.is_folder) {
      return <FolderOpen className="w-10 h-10 text-yellow-500" />;
    }

    const mimeType = file.mime_type;
    if (mimeType.includes('image')) {
      return <Image className="w-10 h-10 text-pink-500" />;
    }
    if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) {
      return <FileSpreadsheet className="w-10 h-10 text-green-500" />;
    }
    if (mimeType.includes('document') || mimeType.includes('word')) {
      return <FileText className="w-10 h-10 text-blue-500" />;
    }
    if (mimeType.includes('code') || mimeType.includes('javascript') || mimeType.includes('json')) {
      return <FileCode className="w-10 h-10 text-purple-500" />;
    }
    return <File className="w-10 h-10 text-gray-400" />;
  };

  // Format file size
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

  // Format date
  const formatDate = (dateStr: string | undefined) => {
    if (!dateStr) return '--';
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  // Initial load
  useEffect(() => {
    checkStatus().then(() => {
      if (isConnected) {
        loadFiles(null);
      }
    });
  }, [checkStatus, isConnected, loadFiles]);

  // Handle OAuth callback success
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('success') === 'google_drive_connected') {
      checkStatus().then(() => {
        if (isConnected) {
          loadFiles(null);
        }
      });
      // Clean URL
      window.history.replaceState({}, document.title, '/documents');
    }
  }, [checkStatus, isConnected, loadFiles]);

  // Not connected state
  if (!isConnected) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6">
        <div className="w-20 h-20 rounded-full bg-blue-500/10 flex items-center justify-center">
          <CloudOff className="w-10 h-10 text-blue-500" />
        </div>
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-[var(--foreground)]">
            Connetti Google Drive
          </h2>
          <p className="text-[var(--foreground-muted)] max-w-md">
            Collega il tuo Google Drive per accedere ai documenti del team direttamente da Zantara.
          </p>
        </div>
        {isConfigured ? (
          <Button
            onClick={handleConnect}
            disabled={connecting}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {connecting ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Cloud className="w-4 h-4 mr-2" />
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <FolderOpen className="w-6 h-6 text-yellow-500" />
            Documenti
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Google Drive del team Bali Zero
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => loadFiles(currentFolderId)}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <Button
            variant={viewMode === 'grid' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('grid')}
          >
            <Grid className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'default' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('list')}
          >
            <List className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={handleDisconnect}>
            <CloudOff className="w-4 h-4 mr-2" />
            Disconnetti
          </Button>
        </div>
      </div>

      {/* Search Bar */}
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Cerca documenti..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/40"
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
        <nav className="flex items-center gap-1 text-sm overflow-x-auto pb-2">
          <button
            onClick={() => navigateToBreadcrumb(-1)}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
          >
            <Home className="w-4 h-4" />
            Home
          </button>
          {breadcrumb.map((item, index) => (
            <React.Fragment key={item.id}>
              <ChevronRight className="w-4 h-4 text-[var(--foreground-muted)]" />
              <button
                onClick={() => navigateToBreadcrumb(index)}
                className="px-2 py-1 rounded hover:bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:text-[var(--foreground)] truncate max-w-[150px]"
              >
                {item.name}
              </button>
            </React.Fragment>
          ))}
        </nav>
      )}

      {/* Loading State */}
      {loading && files.length === 0 ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        </div>
      ) : files.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-[var(--foreground-muted)]">
          <FolderOpen className="w-16 h-16 mb-4 opacity-50" />
          <p>{isSearching ? 'Nessun risultato trovato' : 'Questa cartella è vuota'}</p>
        </div>
      ) : viewMode === 'grid' ? (
        /* Grid View */
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {files.map((file) => (
            <div
              key={file.id}
              onClick={() => file.is_folder && openFolder(file)}
              className={`group relative rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4 transition-all ${
                file.is_folder
                  ? 'cursor-pointer hover:border-blue-500/50 hover:shadow-lg'
                  : ''
              }`}
            >
              <div className="flex flex-col items-center text-center">
                {file.thumbnail_link ? (
                  <img
                    src={file.thumbnail_link}
                    alt={file.name}
                    className="w-16 h-16 object-cover rounded mb-2"
                  />
                ) : (
                  <div className="mb-2">{getFileIcon(file)}</div>
                )}
                <p className="text-sm font-medium text-[var(--foreground)] truncate w-full">
                  {file.name}
                </p>
                <p className="text-xs text-[var(--foreground-muted)]">
                  {file.is_folder ? 'Cartella' : formatSize(file.size)}
                </p>
              </div>
              {file.web_view_link && !file.is_folder && (
                <a
                  href={file.web_view_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 p-1 rounded bg-[var(--background)] hover:bg-[var(--background-secondary)]"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="w-4 h-4 text-[var(--foreground-muted)]" />
                </a>
              )}
            </div>
          ))}
        </div>
      ) : (
        /* List View */
        <div className="rounded-lg border border-[var(--border)] overflow-hidden">
          <table className="w-full">
            <thead className="bg-[var(--background-secondary)]">
              <tr>
                <th className="text-left px-4 py-3 text-sm font-medium text-[var(--foreground-muted)]">
                  Nome
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-[var(--foreground-muted)] hidden md:table-cell">
                  Modificato
                </th>
                <th className="text-left px-4 py-3 text-sm font-medium text-[var(--foreground-muted)] hidden md:table-cell">
                  Dimensione
                </th>
                <th className="w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {files.map((file) => (
                <tr
                  key={file.id}
                  onClick={() => file.is_folder && openFolder(file)}
                  className={`bg-[var(--background-elevated)] transition-colors ${
                    file.is_folder ? 'cursor-pointer hover:bg-[var(--background-secondary)]' : ''
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      {getFileIcon(file)}
                      <span className="text-[var(--foreground)] truncate max-w-[300px]">
                        {file.name}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--foreground-muted)] hidden md:table-cell">
                    {formatDate(file.modified_time)}
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--foreground-muted)] hidden md:table-cell">
                    {file.is_folder ? '--' : formatSize(file.size)}
                  </td>
                  <td className="px-4 py-3">
                    {file.web_view_link && !file.is_folder && (
                      <a
                        href={file.web_view_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-1 rounded hover:bg-[var(--background-secondary)]"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="w-4 h-4 text-[var(--foreground-muted)]" />
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Load More */}
      {nextPageToken && (
        <div className="flex justify-center pt-4">
          <Button variant="outline" onClick={loadMore} disabled={loading}>
            {loading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : null}
            Carica altri
          </Button>
        </div>
      )}
    </div>
  );
}
