"use client";

import React, { useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type {
  ClientDocument,
  DocumentCategory,
  FamilyMember,
  DocumentCategoryType,
} from "@/lib/api/crm/crm.types";
import { Modal } from "../Modal";

export function EditDocumentModal({
  clientId,
  document,
  categories,
  familyMembers,
  onClose,
  onSave,
}: {
  clientId: number;
  document: ClientDocument;
  categories: DocumentCategory[];
  familyMembers: FamilyMember[];
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    file_name: document.file_name || "",
    document_type: document.document_type || "",
    document_category: document.document_category || "other",
    expiry_date: document.expiry_date?.split("T")[0] || "",
    google_drive_file_url: document.google_drive_file_url || "",
    family_member_id: document.family_member_id?.toString() || "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.file_name) {
      toast.error("Document name is required");
      return;
    }
    setIsSaving(true);
    try {
      await api.crm.updateDocument(clientId, document.id, {
        file_name: formData.file_name,
        document_type: formData.document_type,
        document_category: formData.document_category,
        expiry_date: formData.expiry_date || undefined,
        google_drive_file_url: formData.google_drive_file_url || undefined,
        family_member_id: formData.family_member_id
          ? Number(formData.family_member_id)
          : undefined,
      });
      toast.success("Document updated");
      onSave();
      onClose();
    } catch (err) {
      toast.error("Failed to update", { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    "w-full px-4 py-2.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50";

  return (
    <Modal
      title="Edit Document"
      aria-label="Edit Document"
      onClose={onClose}
      isSaving={isSaving}
      onSave={handleSubmit}
    >
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
            placeholder="e.g. Passport Scan"
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
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">
            Google Drive Link
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
      </div>
    </Modal>
  );
}
