'use client';

import React, { useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { DocumentCategory, FamilyMember, DocumentCategoryType } from '@/lib/api/crm/crm.types';
import { Modal } from '../Modal';

export function AddDocumentModal({
  clientId,
  categories,
  familyMembers,
  clientHasDriveFolder,
  onClose,
  onSave,
}: {
  clientId: number;
  categories: DocumentCategory[];
  familyMembers: FamilyMember[];
  clientHasDriveFolder?: boolean;
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    file_name: '',
    document_type: '',
    document_category: 'other' as DocumentCategoryType,
    expiry_date: '',
    google_drive_file_url: '',
    family_member_id: '',
    drive_folder: '',
  });

  // Auto-select folder based on category
  React.useEffect(() => {
    const categoryToFolder: Record<string, string> = {
      immigration: '01_Immigration',
      pma: '02_Company',
      tax: '03_Tax',
      personal: '04_Family',
      other: '99_Misc',
    };

    if (formData.document_category && clientHasDriveFolder) {
      setFormData((prev) => ({
        ...prev,
        drive_folder: categoryToFolder[formData.document_category] || '99_Misc',
      }));
    }
  }, [formData.document_category, clientHasDriveFolder]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.file_name) return;
    setIsSaving(true);
    try {
      await api.crm.createDocument(clientId, {
        ...formData,
        family_member_id: formData.family_member_id ? Number(formData.family_member_id) : undefined,
      });
      toast.success('Document added');
      onSave();
      onClose();
    } catch (err) {
      toast.error('Failed to add', { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    'w-full px-4 py-2.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50';

  return (
    <Modal title="Add Document" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Document Name *</label>
          <input type="text" value={formData.file_name} onChange={(e) => setFormData({ ...formData, file_name: e.target.value })} className={inputClass} placeholder="e.g. Passport Scan" required />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Category</label>
          <select value={formData.document_category} onChange={(e) => setFormData({ ...formData, document_category: e.target.value as DocumentCategoryType })} className={inputClass}>
            <option value="immigration">Immigration</option>
            <option value="pma">Company (PMA)</option>
            <option value="tax">Tax</option>
            <option value="personal">Personal</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Type</label>
          <input type="text" value={formData.document_type} onChange={(e) => setFormData({ ...formData, document_type: e.target.value })} className={inputClass} placeholder="passport, kitas, etc" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Expiry Date</label>
          <input type="date" value={formData.expiry_date} onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Belongs To</label>
          <select value={formData.family_member_id} onChange={(e) => setFormData({ ...formData, family_member_id: e.target.value })} className={inputClass}>
            <option value="">Main Client</option>
            {familyMembers.map((m) => (<option key={m.id} value={m.id}>{m.full_name} ({m.relationship})</option>))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Google Drive Link</label>
          <input type="url" value={formData.google_drive_file_url} onChange={(e) => setFormData({ ...formData, google_drive_file_url: e.target.value })} className={inputClass} placeholder="https://drive.google.com/..." />
        </div>
      </div>
    </Modal>
  );
}
