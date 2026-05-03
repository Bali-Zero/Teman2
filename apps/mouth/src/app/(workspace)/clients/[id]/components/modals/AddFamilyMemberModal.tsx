'use client';

import React, { useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { COMMON_NATIONALITIES } from '@/lib/api/crm/crm.types';
import { Modal } from '../Modal';

export function AddFamilyMemberModal({
  clientId,
  onClose,
  onSave,
}: {
  clientId: number;
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    full_name: '',
    relationship: 'spouse',
    nationality: '',
    passport_number: '',
    passport_expiry: '',
    current_visa_type: '',
    visa_expiry: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name) return;
    setIsSaving(true);
    try {
      await api.crm.createFamilyMember(clientId, formData);
      toast.success('Family member added');
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
    <Modal title="Add Family Member" aria-label="Add Family Member" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Full Name *</label>
          <input type="text" value={formData.full_name} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} className={inputClass} required />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Relationship</label>
          <select value={formData.relationship} onChange={(e) => setFormData({ ...formData, relationship: e.target.value })} className={inputClass}>
            <option value="spouse">Spouse</option>
            <option value="child">Child</option>
            <option value="parent">Parent</option>
            <option value="dependent">Dependent</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Nationality</label>
          <select value={formData.nationality} onChange={(e) => setFormData({ ...formData, nationality: e.target.value })} className={inputClass}>
            <option value="">Select...</option>
            {COMMON_NATIONALITIES.map((nat) => (<option key={nat} value={nat}>{nat}</option>))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Number</label>
          <input type="text" value={formData.passport_number} onChange={(e) => setFormData({ ...formData, passport_number: e.target.value.toUpperCase() })} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Expiry</label>
          <input type="date" value={formData.passport_expiry} onChange={(e) => setFormData({ ...formData, passport_expiry: e.target.value })} className={inputClass} />
        </div>
      </div>
    </Modal>
  );
}
