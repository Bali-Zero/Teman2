import type { FileItem } from '@/lib/api/drive/drive.types';
import { getFileIcon } from './file-icon';

interface FileListProps {
  files: FileItem[];
  selectedFiles: Set<string>;
  onFileClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onFileDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
}

export function FileList({ files, selectedFiles, onFileClick, onFileDoubleClick, onContextMenu }: FileListProps) {
  return (
    <div className="min-w-full inline-block align-middle">
      <div className="border-b border-[var(--border)] bg-[var(--background-subtle)] px-4 py-2 text-xs font-medium text-[var(--foreground-muted)] grid grid-cols-[auto_1fr_auto_auto] gap-4">
        <span>Tipo</span>
        <span>Nome</span>
        <span className="hidden md:inline">Modificato</span>
        <span>Dimensione</span>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {files.map((file, index) => {
          const isSelected = selectedFiles.has(file.id);
          return (
            <div
              key={file.id}
              onClick={(e) => onFileClick(file, index, e)}
              onDoubleClick={() => onFileDoubleClick(file)}
              onContextMenu={(e) => onContextMenu(file, e)}
              className={`grid grid-cols-[auto_1fr_auto_auto] gap-4 items-center px-4 py-3 cursor-pointer transition-colors ${
                isSelected
                  ? 'bg-blue-500/10 hover:bg-blue-500/20'
                  : 'hover:bg-[var(--accent)]'
              }`}
            >
              <div className="w-8 flex justify-center">{getFileIcon(file, 'sm')}</div>
              <span className="truncate text-sm font-medium text-[var(--foreground)]">
                {file.name}
              </span>
              <span className="hidden text-sm text-[var(--foreground-muted)] md:inline">
                {formatDate(file.modified_time)}
              </span>
              <span className="text-sm text-[var(--foreground-muted)] text-right w-20">
                 {file.is_folder ? '--' : formatSize(file.size)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

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
