'use client';

import React, { useState, useEffect } from 'react';
import {
  FolderOpen,
  Folder,
  File,
  Eye,
  Download,
  Plus,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Link as LinkIcon,
  X,
  Upload,
  RefreshCw,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';

interface FolderInfo {
  id: string;
  url: string;
  name: string;
  file_count?: number;
  total_size_bytes?: number;
}

interface DriveFolderStructureProps {
  clientId: number;
  clientName: string;
  existingFolderId?: string | null;
  onFolderCreated?: (folderId: string) => void;
  onFolderLinked?: (folderId: string) => void;
  onViewFolder?: (folderName: string) => void;
}

const STANDARD_FOLDERS = [
  { name: '00_Profile', label: 'Profile', icon: '👤', color: 'bg-blue-500/20 text-blue-400' },
  {
    name: '01_Immigration',
    label: 'Immigration',
    icon: '🛂',
    color: 'bg-green-500/20 text-green-400',
  },
  { name: '02_Company', label: 'Company', icon: '🏢', color: 'bg-purple-500/20 text-purple-400' },
  { name: '03_Tax', label: 'Tax', icon: '💰', color: 'bg-yellow-500/20 text-yellow-400' },
  { name: '04_Family', label: 'Family', icon: '👨‍👩‍👧‍👦', color: 'bg-pink-500/20 text-pink-400' },
  { name: '99_Misc', label: 'Misc', icon: '📁', color: 'bg-gray-500/20 text-gray-400' },
];

export function DriveFolderStructure({
  clientId,
  clientName,
  existingFolderId,
  onFolderCreated,
  onFolderLinked,
  onViewFolder,
}: DriveFolderStructureProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [folderInfo, setFolderInfo] = useState<{
    root_folder_id: string;
    root_folder_url: string;
    folders: Record<string, FolderInfo>;
  } | null>(null);
  const [stats, setStats] = useState<{
    total_files: number;
    total_size_mb: number;
    last_synced: string;
  } | null>(null);
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [linkFolderId, setLinkFolderId] = useState('');

  // Check existing folder on mount
  useEffect(() => {
    if (existingFolderId) {
      checkFolderStatus();
    }
  }, [existingFolderId]);

  const checkFolderStatus = async () => {
    setIsChecking(true);
    try {
      const data = await api.crm.getDriveFolder(clientId);

      if (data.exists && data.folder_id) {
        // Fetch folder structure with file counts
        const structure = await api.crm.getDriveFolderStructure(clientId);

        // Transform structure to match component state
        const foldersMap: Record<string, FolderInfo> = {};
        structure.folders.forEach((folder: any) => {
          foldersMap[folder.name] = {
            id: folder.id,
            url: '', // Not used - no external links
            name: folder.name,
            file_count: folder.file_count,
            total_size_bytes: folder.total_size_bytes,
          };
        });

        setFolderInfo({
          root_folder_id: structure.root_folder_id,
          root_folder_url: '', // Not used - no external links
          folders: foldersMap,
        });

        // Also fetch stats
        try {
          const statsData = await api.crm.getDriveFolderStats(clientId);
          setStats({
            total_files: statsData.total_files,
            total_size_mb: statsData.total_size_mb,
            last_synced: statsData.last_synced,
          });
        } catch (error) {
          logger.error('Failed to load stats:', {}, error as Error);
        }
      }
    } catch (error) {
      logger.error('Failed to check folder status:', {}, error as Error);
    } finally {
      setIsChecking(false);
    }
  };

  const handleCreateFolder = async () => {
    setIsLoading(true);
    try {
      const data = await api.crm.createDriveFolder(clientId);

      // Map the response to ensure it matches FolderInfo
      const foldersMap: Record<string, FolderInfo> = {};
      if (data.folders) {
        Object.entries(data.folders).forEach(([name, info]: [string, any]) => {
          foldersMap[name] = {
            id: info.id,
            url: info.url,
            name: name,
            file_count: 0,
            total_size_bytes: 0,
          };
        });
      }

      setFolderInfo({
        root_folder_id: data.root_folder_id,
        root_folder_url: data.root_folder_url,
        folders: foldersMap,
      });

      toast.success('Folder structure created successfully');
      onFolderCreated?.(data.root_folder_id);
    } catch (error: any) {
      toast.error(error.message || 'Failed to create folder structure');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLinkFolder = async () => {
    if (!linkFolderId.trim()) {
      toast.error('Please enter a folder ID');
      return;
    }

    setIsLoading(true);
    try {
      // Extract folder ID from URL if full URL provided
      const folderId = linkFolderId.includes('folders/')
        ? linkFolderId.split('folders/')[1].split('/')[0].split('?')[0]
        : linkFolderId.trim();

      // Update client with folder ID
      const user = api.getUserProfile();
      await api.crm.updateClient(
        clientId,
        {
          google_drive_folder_id: folderId,
        },
        user?.email || 'system'
      );

      setFolderInfo({
        root_folder_id: folderId,
        root_folder_url: `https://drive.google.com/drive/folders/${folderId}`,
        folders: {},
      });

      toast.success('Folder linked successfully');
      setShowLinkModal(false);
      setLinkFolderId('');
      onFolderLinked?.(folderId);
    } catch (error: any) {
      toast.error(error.message || 'Failed to link folder');
    } finally {
      setIsLoading(false);
    }
  };

  const viewFolderFiles = (folderName: string) => {
    if (onViewFolder) {
      onViewFolder(folderName);
    }
  };

  if (isChecking) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-5 h-5 animate-spin text-[var(--foreground-muted)]" />
        <span className="ml-2 text-sm text-[var(--foreground-muted)]">
          Checking folder status...
        </span>
      </div>
    );
  }

  // No folder exists
  if (!folderInfo && !existingFolderId) {
    return (
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-[var(--foreground)] mb-1">
              Google Drive Folder
            </h3>
            <p className="text-sm text-[var(--foreground-muted)]">
              Create a standardized folder structure for this client
            </p>
          </div>
        </div>

        <div className="mb-4 p-4 rounded-lg bg-[var(--background)] border border-[var(--border)]">
          <p className="text-sm font-medium text-[var(--foreground)] mb-2">Standard Structure:</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {STANDARD_FOLDERS.map((folder) => (
              <div
                key={folder.name}
                className="flex items-center gap-2 text-xs text-[var(--foreground-muted)]"
              >
                <span>{folder.icon}</span>
                <span>{folder.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex gap-2">
          <Button onClick={handleCreateFolder} disabled={isLoading} className="gap-2">
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Plus className="w-4 h-4" />
                Create Folder Structure
              </>
            )}
          </Button>
          <Button variant="outline" onClick={() => setShowLinkModal(true)} className="gap-2">
            <LinkIcon className="w-4 h-4" />
            Link Existing Folder
          </Button>
        </div>

        {/* Link Modal */}
        {showLinkModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-[var(--background)] rounded-lg border border-[var(--border)] p-6 max-w-md w-full mx-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-[var(--foreground)]">
                  Link Existing Folder
                </h3>
                <button
                  onClick={() => {
                    setShowLinkModal(false);
                    setLinkFolderId('');
                  }}
                  className="text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <p className="text-sm text-[var(--foreground-muted)] mb-4">
                Enter the Google Drive folder ID or URL to link to this client.
              </p>
              <input
                type="text"
                value={linkFolderId}
                onChange={(e) => setLinkFolderId(e.target.value)}
                placeholder="1ABC...XYZ or https://drive.google.com/drive/folders/1ABC..."
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] mb-4"
              />
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowLinkModal(false);
                    setLinkFolderId('');
                  }}
                >
                  Cancel
                </Button>
                <Button onClick={handleLinkFolder} disabled={isLoading}>
                  {isLoading ? 'Linking...' : 'Link Folder'}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // Folder exists - show structure
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-6">
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <CheckCircle2 className="w-5 h-5 text-green-500" />
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Google Drive Folder</h3>
          </div>
          {stats && (
            <p className="text-sm text-[var(--foreground-muted)]">
              {stats.total_files} files • {stats.total_size_mb.toFixed(1)} MB • Last sync:{' '}
              {new Date(stats.last_synced).toLocaleTimeString()}
            </p>
          )}
          {!stats && (
            <p className="text-sm text-[var(--foreground-muted)]">
              Folder linked • Files accessible from workspace
            </p>
          )}
        </div>
      </div>

      {/* Folder Structure */}
      <div className="space-y-2">
        {STANDARD_FOLDERS.map((folder) => {
          const folderData = folderInfo?.folders[folder.name];
          const fileCount = folderData?.file_count ?? 0;
          const sizeMB = folderData?.total_size_bytes
            ? (folderData.total_size_bytes / 1024 / 1024).toFixed(1)
            : '0';

          return (
            <div
              key={folder.name}
              className="flex items-center justify-between p-3 rounded-lg border border-[var(--border)] bg-[var(--background)] hover:bg-[var(--background-elevated)] transition-colors"
            >
              <div className="flex items-center gap-3 flex-1">
                <div className={`p-2 rounded-lg ${folder.color}`}>
                  <span className="text-lg">{folder.icon}</span>
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Folder className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <span className="font-medium text-[var(--foreground)]">{folder.label}</span>
                    <span className="text-xs text-[var(--foreground-muted)]">({folder.name})</span>
                  </div>
                  {fileCount > 0 && (
                    <div className="text-xs text-[var(--foreground-muted)] mt-1">
                      {fileCount} file{fileCount !== 1 ? 's' : ''} • {sizeMB} MB
                    </div>
                  )}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => viewFolderFiles(folder.name)}
                className="gap-1"
                title="View files in workspace"
                disabled={!folderData}
              >
                <Eye className="w-3 h-3" />
              </Button>
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-4 border-t border-[var(--border)] flex gap-2">
        <Button variant="outline" size="sm" onClick={checkFolderStatus} className="gap-2">
          <RefreshCw className="w-4 h-4" />
          Refresh
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            // Open upload modal (will be implemented)
            toast.info('Upload feature coming soon');
          }}
          className="gap-2"
        >
          <Upload className="w-4 h-4" />
          Upload Files
        </Button>
      </div>
    </div>
  );
}
