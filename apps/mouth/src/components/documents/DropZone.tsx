'use client';

import { useCallback, useState, useEffect } from 'react';
import { Upload, X } from 'lucide-react';

interface DropZoneProps {
  onFilesDropped: (files: File[]) => void;
  disabled?: boolean;
  children: React.ReactNode;
}

export function DropZone({ onFilesDropped, disabled, children }: DropZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);

  const handleDragEnter = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (disabled) return;

      setDragCounter((prev) => prev + 1);
      if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
        setIsDragging(true);
      }
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    setDragCounter((prev) => {
      const newCount = prev - 1;
      if (newCount === 0) {
        setIsDragging(false);
      }
      return newCount;
    });
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      setDragCounter(0);

      if (disabled) return;

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) {
        onFilesDropped(files);
      }
    },
    [disabled, onFilesDropped]
  );

  // Reset drag state on window blur
  useEffect(() => {
    const handleBlur = () => {
      setIsDragging(false);
      setDragCounter(0);
    };

    window.addEventListener('blur', handleBlur);
    return () => window.removeEventListener('blur', handleBlur);
  }, []);

  return (
    <div
      className="relative h-full w-full"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {children}

      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-emerald-500/10 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-4 rounded-xl border-2 border-dashed border-emerald-500 bg-white/90 px-12 py-8 shadow-lg dark:bg-gray-800/90">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900/50">
              <Upload className="h-8 w-8 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div className="text-center">
              <p className="text-lg font-medium text-gray-900 dark:text-gray-100">
                Rilascia i file qui
              </p>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                I file verranno caricati nella cartella corrente
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface UploadProgressProps {
  uploads: Array<{
    id: string;
    name: string;
    progress: number;
    status: 'uploading' | 'completed' | 'error';
    error?: string;
  }>;
  onCancel: (id: string) => void;
  onDismiss: (id: string) => void;
}

export function UploadProgress({ uploads, onCancel, onDismiss }: UploadProgressProps) {
  if (uploads.length === 0) return null;

  const activeUploads = uploads.filter((u) => u.status === 'uploading');
  const completedUploads = uploads.filter((u) => u.status !== 'uploading');

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl dark:border-gray-700 dark:bg-gray-800">
      {/* Header */}
      <div className="border-b border-gray-200 bg-gray-50 px-4 py-2 dark:border-gray-700 dark:bg-gray-900">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
            {activeUploads.length > 0
              ? `Caricamento ${activeUploads.length} file...`
              : 'Upload completati'}
          </span>
          {completedUploads.length > 0 && activeUploads.length === 0 && (
            <button
              onClick={() => completedUploads.forEach((u) => onDismiss(u.id))}
              className="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
            >
              Chiudi tutto
            </button>
          )}
        </div>
      </div>

      {/* Upload list */}
      <div className="max-h-60 overflow-y-auto">
        {uploads.map((upload) => (
          <div
            key={upload.id}
            className="flex items-center gap-3 border-b border-gray-100 px-4 py-3 last:border-0 dark:border-gray-700"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-gray-700 dark:text-gray-200">
                {upload.name}
              </p>

              {upload.status === 'uploading' && (
                <div className="mt-1">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                      style={{ width: `${upload.progress}%` }}
                    />
                  </div>
                  <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                    {upload.progress}%
                  </p>
                </div>
              )}

              {upload.status === 'completed' && (
                <p className="mt-0.5 text-xs text-emerald-600 dark:text-emerald-400">
                  Completato
                </p>
              )}

              {upload.status === 'error' && (
                <p className="mt-0.5 text-xs text-red-600 dark:text-red-400">
                  {upload.error || 'Errore durante il caricamento'}
                </p>
              )}
            </div>

            <button
              onClick={() =>
                upload.status === 'uploading' ? onCancel(upload.id) : onDismiss(upload.id)
              }
              className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-200"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
