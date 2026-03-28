"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { X, Upload, File, AlertCircle, CheckCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface UploadDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onUpload: (files: File[]) => void;
  uploading?: boolean;
}

export function UploadDialog({
  isOpen,
  onClose,
  onUpload,
  uploading = false,
}: UploadDialogProps) {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files || []);
      setSelectedFiles((prev) => [...prev, ...files]);
    },
    [],
  );

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    setSelectedFiles((prev) => [...prev, ...files]);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const removeFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = () => {
    if (selectedFiles.length > 0) {
      onUpload(selectedFiles);
      setSelectedFiles([]);
    }
  };

  const handleClose = () => {
    setSelectedFiles([]);
    onClose();
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Modal */}
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        role="dialog"
        aria-modal="true"
        aria-label="Carica file"
        className="relative z-10 w-full max-w-lg rounded-xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-gray-700 dark:bg-gray-800"
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-900/50">
              <Upload className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Carica file
            </h2>
          </div>
          <button
            onClick={handleClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Drop Zone */}
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`
            relative mb-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-all
            ${
              isDragOver
                ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20"
                : "border-gray-300 bg-gray-50 hover:border-emerald-400 hover:bg-gray-100 dark:border-gray-600 dark:bg-gray-900/50 dark:hover:border-emerald-500 dark:hover:bg-gray-900"
            }
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
          />

          <div
            className={`
            mb-3 flex h-16 w-16 items-center justify-center rounded-full transition-colors
            ${isDragOver ? "bg-emerald-100 dark:bg-emerald-900/50" : "bg-gray-200 dark:bg-gray-700"}
          `}
          >
            <Upload
              className={`h-8 w-8 ${isDragOver ? "text-emerald-600 dark:text-emerald-400" : "text-gray-400"}`}
            />
          </div>

          <p className="text-center text-sm font-medium text-gray-700 dark:text-gray-200">
            {isDragOver
              ? "Rilascia i file qui"
              : "Trascina i file qui oppure clicca per selezionare"}
          </p>
          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Supportati tutti i tipi di file
          </p>
        </div>

        {/* Selected Files List */}
        <AnimatePresence>
          {selectedFiles.length > 0 && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mb-4 max-h-48 overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-700"
            >
              {selectedFiles.map((file, index) => (
                <motion.div
                  key={`${file.name}-${index}`}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className="flex items-center justify-between border-b border-gray-100 px-3 py-2 last:border-0 dark:border-gray-700"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <File className="h-4 w-4 shrink-0 text-gray-400" />
                    <span className="truncate text-sm text-gray-700 dark:text-gray-200">
                      {file.name}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {formatFileSize(file.size)}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(index);
                      }}
                      className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-red-500 dark:hover:bg-gray-700"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={handleClose}
            disabled={uploading}
            className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:text-gray-200 dark:hover:bg-gray-700"
          >
            Annulla
          </button>
          <button
            onClick={handleUpload}
            disabled={selectedFiles.length === 0 || uploading}
            className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 dark:bg-emerald-500 dark:hover:bg-emerald-600"
          >
            {uploading ? (
              <>
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                Caricamento...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Carica{" "}
                {selectedFiles.length > 0 ? `(${selectedFiles.length})` : ""}
              </>
            )}
          </button>
        </div>
      </motion.div>
    </div>
  );
}
