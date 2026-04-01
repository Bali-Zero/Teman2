"use client";

import React, { useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import { Upload, FileText, X } from "lucide-react";
import { api } from "@/lib/api";
import { fileToBase64 } from "@/lib/utils";
import type {
  DocumentCategory,
  FamilyMember,
  DocumentCategoryType,
} from "@/lib/api/crm/crm.types";
import { Modal } from "../Modal";

export function AddDocumentModal({
  clientId,
  categories,
  familyMembers,
  clientHasDriveFolder,
  onClose,
  onSave,
  defaultCategory,
  defaultType,
  defaultSubfolderHint,
}: {
  clientId: number;
  categories: DocumentCategory[];
  familyMembers: FamilyMember[];
  clientHasDriveFolder?: boolean;
  onClose: () => void;
  onSave: () => void;
  defaultCategory?: DocumentCategoryType;
  defaultType?: string;
  defaultSubfolderHint?: string;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [formData, setFormData] = useState({
    file_name: "",
    document_type: defaultType || "",
    document_category: (defaultCategory || "other") as DocumentCategoryType,
    expiry_date: "",
    google_drive_file_url: "",
    family_member_id: "",
  });

  const allowedTypes = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/pdf",
  ];
  const maxSize = 10 * 1024 * 1024; // 10MB

  const handleFileSelect = useCallback(
    (file: File) => {
      if (!allowedTypes.includes(file.type)) {
        toast.error("Invalid file type", {
          description: "Please upload JPG, PNG, or PDF",
        });
        return;
      }
      if (file.size > maxSize) {
        toast.error("File too large", {
          description: "Maximum file size is 10MB",
        });
        return;
      }
      setSelectedFile(file);
      if (!formData.file_name) {
        setFormData((prev) => ({ ...prev, file_name: file.name }));
      }
    },
    [formData.file_name],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect],
  );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.file_name) {
      toast.error("Document name is required");
      return;
    }
    if (!selectedFile && !formData.google_drive_file_url) {
      toast.error("Please upload a file or provide a Drive link");
      return;
    }

    setIsSaving(true);
    try {
      if (selectedFile) {
        // Base64 upload path
        const base64 = await fileToBase64(selectedFile);
        const response = await api.crm.uploadDocumentBase64(clientId, {
          file: base64,
          file_name: formData.file_name,
          document_type: formData.document_type || "document",
          mime_type: selectedFile.type,
          document_category: formData.document_category,
          subfolder_hint: defaultSubfolderHint,
          expiry_date: formData.expiry_date || undefined,
          family_member_id: formData.family_member_id
            ? Number(formData.family_member_id)
            : undefined,
        });
        if (response.success) {
          toast.success(
            response.ocr_triggered
              ? "Document uploaded — OCR in progress..."
              : "Document uploaded",
          );
        }
      } else {
        // Drive URL fallback path (existing behavior)
        await api.crm.createDocument(clientId, {
          ...formData,
          family_member_id: formData.family_member_id
            ? Number(formData.family_member_id)
            : undefined,
        });
        toast.success("Document added");
      }
      onSave();
      onClose();
    } catch (err) {
      toast.error("Failed to upload", {
        description: (err as Error).message,
      });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    "w-full px-4 py-2.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50";

  return (
    <Modal
      title="Add Document"
      aria-label="Add Document"
      onClose={onClose}
      isSaving={isSaving}
      onSave={handleSubmit}
    >
      {/* Drag-and-drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`mb-4 border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
          isDragging
            ? "border-[var(--bz-accent)] bg-[var(--bz-accent)]/10"
            : selectedFile
              ? "border-green-500/50 bg-green-500/5"
              : "border-[var(--bz-border)] hover:border-[var(--bz-accent)]/50"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFileSelect(file);
          }}
          className="hidden"
        />
        {selectedFile ? (
          <div className="flex items-center justify-center gap-3">
            <FileText className="w-5 h-5 text-green-400" />
            <span className="text-sm text-[var(--bz-text-1)]">
              {selectedFile.name}
            </span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedFile(null);
              }}
              className="p-1 rounded hover:bg-[var(--bz-surface-2)]"
            >
              <X className="w-4 h-4 text-[var(--bz-text-3)]" />
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <Upload className="w-8 h-8 mx-auto text-[var(--bz-text-3)]" />
            <p className="text-sm text-[var(--bz-text-2)]">
              Drop file here or click to browse
            </p>
            <p className="text-xs text-[var(--bz-text-3)]">
              PDF, JPG, PNG — max 10MB
            </p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">
            Document Name *
          </label>
          <input
            type="text"
            value={formData.file_name}
            onChange={(e) =>
              setFormData({ ...formData, file_name: e.target.value })
            }
            className={inputClass}
            placeholder="e.g. KITAS Eduardo 2026"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Category</label>
          <select
            value={formData.document_category}
            onChange={(e) =>
              setFormData({
                ...formData,
                document_category: e.target.value as DocumentCategoryType,
              })
            }
            className={inputClass}
          >
            <option value="immigration">Immigration</option>
            <option value="pma">Company (PMA)</option>
            <option value="tax">Tax</option>
            <option value="personal">Personal</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Type</label>
          <input
            type="text"
            value={formData.document_type}
            onChange={(e) =>
              setFormData({ ...formData, document_type: e.target.value })
            }
            className={inputClass}
            placeholder="passport, kitas, etc"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Expiry Date
          </label>
          <input
            type="date"
            value={formData.expiry_date}
            onChange={(e) =>
              setFormData({ ...formData, expiry_date: e.target.value })
            }
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Belongs To</label>
          <select
            value={formData.family_member_id}
            onChange={(e) =>
              setFormData({ ...formData, family_member_id: e.target.value })
            }
            className={inputClass}
          >
            <option value="">Main Client</option>
            {familyMembers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name} ({m.relationship})
              </option>
            ))}
          </select>
        </div>

        {/* Drive URL fallback — only shown when no file selected */}
        {!selectedFile && (
          <div className="md:col-span-2">
            <label className="block text-sm font-medium mb-1.5">
              Or paste Google Drive Link
            </label>
            <input
              type="url"
              value={formData.google_drive_file_url}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  google_drive_file_url: e.target.value,
                })
              }
              className={inputClass}
              placeholder="https://drive.google.com/..."
            />
          </div>
        )}
      </div>
    </Modal>
  );
}
