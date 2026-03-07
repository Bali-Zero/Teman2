"use client";

import React, { useState, useCallback } from "react";
import { Upload, X, FileText, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface FileUploadFieldProps {
  id: string;
  label?: string;
  accept?: string;
  maxSize?: number;
  onFileSelect: (file: File | null, error: string | null) => void;
  error?: string | null;
  compact?: boolean;
  className?: string;
}

export const FileUploadField = React.memo(function FileUploadField({
  id,
  label = "Upload File",
  accept = ".pdf,.jpg,.jpeg,.png",
  maxSize = 10 * 1024 * 1024, // 10MB default
  onFileSelect,
  error,
  compact = false,
  className,
}: FileUploadFieldProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const validateFile = useCallback(
    (file: File): string | null => {
      if (maxSize && file.size > maxSize) {
        return `File size must be less than ${(maxSize / 1024 / 1024).toFixed(1)}MB`;
      }

      if (accept) {
        const acceptedTypes = accept
          .split(",")
          .map((t) => t.trim().toLowerCase());
        const fileExt = file.name.split(".").pop()?.toLowerCase() || "";
        const isAccepted = acceptedTypes.some((type) => {
          if (type.startsWith(".")) {
            return fileExt === type.slice(1);
          }
          return file.type.includes(type);
        });

        if (!isAccepted) {
          return `File type must be: ${accept}`;
        }
      }

      return null;
    },
    [accept, maxSize],
  );

  const handleFile = useCallback(
    (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        onFileSelect(null, validationError);
        setSelectedFile(null);
        return;
      }

      setSelectedFile(file);
      onFileSelect(file, null);
    },
    [validateFile, onFileSelect],
  );

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);

      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        handleFile(e.dataTransfer.files[0]);
      }
    },
    [handleFile],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      e.preventDefault();

      if (e.target.files && e.target.files[0]) {
        handleFile(e.target.files[0]);
      }
    },
    [handleFile],
  );

  const clearFile = useCallback(() => {
    setSelectedFile(null);
    onFileSelect(null, null);
    // Reset input
    const input = document.getElementById(id) as HTMLInputElement;
    if (input) input.value = "";
  }, [id, onFileSelect]);

  if (compact) {
    return (
      <div className={cn("space-y-2", className)}>
        {selectedFile ? (
          <div className="flex items-center gap-2 p-2 bg-muted rounded-lg">
            <FileText className="w-4 h-4 text-[var(--accent)]" />
            <span className="text-sm flex-1 truncate">{selectedFile.name}</span>
            <span className="text-xs text-muted-foreground">
              {(selectedFile.size / 1024).toFixed(0)} KB
            </span>
            <button
              onClick={clearFile}
              className="p-1 hover:bg-destructive/10 rounded"
              type="button"
            >
              <X className="w-4 h-4 text-destructive" />
            </button>
          </div>
        ) : (
          <label
            htmlFor={id}
            className={cn(
              "flex items-center gap-2 p-2 border-2 border-dashed rounded-lg cursor-pointer transition-colors",
              dragActive
                ? "border-[var(--accent)] bg-[var(--accent)]/5"
                : "border-muted-foreground/25 hover:border-muted-foreground/50",
              error && "border-destructive bg-destructive/5",
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <Upload className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              Click or drop file
            </span>
            <input
              id={id}
              type="file"
              accept={accept}
              onChange={handleChange}
              className="hidden"
            />
          </label>
        )}

        {error && (
          <div className="flex items-center gap-1 text-xs text-destructive">
            <AlertCircle className="w-3 h-3" />
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      <label className="text-sm font-medium">{label}</label>

      {selectedFile ? (
        <div className="flex items-center gap-3 p-3 border rounded-lg bg-muted">
          <FileText className="w-8 h-8 text-[var(--accent)]" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{selectedFile.name}</p>
            <p className="text-xs text-muted-foreground">
              {(selectedFile.size / 1024).toFixed(1)} KB
            </p>
          </div>
          <button
            onClick={clearFile}
            className="p-2 hover:bg-destructive/10 rounded-lg transition-colors"
            type="button"
          >
            <X className="w-4 h-4 text-destructive" />
          </button>
        </div>
      ) : (
        <label
          htmlFor={id}
          className={cn(
            "flex flex-col items-center justify-center gap-2 p-6 border-2 border-dashed rounded-lg cursor-pointer transition-colors min-h-[120px]",
            dragActive
              ? "border-[var(--accent)] bg-[var(--accent)]/5"
              : "border-muted-foreground/25 hover:border-muted-foreground/50",
            error && "border-destructive bg-destructive/5",
          )}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <Upload className="w-8 h-8 text-muted-foreground" />
          <div className="text-center">
            <p className="text-sm font-medium">
              Click to upload or drag and drop
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {accept.replace(/\./g, "").toUpperCase()} up to{" "}
              {(maxSize / 1024 / 1024).toFixed(0)}MB
            </p>
          </div>
          <input
            id={id}
            type="file"
            accept={accept}
            onChange={handleChange}
            className="hidden"
          />
        </label>
      )}

      {error && (
        <div className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}
    </div>
  );
});

export default FileUploadField;
