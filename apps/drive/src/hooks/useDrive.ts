import {
  useQuery,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  QueryClient,
} from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { driveLogger } from "@/lib/logging/drive-logger";
// Note: api.drive maps to driveApi from @/lib/api.ts
import type {
  FileItem,
  CreateFolderRequest,
  DocType,
  FileListResponse,
  BreadcrumbItem,
} from "@/lib/api/drive/drive.types";

/** Type for drive file list query data */
interface DriveFilesData {
  files: FileItem[];
  breadcrumb: BreadcrumbItem[];
}

/** Default page size for file listing */
const DEFAULT_PAGE_SIZE = 50;

/**
 * Hook for fetching drive files with infinite scroll pagination
 * Supports automatic loading of more files when scrolling
 */
export function useDriveFiles(
  folderId: string | null,
  searchQuery: string = "",
) {
  const infiniteQuery = useInfiniteQuery({
    queryKey: ["drive", "files", folderId, searchQuery],
    queryFn: async ({ pageParam }) => {
      if (searchQuery) {
        // Search doesn't support pagination yet
        const results = await api.drive.searchFiles(searchQuery);
        return { files: results, breadcrumb: [], next_page_token: null };
      }
      return api.drive.listFiles({
        folder_id: folderId || undefined,
        page_token: pageParam,
        page_size: DEFAULT_PAGE_SIZE,
      });
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage?.next_page_token || undefined,
    staleTime: 1000 * 60, // 1 minute cache
  });

  // Flatten all pages into a single files array
  const data = useMemo(() => {
    if (!infiniteQuery.data?.pages) return undefined;

    const allFiles: FileItem[] = [];
    let breadcrumb: BreadcrumbItem[] = [];

    infiniteQuery.data.pages.forEach((page, index) => {
      // Safety check: ensure page and page.files exist
      if (page?.files) {
        allFiles.push(...page.files);
      }
      // Use breadcrumb from first page
      if (index === 0 && page?.breadcrumb) {
        breadcrumb = page.breadcrumb;
      }
    });

    return { files: allFiles, breadcrumb };
  }, [infiniteQuery.data]);

  return {
    data,
    isLoading: infiniteQuery.isLoading,
    error: infiniteQuery.error,
    // Infinite scroll helpers (with safe defaults)
    hasNextPage: infiniteQuery.hasNextPage ?? false,
    isFetchingNextPage: infiniteQuery.isFetchingNextPage ?? false,
    fetchNextPage: infiniteQuery.fetchNextPage,
  };
}

/** Prefetch folder contents on hover for instant navigation */
export function usePrefetchFolder() {
  const queryClient = useQueryClient();

  const prefetchFolder = useCallback(
    (folderId: string) => {
      // Only prefetch if not already in cache
      const cached = queryClient.getQueryData(["drive", "files", folderId, ""]);
      if (cached) {
        driveLogger.logPrefetchSkipped(folderId, "cached");
        return;
      }

      driveLogger.logPrefetchStarted(folderId);
      const startTime = performance.now();

      // Prefetch as infinite query to match main query structure
      queryClient.prefetchInfiniteQuery({
        queryKey: ["drive", "files", folderId, ""],
        queryFn: async () => {
          try {
            const result = await api.drive.listFiles({
              folder_id: folderId,
              page_size: DEFAULT_PAGE_SIZE,
            });
            const duration = Math.round(performance.now() - startTime);
            driveLogger.logPrefetchCompleted(
              folderId,
              duration,
              result.files.length,
            );
            return result;
          } catch (error) {
            driveLogger.logPrefetchError(
              folderId,
              error instanceof Error ? error : new Error(String(error)),
            );
            throw error;
          }
        },
        initialPageParam: undefined,
        staleTime: 1000 * 60, // 1 minute
      });
    },
    [queryClient],
  );

  return { prefetchFolder };
}

export function useDriveStatus() {
  return useQuery({
    queryKey: ["drive", "status"],
    queryFn: () => api.drive.getStatus(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

export function useDriveMutations() {
  const queryClient = useQueryClient();

  const invalidateFiles = () => {
    queryClient.invalidateQueries({ queryKey: ["drive", "files"] });
  };

  const createFolder = useMutation({
    mutationFn: (variable: { name: string; parentId: string | null }) =>
      api.drive.createFolder({
        name: variable.name,
        parent_id: variable.parentId || "root",
      }),
    onSuccess: invalidateFiles,
  });

  const createDoc = useMutation({
    mutationFn: (variable: {
      name: string;
      parentId: string | null;
      docType: DocType;
    }) =>
      api.drive.createDoc({
        name: variable.name,
        parent_id: variable.parentId || "root",
        doc_type: variable.docType,
      }),
    onSuccess: invalidateFiles,
  });

  const deleteFile = useMutation({
    mutationFn: (fileId: string) => api.drive.deleteFile(fileId),
    onMutate: async (fileId) => {
      // Optimistic update: Remove file from list immediately
      await queryClient.cancelQueries({ queryKey: ["drive", "files"] });
      const previousData = queryClient.getQueriesData({
        queryKey: ["drive", "files"],
      });

      // Update infinite query data structure (pages array)
      queryClient.setQueriesData<{
        pages: FileListResponse[];
        pageParams: unknown[];
      }>({ queryKey: ["drive", "files"] }, (old) => {
        if (!old?.pages) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            files: page.files?.filter((f) => f.id !== fileId) || [],
          })),
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
        variable.targetFolderId === "root" ? "" : variable.targetFolderId,
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
