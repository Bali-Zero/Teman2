'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Download,
  Share2,
  Trash2,
  MoreVertical,
  Eye,
  Clock,
  User,
  FileText,
  Folder,
  HardDrive,
  Calendar,
  Link2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { FileItem } from '@/lib/api/drive/drive.types';
import { getFileIcon } from './file-icon';

interface DriveInfoPanelProps {
  file: FileItem | null;
  isOpen: boolean;
  onClose: () => void;
  onPreview?: (file: FileItem) => void;
  onDownload?: (file: FileItem) => void;
  onDelete?: (file: FileItem) => void;
}

export function DriveInfoPanel({
  file,
  isOpen,
  onClose,
  onPreview,
  onDownload,
  onDelete,
}: DriveInfoPanelProps) {
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
    const date = new Date(dateStr);
    return date.toLocaleDateString('it-IT', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <AnimatePresence>
      {isOpen && file && (
        <motion.div
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 320, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="flex h-full flex-col border-l border-[#dadce0] bg-white dark:bg-[var(--background)]"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[#dadce0] px-4 py-3">
            <h3 className="font-medium text-[#202124] dark:text-[var(--foreground)] truncate max-w-[200px]">
              {file.name}
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-8 w-8 p-0 rounded-full hover:bg-[#f5f5f5]"
            >
              <X className="h-4 w-4 text-[#5f6368]" />
            </Button>
          </div>

          {/* Preview area */}
          <div className="flex items-center justify-center bg-[#f8f9fa] dark:bg-[var(--background-subtle)] p-8">
            <div className="w-24 h-24">{getFileIcon(file, 'lg')}</div>
          </div>

          {/* Quick actions */}
          <div className="flex items-center justify-center gap-2 border-b border-[#dadce0] py-3">
            {!file.is_folder && onPreview && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onPreview(file)}
                className="h-10 w-10 p-0 rounded-full hover:bg-[#f5f5f5]"
                title="Anteprima"
              >
                <Eye className="h-5 w-5 text-[#5f6368]" />
              </Button>
            )}
            {!file.is_folder && onDownload && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDownload(file)}
                className="h-10 w-10 p-0 rounded-full hover:bg-[#f5f5f5]"
                title="Scarica"
              >
                <Download className="h-5 w-5 text-[#5f6368]" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-10 w-10 p-0 rounded-full hover:bg-[#f5f5f5]"
              title="Condividi"
              disabled
            >
              <Share2 className="h-5 w-5 text-[#9aa0a6]" />
            </Button>
            {onDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete(file)}
                className="h-10 w-10 p-0 rounded-full hover:bg-[#fce8e6]"
                title="Elimina"
              >
                <Trash2 className="h-5 w-5 text-[#ea4335]" />
              </Button>
            )}
          </div>

          {/* Details */}
          <div className="flex-1 overflow-auto p-4 space-y-4">
            <h4 className="text-xs font-medium text-[#5f6368] uppercase tracking-wider">
              Dettagli
            </h4>

            {/* Type */}
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f1f3f4]">
                {file.is_folder ? (
                  <Folder className="h-4 w-4 text-[#5f6368]" />
                ) : (
                  <FileText className="h-4 w-4 text-[#5f6368]" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-[#5f6368]">Tipo</p>
                <p className="text-sm text-[#202124] dark:text-[var(--foreground)]">
                  {file.is_folder ? 'Cartella' : file.mime_type?.split('/').pop() || 'Documento'}
                </p>
              </div>
            </div>

            {/* Size */}
            {!file.is_folder && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f1f3f4]">
                  <HardDrive className="h-4 w-4 text-[#5f6368]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-[#5f6368]">Dimensione</p>
                  <p className="text-sm text-[#202124] dark:text-[var(--foreground)]">
                    {formatSize(file.size)}
                  </p>
                </div>
              </div>
            )}

            {/* Modified */}
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f1f3f4]">
                <Clock className="h-4 w-4 text-[#5f6368]" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-[#5f6368]">Modificato</p>
                <p className="text-sm text-[#202124] dark:text-[var(--foreground)]">
                  {formatDate(file.modified_time)}
                </p>
              </div>
            </div>

            {/* Created */}
            {(file as any).created_time && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f1f3f4]">
                  <Calendar className="h-4 w-4 text-[#5f6368]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-[#5f6368]">Creato</p>
                  <p className="text-sm text-[#202124] dark:text-[var(--foreground)]">
                    {formatDate((file as any).created_time)}
                  </p>
                </div>
              </div>
            )}

            {/* Owner */}
            {(file as any).owner_name && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f1f3f4]">
                  <User className="h-4 w-4 text-[#5f6368]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-[#5f6368]">Proprietario</p>
                  <p className="text-sm text-[#202124] dark:text-[var(--foreground)]">
                    {(file as any).owner_name}
                  </p>
                </div>
              </div>
            )}

            {/* Link */}
            {file.web_view_link && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f1f3f4]">
                  <Link2 className="h-4 w-4 text-[#5f6368]" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-[#5f6368]">Link</p>
                  <a
                    href={file.web_view_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-[#1a73e8] hover:underline truncate block"
                  >
                    Apri in Google Drive
                  </a>
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
