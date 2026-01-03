'use client';

import { useState, useEffect, useRef } from 'react';
import { X, Folder, FileText, FileSpreadsheet, Presentation } from 'lucide-react';
import type { DocType } from '@/lib/api/drive/drive.types';

type ModalMode = 'folder' | 'document' | 'spreadsheet' | 'presentation' | 'rename';

interface FileModalProps {
  mode: ModalMode;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (name: string, docType?: DocType) => void;
  initialName?: string;
  loading?: boolean;
}

const modeConfig: Record<
  ModalMode,
  { title: string; placeholder: string; icon: React.ElementType; buttonText: string }
> = {
  folder: {
    title: 'Nuova cartella',
    placeholder: 'Nome cartella',
    icon: Folder,
    buttonText: 'Crea',
  },
  document: {
    title: 'Nuovo documento',
    placeholder: 'Nome documento',
    icon: FileText,
    buttonText: 'Crea',
  },
  spreadsheet: {
    title: 'Nuovo foglio di calcolo',
    placeholder: 'Nome foglio',
    icon: FileSpreadsheet,
    buttonText: 'Crea',
  },
  presentation: {
    title: 'Nuova presentazione',
    placeholder: 'Nome presentazione',
    icon: Presentation,
    buttonText: 'Crea',
  },
  rename: {
    title: 'Rinomina',
    placeholder: 'Nuovo nome',
    icon: FileText,
    buttonText: 'Rinomina',
  },
};

export function FileModal({
  mode,
  isOpen,
  onClose,
  onSubmit,
  initialName = '',
  loading = false,
}: FileModalProps) {
  const [name, setName] = useState(initialName);
  const inputRef = useRef<HTMLInputElement>(null);

  const config = modeConfig[mode];
  const Icon = config.icon;

  // Reset and focus on open
  useEffect(() => {
    if (isOpen) {
      setName(initialName);
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      }, 100);
    }
  }, [isOpen, initialName]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || loading) return;

    const docType = mode === 'folder' || mode === 'rename' ? undefined : (mode as DocType);
    onSubmit(name.trim(), docType);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-md rounded-xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-800">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/50">
              <Icon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {config.title}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          <div className="mb-6">
            <input
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={config.placeholder}
              disabled={loading}
              className="w-full rounded-lg border border-gray-300 bg-white px-4 py-3 text-gray-900 placeholder-gray-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder-gray-500 dark:focus:border-emerald-400"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:text-gray-200 dark:hover:bg-gray-700"
            >
              Annulla
            </button>
            <button
              type="submit"
              disabled={!name.trim() || loading}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 dark:bg-emerald-500 dark:hover:bg-emerald-600"
            >
              {loading && (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              )}
              {config.buttonText}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Create menu dropdown for selecting doc type
interface CreateMenuProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (mode: 'folder' | 'document' | 'spreadsheet' | 'presentation') => void;
  position: { x: number; y: number };
}

export function CreateMenu({ isOpen, onClose, onSelect, position }: CreateMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const items = [
    { mode: 'folder' as const, icon: Folder, label: 'Nuova cartella', color: 'text-amber-600' },
    { mode: 'document' as const, icon: FileText, label: 'Google Docs', color: 'text-blue-600' },
    {
      mode: 'spreadsheet' as const,
      icon: FileSpreadsheet,
      label: 'Google Sheets',
      color: 'text-green-600',
    },
    {
      mode: 'presentation' as const,
      icon: Presentation,
      label: 'Google Slides',
      color: 'text-yellow-600',
    },
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[200px] rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-gray-700 dark:bg-gray-800"
      style={{ left: position.x, top: position.y }}
    >
      {items.map((item) => (
        <button
          key={item.mode}
          onClick={() => {
            onSelect(item.mode);
            onClose();
          }}
          className="flex w-full items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700"
        >
          <item.icon className={`h-5 w-5 ${item.color}`} />
          {item.label}
        </button>
      ))}
    </div>
  );
}
