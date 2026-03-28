'use client';

import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Download,
  Share2,
  Trash2,
  Eye,
  Clock,
  User,
  FileText,
  Folder,
  HardDrive,
  Calendar,
  ExternalLink,
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
      month: 'short',
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
          animate={{ width: 300, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="flex h-full flex-col border-l border-slate-200/60 dark:border-slate-700/40 bg-slate-50/50 dark:bg-slate-900/30"
        >
          {/* Header - Elegant minimal */}
          <div className="flex items-center justify-between border-b border-slate-200/60 dark:border-slate-700/40 px-4 py-3">
            <h3 className="text-[13px] font-semibold text-slate-700 dark:text-slate-200 truncate max-w-[200px]">
              {file.name}
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="h-7 w-7 p-0 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Chiudi pannello dettagli"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Preview area - Clean */}
          <div className="flex items-center justify-center bg-white/60 dark:bg-slate-800/30 p-8">
            <div className="w-20 h-20">{getFileIcon(file, 'lg')}</div>
          </div>

          {/* Quick actions - Minimal pill style */}
          <div className="flex items-center justify-center gap-1.5 border-b border-slate-200/60 dark:border-slate-700/40 py-3 px-4">
            {!file.is_folder && onPreview && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onPreview(file)}
                className="h-9 w-9 p-0 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                title="Anteprima"
              >
                <Eye className="h-4 w-4" />
              </Button>
            )}
            {!file.is_folder && onDownload && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDownload(file)}
                className="h-9 w-9 p-0 rounded-lg text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800"
                title="Scarica"
              >
                <Download className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-9 w-9 p-0 rounded-lg text-slate-300 dark:text-slate-600 cursor-not-allowed"
              title="Condividi"
              disabled
            >
              <Share2 className="h-4 w-4" />
            </Button>
            {onDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete(file)}
                className="h-9 w-9 p-0 rounded-lg text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30"
                title="Elimina"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>

          {/* Details - Elegant card style */}
          <div className="flex-1 overflow-auto p-4 space-y-3">
            <h4 className="text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider mb-3">
              Dettagli
            </h4>

            {/* Type */}
            <div className="flex items-center gap-3 p-2.5 rounded-lg bg-white/60 dark:bg-slate-800/30">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/80 dark:bg-slate-700/50">
                {file.is_folder ? (
                  <Folder className="h-4 w-4 text-slate-500" />
                ) : (
                  <FileText className="h-4 w-4 text-slate-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[10px] text-slate-400 uppercase tracking-wide">Tipo</p>
                <p className="text-[13px] text-slate-700 dark:text-slate-200">
                  {file.is_folder ? 'Cartella' : file.mime_type?.split('/').pop() || 'Documento'}
                </p>
              </div>
            </div>

            {/* Size */}
            {!file.is_folder && (
              <div className="flex items-center gap-3 p-2.5 rounded-lg bg-white/60 dark:bg-slate-800/30">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/80 dark:bg-slate-700/50">
                  <HardDrive className="h-4 w-4 text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wide">Dimensione</p>
                  <p className="text-[13px] text-slate-700 dark:text-slate-200">
                    {formatSize(file.size)}
                  </p>
                </div>
              </div>
            )}

            {/* Modified */}
            <div className="flex items-center gap-3 p-2.5 rounded-lg bg-white/60 dark:bg-slate-800/30">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/80 dark:bg-slate-700/50">
                <Clock className="h-4 w-4 text-slate-500" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[10px] text-slate-400 uppercase tracking-wide">Modificato</p>
                <p className="text-[13px] text-slate-700 dark:text-slate-200">
                  {formatDate(file.modified_time)}
                </p>
              </div>
            </div>

            {/* Created */}
            {(file as any).created_time && (
              <div className="flex items-center gap-3 p-2.5 rounded-lg bg-white/60 dark:bg-slate-800/30">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/80 dark:bg-slate-700/50">
                  <Calendar className="h-4 w-4 text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wide">Creato</p>
                  <p className="text-[13px] text-slate-700 dark:text-slate-200">
                    {formatDate((file as any).created_time)}
                  </p>
                </div>
              </div>
            )}

            {/* Owner */}
            {(file as any).owner_name && (
              <div className="flex items-center gap-3 p-2.5 rounded-lg bg-white/60 dark:bg-slate-800/30">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100/80 dark:bg-slate-700/50">
                  <User className="h-4 w-4 text-slate-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wide">Proprietario</p>
                  <p className="text-[13px] text-slate-700 dark:text-slate-200">
                    {(file as any).owner_name}
                  </p>
                </div>
              </div>
            )}

            {/* Link */}
            {file.web_view_link && (
              <a
                href={file.web_view_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-2.5 rounded-lg bg-blue-50/60 dark:bg-blue-950/20 hover:bg-blue-50 dark:hover:bg-blue-950/30 transition-colors"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100/80 dark:bg-blue-900/40">
                  <ExternalLink className="h-4 w-4 text-blue-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-medium text-blue-600 dark:text-blue-400">
                    Apri in Google Drive
                  </p>
                </div>
              </a>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
