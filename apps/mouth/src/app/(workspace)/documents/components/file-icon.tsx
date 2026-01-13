import { Image, FileSpreadsheet, Presentation, FileText, FileCode, File } from 'lucide-react';
import type { FileItem } from '@/lib/api/drive/drive.types';

// Windows-style filled folder icon
function WindowsFolder({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Back panel shadow */}
      <path
        d="M4 12C4 10.8954 4.89543 10 6 10H18L22 14H42C43.1046 14 44 14.8954 44 16V38C44 39.1046 43.1046 40 42 40H6C4.89543 40 4 39.1046 4 38V12Z"
        fill="#D97706"
      />
      {/* Front panel */}
      <path
        d="M4 16C4 14.8954 4.89543 14 6 14H42C43.1046 14 44 14.8954 44 16V38C44 39.1046 43.1046 40 42 40H6C4.89543 40 4 39.1046 4 38V16Z"
        fill="#F59E0B"
      />
      {/* Top highlight */}
      <path
        d="M6 14H18L22 10H6C4.89543 10 4 10.8954 4 12V16C4 14.8954 4.89543 14 6 14Z"
        fill="#FBBF24"
      />
      {/* Inner shadow for depth */}
      <path
        d="M6 18H42V20H6V18Z"
        fill="#D97706"
        opacity="0.3"
      />
    </svg>
  );
}

export function getFileIcon(file: FileItem, size: 'sm' | 'lg' = 'lg') {
  const mimeType = file.mime_type || '';
  const sizeClass = size === 'sm' ? 'h-5 w-5' : 'h-12 w-12';

  if (file.is_folder) {
    return <WindowsFolder className={sizeClass} />;
  }
  if (mimeType.includes('image')) {
    return <Image className={`${sizeClass} text-pink-500`} />;
  }
  if (mimeType.includes('spreadsheet') || mimeType.includes('excel')) {
    return <FileSpreadsheet className={`${sizeClass} text-green-500`} />;
  }
  if (mimeType.includes('presentation')) {
    return <Presentation className={`${sizeClass} text-yellow-500`} />;
  }
  if (mimeType.includes('document') || mimeType.includes('word')) {
    return <FileText className={`${sizeClass} text-blue-500`} />;
  }
  if (mimeType.includes('pdf')) {
    return <FileText className={`${sizeClass} text-red-500`} />;
  }
  if (
    mimeType.includes('code') ||
    mimeType.includes('javascript') ||
    mimeType.includes('json')
  ) {
    return <FileCode className={`${sizeClass} text-purple-500`} />;
  }
  return <File className={`${sizeClass} text-gray-400`} />;
}
