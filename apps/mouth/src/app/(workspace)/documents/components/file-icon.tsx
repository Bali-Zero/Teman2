import { Folder, Image, FileSpreadsheet, Presentation, FileText, FileCode, File } from 'lucide-react';
import type { FileItem } from '@/lib/api/drive/drive.types';

export function getFileIcon(file: FileItem, size: 'sm' | 'lg' = 'lg') {
  const mimeType = file.mime_type || '';
  const sizeClass = size === 'sm' ? 'h-5 w-5' : 'h-12 w-12';

  if (file.is_folder) {
    return <Folder className={`${sizeClass} text-amber-500`} />;
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
