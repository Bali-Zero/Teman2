/**
 * useDriveOptimized Hooks
 * 
 * Versione ultra-ottimizzata dei Drive hooks con:
 * - React Query con caching aggressivo
 * - Prefetching intelligente
 * - Upload con deduplicazione
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  useQuery,
  useMutation,
  useQueryClient,
  useInfiniteQuery,
} from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { FileItem, ConnectionStatus, FileListResponse } from '@/lib/api/drive/drive.types';
import { useDebounce } from '@/lib/hooks/optimized/useDebounce';

// ============================================================================
// CONSTANTS
// ============================================================================

const STALE_TIME = {
  files: 30 * 1000,
  status: 60 * 1000,
  search: 10 * 1000,
};

const CACHE_TIME = {
  files: 5 * 60 * 1000,
  status: 10 * 60 * 1000,
};

const PAGE_SIZE = 100;

// ============================================================================
// DRIVE STATUS
// ============================================================================

export function useDriveStatus() {
  return useQuery({
    queryKey: ['drive', 'status'],
    queryFn: async (): Promise<ConnectionStatus> => {
      return api.drive.getStatus();
    },
    staleTime: STALE_TIME.status,
    gcTime: CACHE_TIME.status,
    refetchInterval: 5 * 60 * 1000,
  });
}

// ============================================================================
// DRIVE FILES - Infinite Scroll
// ============================================================================

interface DriveFilesPage {
  files: FileItem[];
  nextPageToken: string | null;
  breadcrumb: { id: string; name: string }[];
}

export function useDriveFilesInfinite(
  folderId: string | null,
  searchQuery: string = '',
  enabled: boolean = true
) {
  const debouncedSearch = useDebounce(searchQuery, 300);
  
  return useInfiniteQuery({
    queryKey: ['drive', 'files', folderId || 'root', debouncedSearch || 'all'],
    queryFn: async ({ pageParam }): Promise<DriveFilesPage> => {
      const result = await api.drive.listFiles({
        folder_id: folderId || undefined,
        page_token: pageParam || undefined,
        page_size: PAGE_SIZE,
      });
      
      return {
        files: result.files,
        nextPageToken: result.next_page_token,
        breadcrumb: result.breadcrumb,
      };
    },
    getNextPageParam: (lastPage) => lastPage.nextPageToken || undefined,
    initialPageParam: undefined as string | undefined,
    enabled,
    staleTime: debouncedSearch ? STALE_TIME.search : STALE_TIME.files,
    gcTime: CACHE_TIME.files,
  });
}

// ============================================================================
// DRIVE FILES - Single Load
// ============================================================================

export function useDriveFiles(
  folderId: string | null,
  searchQuery: string = '',
  enabled: boolean = true
) {
  const debouncedSearch = useDebounce(searchQuery, 300);
  
  return useQuery({
    queryKey: ['drive', 'files', 'single', folderId || 'root', debouncedSearch || 'all'],
    queryFn: async (): Promise<FileListResponse> => {
      return api.drive.listFiles({ 
        folder_id: folderId || undefined, 
        page_size: 1000 
      });
    },
    enabled,
    staleTime: debouncedSearch ? STALE_TIME.search : STALE_TIME.files,
    gcTime: CACHE_TIME.files,
  });
}

// ============================================================================
// FILE METADATA
// ============================================================================

export function useFileMetadata(fileId: string | null) {
  return useQuery({
    queryKey: ['drive', 'file', fileId, 'metadata'],
    queryFn: async (): Promise<FileItem | null> => {
      if (!fileId) return null;
      return api.drive.getFile(fileId);
    },
    enabled: !!fileId,
    staleTime: 60 * 1000,
  });
}

// ============================================================================
// FOLDER PREFETCHING
// ============================================================================

export function usePrefetchFolder() {
  const queryClient = useQueryClient();
  const prefetchTimeout = useRef<NodeJS.Timeout | null>(null);

  const prefetchFolder = useCallback((folderId: string) => {
    if (prefetchTimeout.current) {
      clearTimeout(prefetchTimeout.current);
    }

    prefetchTimeout.current = setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: ['drive', 'files', 'single', folderId, 'all'],
        queryFn: async () => api.drive.listFiles({ folder_id: folderId, page_size: 100 }),
        staleTime: STALE_TIME.files,
      });
    }, 300);
  }, [queryClient]);

  const cancelPrefetch = useCallback(() => {
    if (prefetchTimeout.current) {
      clearTimeout(prefetchTimeout.current);
    }
  }, []);

  useEffect(() => {
    return () => {
      if (prefetchTimeout.current) {
        clearTimeout(prefetchTimeout.current);
      }
    };
  }, []);

  return { prefetchFolder, cancelPrefetch };
}

// ============================================================================
// UPLOAD WITH DEDUPLICATION
// ============================================================================

interface UploadState {
  id: string;
  fileName: string;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

export function useDriveUpload() {
  const queryClient = useQueryClient();
  const [uploads, setUploads] = useState<Map<string, UploadState>>(new Map());

  const uploadFile = useCallback(async (
    file: File,
    parentId: string,
    onProgress?: (progress: { loaded: number; total: number; percentage: number }) => void
  ) => {
    const uploadId = `${parentId}-${file.name}-${file.size}`;
    
    if (uploads.has(uploadId)) {
      console.warn(`Upload already in progress: ${file.name}`);
      return uploads.get(uploadId)!;
    }

    setUploads(prev => new Map(prev.set(uploadId, {
      id: uploadId,
      fileName: file.name,
      progress: 0,
      status: 'uploading',
    })));

    try {
      const result = await api.drive.uploadFile(
        file,
        parentId,
        (progress) => {
          setUploads(prev => {
            const next = new Map(prev);
            const upload = next.get(uploadId);
            if (upload) {
              upload.progress = progress.percentage;
            }
            return next;
          });
          onProgress?.(progress);
        }
      );

      setUploads(prev => {
        const next = new Map(prev);
        const upload = next.get(uploadId);
        if (upload) {
          upload.status = 'completed';
          upload.progress = 100;
        }
        return next;
      });

      queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });

      setTimeout(() => {
        setUploads(prev => {
          const next = new Map(prev);
          next.delete(uploadId);
          return next;
        });
      }, 3000);

      return result;
    } catch (error) {
      setUploads(prev => {
        const next = new Map(prev);
        const upload = next.get(uploadId);
        if (upload) {
          upload.status = 'error';
          upload.error = error instanceof Error ? error.message : 'Upload failed';
        }
        return next;
      });
      throw error;
    }
  }, [uploads, queryClient]);

  const uploadMultiple = useCallback(async (
    files: File[],
    parentId: string | null,
    options?: { 
      onFileComplete?: (file: File, result: any) => void;
      onFileError?: (file: File, error: Error) => void;
      parallel?: number;
    }
  ) => {
    const { parallel = 3 } = options || {};
    const results: Array<{ file: File; success: boolean; result?: any; error?: Error }> = [];
    
    for (let i = 0; i < files.length; i += parallel) {
      const batch = files.slice(i, i + parallel);
      const batchResults = await Promise.allSettled(
        batch.map(async (file) => {
          try {
            const result = await uploadFile(file, parentId || 'root');
            options?.onFileComplete?.(file, result);
            return { file, success: true, result };
          } catch (error) {
            const err = error instanceof Error ? error : new Error(String(error));
            options?.onFileError?.(file, err);
            return { file, success: false, error: err };
          }
        })
      );
      
      results.push(...batchResults.map((r, idx) => 
        r.status === 'fulfilled' 
          ? r.value 
          : { file: batch[idx], success: false, error: new Error(String(r.reason)) }
      ));
    }

    return results;
  }, [uploadFile]);

  const clearCompleted = useCallback(() => {
    setUploads(prev => {
      const next = new Map();
      prev.forEach((upload, id) => {
        if (upload.status !== 'completed') {
          next.set(id, upload);
        }
      });
      return next;
    });
  }, []);

  return {
    uploads: Array.from(uploads.values()),
    uploadFile,
    uploadMultiple,
    clearCompleted,
  };
}

// ============================================================================
// FILE OPERATIONS
// ============================================================================

export function useDriveMutationsOptimized() {
  const queryClient = useQueryClient();

  const createFolder = useMutation({
    mutationFn: async ({ name, parentId }: { name: string; parentId: string | null }) => {
      return api.drive.createFolder({ name, parent_id: parentId || 'root' });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });
    },
  });

  const renameFile = useMutation({
    mutationFn: async ({ fileId, newName }: { fileId: string; newName: string }) => {
      return api.drive.renameFile(fileId, newName);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });
    },
  });

  const deleteFile = useMutation({
    mutationFn: async (fileId: string) => {
      return api.drive.deleteFile(fileId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });
    },
  });

  const moveFiles = useMutation({
    mutationFn: async ({ fileIds, targetFolderId }: { fileIds: string[]; targetFolderId: string }) => {
      return api.drive.moveFiles(fileIds, targetFolderId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });
    },
  });

  const copyFile = useMutation({
    mutationFn: async ({ fileId, parentId }: { fileId: string; parentId: string }) => {
      return api.drive.copyFile(fileId, undefined, parentId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });
    },
  });

  return {
    createFolder,
    renameFile,
    deleteFile,
    moveFiles,
    copyFile,
  };
}

// ============================================================================
// SEARCH
// ============================================================================

export function useDriveSearch(query: string, enabled: boolean = true) {
  const debouncedQuery = useDebounce(query, 300);
  
  return useQuery({
    queryKey: ['drive', 'search', debouncedQuery],
    queryFn: async (): Promise<FileItem[]> => {
      if (debouncedQuery.length < 2) return [];
      return api.drive.searchFiles(debouncedQuery, 50);
    },
    enabled: enabled && debouncedQuery.length >= 2,
    staleTime: STALE_TIME.search,
  });
}
