import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { DriveFilesResponse } from "@/lib/api/portal/portal.types";

export function usePortalDriveFiles() {
  return useQuery<DriveFilesResponse>({
    queryKey: ["portal", "drive-files"],
    queryFn: () => api.portal.getDriveFiles(),
    staleTime: 120_000,
  });
}

export function usePortalDriveSubfolder(folderId: string | null) {
  return useQuery<DriveFilesResponse>({
    queryKey: ["portal", "drive-files", folderId],
    queryFn: () => api.portal.getDriveSubfolderFiles(folderId!),
    enabled: !!folderId,
    staleTime: 120_000,
  });
}
