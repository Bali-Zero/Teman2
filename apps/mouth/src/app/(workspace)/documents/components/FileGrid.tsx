import type { FileItem } from '@/lib/api/drive/drive.types';
import { getFileIcon } from './file-icon';

interface FileGridProps {
  files: FileItem[];
  selectedFiles: Set<string>;
  onFileClick: (file: FileItem, index: number, e: React.MouseEvent) => void;
  onFileDoubleClick: (file: FileItem) => void;
  onContextMenu: (file: FileItem, e: React.MouseEvent) => void;
}

export function FileGrid({ files, selectedFiles, onFileClick, onFileDoubleClick, onContextMenu }: FileGridProps) {
  return (
    <div className="grid grid-cols-2 gap-4 p-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
      {files.map((file, index) => {
        const isSelected = selectedFiles.has(file.id);
        return (
          <div
            key={file.id}
            onClick={(e) => onFileClick(file, index, e)}
            onDoubleClick={() => onFileDoubleClick(file)}
            onContextMenu={(e) => onContextMenu(file, e)}
            className={`group relative flex cursor-pointer flex-col items-center rounded-xl border p-4 transition-all hover:bg-[var(--accent)] ${
              isSelected
                ? 'border-blue-500 bg-blue-500/10 hover:bg-blue-500/20'
                : 'border-transparent hover:border-[var(--border)]'
            }`}
          >
            <div className="mb-3 transition-transform group-hover:scale-110">
              {getFileIcon(file, 'lg')}
            </div>
            <span className="w-full truncate text-center text-sm font-medium text-[var(--foreground)]">
              {file.name}
            </span>
            <span className="text-xs text-[var(--foreground-muted)]">
                {file.is_folder ? 'Cartella' : formatSize(file.size)}
            </span>
          </div>
        );
      })}
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
