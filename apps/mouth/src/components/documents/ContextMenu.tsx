'use client';

import { useEffect, useRef } from 'react';
import {
  ExternalLink,
  Download,
  Pencil,
  Trash2,
  Copy,
  FolderInput,
  FileText,
  Users,
} from 'lucide-react';
import type { FileItem } from '@/lib/api/drive/drive.types';

interface ContextMenuProps {
  file: FileItem;
  position: { x: number; y: number };
  onClose: () => void;
  onOpen: (file: FileItem) => void;
  onRename: (file: FileItem) => void;
  onDelete: (file: FileItem) => void;
  onMove: (file: FileItem) => void;
  onCopy: (file: FileItem) => void;
  onDownload: (file: FileItem) => void;
  onManageAccess?: (file: FileItem) => void;
  isBoard?: boolean;
}

export function ContextMenu({
  file,
  position,
  onClose,
  onOpen,
  onRename,
  onDelete,
  onMove,
  onCopy,
  onDownload,
  onManageAccess,
  isBoard = false,
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  // Adjust position to stay within viewport
  useEffect(() => {
    if (menuRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let adjustedX = position.x;
      let adjustedY = position.y;

      // Flip horizontally if too close to right edge
      if (position.x + rect.width > viewportWidth - 10) {
        adjustedX = position.x - rect.width;
      }

      // Flip vertically if too close to bottom edge
      if (position.y + rect.height > viewportHeight - 10) {
        adjustedY = position.y - rect.height;
      }

      menuRef.current.style.left = `${adjustedX}px`;
      menuRef.current.style.top = `${adjustedY}px`;
    }
  }, [position]);

  const menuItems = [
    {
      icon: ExternalLink,
      label: file.is_folder ? 'Apri' : 'Apri in Drive',
      action: () => onOpen(file),
      divider: false,
    },
    {
      icon: Pencil,
      label: 'Rinomina',
      action: () => onRename(file),
      divider: false,
    },
    {
      icon: FolderInput,
      label: 'Sposta in...',
      action: () => onMove(file),
      divider: false,
    },
    ...(file.is_folder
      ? []
      : [
          {
            icon: Copy,
            label: 'Crea copia',
            action: () => onCopy(file),
            divider: false,
          },
          {
            icon: Download,
            label: 'Scarica',
            action: () => onDownload(file),
            divider: false,
          },
        ]),
    // Manage Access - available to all users
    ...(onManageAccess
      ? [
          {
            icon: Users,
            label: 'Gestisci accesso',
            action: () => onManageAccess(file),
            divider: true,
            highlight: true,
          },
        ]
      : []),
    {
      icon: Trash2,
      label: 'Elimina',
      action: () => onDelete(file),
      divider: false,
      danger: true,
    },
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[200px] rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-800"
      style={{ left: position.x, top: position.y }}
    >
      {/* File name header */}
      <div className="flex items-center gap-2 border-b border-gray-200 px-3 py-2 dark:border-gray-700">
        <FileText className="h-4 w-4 text-gray-400" />
        <span className="max-w-[180px] truncate text-sm font-medium text-gray-700 dark:text-gray-200">
          {file.name}
        </span>
      </div>

      {/* Menu items */}
      <div className="py-1">
        {menuItems.map((item, index) => (
          <div key={item.label}>
            {item.divider && (
              <div className="my-1 border-t border-gray-200 dark:border-gray-700" />
            )}
            <button
              onClick={() => {
                item.action();
                onClose();
              }}
              className={`flex w-full items-center gap-3 px-3 py-2 text-sm transition-colors ${
                item.danger
                  ? 'text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20'
                  : (item as { highlight?: boolean }).highlight
                    ? 'text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-900/20'
                    : 'text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700'
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
