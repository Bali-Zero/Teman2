"use client";

import { useState, useRef } from "react";
import { intelligenceApi, StagingItem } from "@/lib/api/intelligence.api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { Loader2, Upload, Image as ImageIcon, X } from "lucide-react";
import { logger } from "@/lib/logger";
import { fileToBase64 } from "@/lib/utils";

interface CoverImageUploaderProps {
  item: StagingItem;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploaded: () => void;
}

export function CoverImageUploader({
  item,
  open,
  onOpenChange,
  onUploaded,
}: CoverImageUploaderProps) {
  const [preview, setPreview] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const handleFileSelect = (selectedFile: File) => {
    if (!selectedFile.type.startsWith("image/")) {
      toast.error("Invalid file", "Please select an image file");
      return;
    }

    // Check file size (max 5MB)
    if (selectedFile.size > 5 * 1024 * 1024) {
      toast.error("File too large", "Please select an image smaller than 5MB");
      return;
    }

    setFile(selectedFile);

    // Create preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreview(e.target?.result as string);
    };
    reader.readAsDataURL(selectedFile);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  };

  const handleUpload = async () => {
    if (!file || !preview) {
      toast.error("No file", "Please select an image first");
      return;
    }

    setUploading(true);
    try {
      // Convert to base64 using utility function
      const base64 = await fileToBase64(file);
      const filename = file.name;

      await intelligenceApi.uploadCoverImage(
        item.type,
        item.id,
        base64,
        filename,
      );
      toast.success("Uploaded!", "Cover image uploaded successfully");
      onUploaded();
      onOpenChange(false);
      setFile(null);
      setPreview(null);
    } catch (error) {
      toast.error("Error", "Failed to upload cover image");
      logger.error(
        "Failed to upload cover image",
        {
          component: "CoverImageUploader",
          action: "upload_cover_image",
          itemId: item.id,
        },
        error as Error,
      );
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    if (!uploading) {
      setFile(null);
      setPreview(null);
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            Upload Cover Image
          </DialogTitle>
          <DialogDescription>
            Upload a cover image for this article
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 mt-4">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-[var(--accent)] transition-colors min-h-[200px] flex items-center justify-center"
            onClick={() => fileInputRef.current?.click()}
          >
            {preview ? (
              <div className="relative w-full">
                <img
                  src={preview}
                  alt="Preview"
                  className="max-h-64 mx-auto rounded-lg object-cover"
                />
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setPreview(null);
                    setFile(null);
                  }}
                  className="absolute top-2 right-2 p-1 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors"
                  disabled={uploading}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <Upload className="h-12 w-12 mx-auto text-[var(--foreground-muted)]" />
                <p className="text-[var(--foreground-muted)]">
                  Drag & drop an image here, or click to select
                </p>
                <p className="text-sm text-[var(--foreground-muted)]">
                  Supports: JPG, PNG, WebP (max 5MB)
                </p>
              </div>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              aria-label="Upload cover image"
              className="hidden"
              onChange={(e) => {
                const selectedFile = e.target.files?.[0];
                if (selectedFile) {
                  handleFileSelect(selectedFile);
                }
              }}
            />
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <Button variant="outline" onClick={handleClose} disabled={uploading}>
            Cancel
          </Button>
          <Button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="gap-2"
          >
            {uploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Upload Cover Image
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
