'use client';

import React, { useState, useEffect } from 'react';
import {
  File,
  Download,
  Eye,
  Search,
  Upload,
  ArrowLeft,
  Loader2,
  Image as ImageIcon,
  FileText,
  FileSpreadsheet,
  FileVideo,
  FileAudio,
  Archive,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';

interface FileInfo {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number | null;
  created_time: string;
  modified_time: string;
  thumbnail_url: string | null;
  download_url: string;
  is_folder: boolean;
}

interface FolderFilesBrowserProps {
  clientId: number;
  clientName: string;
  folderName: string;
  folderLabel: string;
  onBack: () => void;
}

const STANDARD_FOLDERS: Record<string, { label: string; icon: string }> = {
  '00_Profile': { label: 'Profile', icon: '👤' },
  '01_Immigration': { label: 'Immigration', icon: '🛂' },
  '02_Company': { label: 'Company', icon: '🏢' },
  '03_Tax': { label: 'Tax', icon: '💰' },
  '04_Family': { label: 'Family', icon: '👨‍👩‍👧‍👦' },
  '99_Misc': { label: 'Misc', icon: '📁' },
};

function getFileIcon(mimeType: string) {
  if (mimeType.startsWith('image/')) return ImageIcon;
  if (mimeType === 'application/pdf') return FileText;
  if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) return FileSpreadsheet;
  if (mimeType.startsWith('video/')) return FileVideo;
  if (mimeType.startsWith('audio/')) return FileAudio;
  if (mimeType.includes('zip') || mimeType.includes('archive')) return Archive;
  return File;
}

function formatFileSize(bytes: number | null): string {
  if (!bytes) return 'Unknown size';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function FolderFilesBrowser({
  clientId,
  clientName,
  folderName,
  folderLabel,
  onBack,
}: FolderFilesBrowserProps) {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [total, setTotal] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [previewFile, setPreviewFile] = useState<FileInfo | null>(null);

  const folderInfo = STANDARD_FOLDERS[folderName] || { label: folderLabel, icon: '📁' };

  useEffect(() => {
    loadFiles(true);
  }, [folderName]);

  useEffect(() => {
    if (searchQuery) {
      const debounceTimer = setTimeout(() => loadFiles(true), 300);
      return () => clearTimeout(debounceTimer);
    } else {
      loadFiles(true);
    }
  }, [searchQuery]);

  const loadFiles = async (reset = true) => {
    if (reset) {
      setIsLoading(true);
      setOffset(0);
      setHasMore(true);
    } else {
      setIsLoadingMore(true);
    }

    try {
      const currentOffset = reset ? 0 : offset;
      const data = await api.crm.listFolderFiles(clientId, folderName, {
        limit: 50,
        offset: currentOffset,
        search: searchQuery || undefined,
      });

      if (reset) {
        setFiles(data.files);
      } else {
        setFiles((prev) => [...prev, ...data.files]);
      }

      setTotal(data.total);
      setHasMore(data.has_more);
      setOffset(currentOffset + data.files.length);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to load files';
      toast.error(errorMessage);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  };

  const handleDownload = async (file: FileInfo) => {
    try {
      // Download via proxy backend
      const response = await fetch(file.download_url, {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Download failed');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast.success(`Downloaded ${file.name}`);
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to download file';
      toast.error(errorMessage);
    }
  };

  const handleDownloadMultiple = async () => {
    if (selectedFiles.size === 0) return;

    try {
      // Download each file sequentially
      const selectedFilesList = files.filter((f) => selectedFiles.has(f.id));

      for (const file of selectedFilesList) {
        await handleDownload(file);
        // Small delay between downloads
        await new Promise((resolve) => setTimeout(resolve, 500));
      }

      toast.success(`Downloaded ${selectedFiles.size} file(s)`);
      setSelectedFiles(new Set());
    } catch (error: unknown) {
      logger.error('Failed to download files', { component: 'FolderFilesBrowser', action: 'handleDownloadMultiple' }, error instanceof Error ? error : new Error(String(error)));
      toast.error('Failed to download files');
    }
  };

  const handlePreview = (file: FileInfo) => {
    // Only preview images for now
    if (file.mime_type.startsWith('image/')) {
      setPreviewFile(file);
    } else {
      toast.info('Preview available only for images');
    }
  };

  const toggleFileSelection = (fileId: string) => {
    setSelectedFiles((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(fileId)) {
        newSet.delete(fileId);
      } else {
        newSet.add(fileId);
      }
      return newSet;
    });
  };

  const filteredFiles = files.filter((file) =>
    file.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--foreground-muted)]" />
        <span className="ml-2 text-sm text-[var(--foreground-muted)]">Loading files...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack} className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to Overview
          </Button>
          <div className="h-6 w-px bg-[var(--border)]" />
          <div className="flex items-center gap-2">
            <span className="text-2xl">{folderInfo.icon}</span>
            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)]">{folderInfo.label}</h2>
              <p className="text-xs text-[var(--foreground-muted)]">
                {folderName} • {total} file{total !== 1 ? 's' : ''}
              </p>
            </div>
          </div>
        </div>
        {selectedFiles.size > 0 && (
          <Button onClick={handleDownloadMultiple} className="gap-2">
            <Download className="w-4 h-4" />
            Download {selectedFiles.size} file{selectedFiles.size !== 1 ? 's' : ''}
          </Button>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
        <input
          type="text"
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
        />
      </div>

      {/* Files List */}
      {filteredFiles.length === 0 ? (
        <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)] p-12 text-center">
          <File className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">No files found</h3>
          <p className="text-sm text-[var(--foreground-muted)] mb-4">
            {searchQuery ? 'Try a different search term' : 'This folder is empty'}
          </p>
          <Button
            variant="outline"
            onClick={() => {
              toast.info('Upload feature coming soon');
            }}
            className="gap-2"
          >
            <Upload className="w-4 h-4" />
            Upload Files
          </Button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredFiles.map((file) => {
              const FileIcon = getFileIcon(file.mime_type);
              const isSelected = selectedFiles.has(file.id);
              const isImage = file.mime_type.startsWith('image/');

              return (
                <div
                  key={file.id}
                  className={`rounded-lg border p-4 bg-[var(--background-secondary)] hover:bg-[var(--background-elevated)] transition-colors cursor-pointer ${
                    isSelected
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                      : 'border-[var(--border)]'
                  }`}
                  onClick={() => toggleFileSelection(file.id)}
                >
                  <div className="flex items-start gap-3">
                    {/* Thumbnail or Icon */}
                    {isImage && file.thumbnail_url ? (
                      <div className="w-16 h-16 rounded-lg overflow-hidden border border-[var(--border)] bg-[var(--background)] flex-shrink-0">
                        <img
                          src={file.thumbnail_url}
                          alt={file.name}
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            (e.target as HTMLImageElement).style.display = 'none';
                          }}
                        />
                      </div>
                    ) : (
                      <div className="w-16 h-16 rounded-lg bg-[var(--background-elevated)] flex items-center justify-center flex-shrink-0">
                        <FileIcon className="w-8 h-8 text-[var(--foreground-muted)]" />
                      </div>
                    )}

                    {/* File Info */}
                    <div className="flex-1 min-w-0">
                      <h4 className="font-medium text-[var(--foreground)] truncate mb-1">
                        {file.name}
                      </h4>
                      <p className="text-xs text-[var(--foreground-muted)] mb-2">
                        {formatFileSize(file.size_bytes)}
                      </p>
                      <div className="flex items-center gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDownload(file);
                          }}
                          className="h-7 px-2 gap-1"
                        >
                          <Download className="w-3 h-3" />
                        </Button>
                        {isImage && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handlePreview(file);
                            }}
                            className="h-7 px-2 gap-1"
                          >
                            <Eye className="w-3 h-3" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Load More */}
          {hasMore && (
            <div className="flex justify-center pt-4">
              <Button
                variant="outline"
                onClick={() => loadFiles(false)}
                disabled={isLoadingMore}
                className="gap-2"
              >
                {isLoadingMore ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading...
                  </>
                ) : (
                  'Load More'
                )}
              </Button>
            </div>
          )}
        </>
      )}

      {/* Image Preview Modal */}
      {previewFile && previewFile.mime_type.startsWith('image/') && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="relative max-w-4xl max-h-[90vh]">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setPreviewFile(null)}
              className="absolute top-4 right-4 z-10 bg-black/50 hover:bg-black/70 text-white"
            >
              <X className="w-5 h-5" />
            </Button>
            <img
              src={previewFile.download_url}
              alt={previewFile.name}
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
            />
            <div className="absolute bottom-4 left-4 right-4 bg-black/50 text-white p-3 rounded-lg">
              <p className="font-medium">{previewFile.name}</p>
              <p className="text-sm opacity-80">{formatFileSize(previewFile.size_bytes)}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
