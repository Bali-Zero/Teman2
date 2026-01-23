import { useQuery, useMutation, useQueryClient, QueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { api } from '@/lib/api';
import { driveLogger } from '@/lib/logging/drive-logger';
import type {
  FileItem,
  CreateFolderRequest,
  DocType,
  FileListResponse,
  BreadcrumbItem,
} from '@/lib/api/drive/drive.types';

/** Type for drive file list query data */
interface DriveFilesData {
  files: FileItem[];
  breadcrumb: BreadcrumbItem[];
}

export function useDriveFiles(folderId: string | null, searchQuery: string = '') {
  return useQuery({
    queryKey: ['drive', 'files', folderId, searchQuery],
    queryFn: async () => {
      if (searchQuery) {
        const results = await api.drive.searchFiles(searchQuery);
        return { files: results, breadcrumb: [] };
      }
      return api.drive.listFiles({ folder_id: folderId || undefined });
    },
    placeholderData: (previousData) => previousData, // Keep previous data while fetching new folder
    staleTime: 1000 * 60, // 1 minute cache
  });
}

/** Prefetch folder contents on hover for instant navigation */
export function usePrefetchFolder() {
  const queryClient = useQueryClient();

  const prefetchFolder = useCallback(
    (folderId: string) => {
      // Only prefetch if not already in cache
      const cached = queryClient.getQueryData(['drive', 'files', folderId, '']);
      if (cached) {
        driveLogger.logPrefetchSkipped(folderId, 'cached');
        return;
      }

      driveLogger.logPrefetchStarted(folderId);
      const startTime = performance.now();

      queryClient.prefetchQuery({
        queryKey: ['drive', 'files', folderId, ''],
        queryFn: async () => {
          try {
            const result = await api.drive.listFiles({ folder_id: folderId });
            const duration = Math.round(performance.now() - startTime);
            driveLogger.logPrefetchCompleted(folderId, duration, result.files.length);
            return result;
          } catch (error) {
            driveLogger.logPrefetchError(
              folderId,
              error instanceof Error ? error : new Error(String(error))
            );
            throw error;
          }
        },
        staleTime: 1000 * 60, // 1 minute
      });
    },
    [queryClient]
  );

  return { prefetchFolder };
}

export function useDriveStatus() {
  return useQuery({
    queryKey: ['drive', 'status'],
    queryFn: () => api.drive.getStatus(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

export function useDriveMutations() {
  const queryClient = useQueryClient();

  const invalidateFiles = () => {
    queryClient.invalidateQueries({ queryKey: ['drive', 'files'] });
  };

  const createFolder = useMutation({
    mutationFn: (variable: { name: string; parentId: string | null }) =>
      api.drive.createFolder({ name: variable.name, parent_id: variable.parentId || 'root' }),
    onSuccess: invalidateFiles,
  });

  const createDoc = useMutation({
    mutationFn: (variable: { name: string; parentId: string | null; docType: DocType }) =>
      api.drive.createDoc({
        name: variable.name,
        parent_id: variable.parentId || 'root',
        doc_type: variable.docType,
      }),
    onSuccess: invalidateFiles,
  });

  const deleteFile = useMutation({
    mutationFn: (fileId: string) => api.drive.deleteFile(fileId),
    onMutate: async (fileId) => {
      // Optimistic update: Remove file from list immediately
      await queryClient.cancelQueries({ queryKey: ['drive', 'files'] });
      const previousData = queryClient.getQueriesData({ queryKey: ['drive', 'files'] });

      queryClient.setQueriesData<DriveFilesData>({ queryKey: ['drive', 'files'] }, (old) => {
        if (!old) return old;
        return {
          ...old,
          files: old.files.filter((f) => f.id !== fileId),
        };
      });

      return { previousData };
    },
    onError: (err, fileId, context) => {
      // Rollback on error
      if (context?.previousData) {
        context.previousData.forEach(([key, data]) => {
          queryClient.setQueryData(key, data);
        });
      }
    },
    onSettled: invalidateFiles,
  });

  const renameFile = useMutation({
    mutationFn: (variable: { fileId: string; newName: string }) =>
      api.drive.renameFile(variable.fileId, variable.newName),
    onSuccess: invalidateFiles,
  });

  const moveFiles = useMutation({
    mutationFn: (variable: { fileIds: string[]; targetFolderId: string }) =>
      api.drive.moveFiles(
        variable.fileIds,
        variable.targetFolderId === 'root' ? '' : variable.targetFolderId
      ),
    onSuccess: invalidateFiles,
  });

  return {
    createFolder,
    createDoc,
    deleteFile,
    renameFile,
    moveFiles,
  };
}
