'use client';

import React, { useState } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { FamilyMember } from '@/lib/api/crm/crm.types';
import { COMMON_NATIONALITIES } from '@/lib/api/crm/crm.types';
import { Modal } from '../Modal';

export function EditFamilyMemberModal({
  clientId,
  member,
  onClose,
  onSave,
}: {
  clientId: number;
  member: FamilyMember;
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState<{
    full_name: string; relationship: string; nationality: string; date_of_birth: string;
    passport_number: string; passport_expiry: string; current_visa_type: string;
    visa_expiry: string; email: string; phone: string;
  }>({
    full_name: member.full_name || '', relationship: member.relationship || 'spouse',
    nationality: member.nationality || '', date_of_birth: member.date_of_birth || '',
    passport_number: member.passport_number || '', passport_expiry: member.passport_expiry || '',
    current_visa_type: member.current_visa_type || '', visa_expiry: member.visa_expiry || '',
    email: member.email || '', phone: member.phone || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name) return;
    setIsSaving(true);
    try {
      await api.crm.updateFamilyMember(clientId, member.id, formData);
      toast.success('Family member updated');
      onSave();
      onClose();
    } catch (err) {
      toast.error('Failed to update', { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    'w-full px-4 py-2.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50';

  return (
    <Modal title={`Edit ${member.full_name}`} onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
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
          <label className="block text-sm font-medium mb-1.5">Date of Birth</label>
          <input type="date" value={formData.date_of_birth} onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Email</label>
          <input type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Phone</label>
          <input type="tel" value={formData.phone} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Number</label>
          <input type="text" value={formData.passport_number} onChange={(e) => setFormData({ ...formData, passport_number: e.target.value.toUpperCase() })} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Expiry</label>
          <input type="date" value={formData.passport_expiry} onChange={(e) => setFormData({ ...formData, passport_expiry: e.target.value })} className={inputClass} />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Visa Type</label>
          <input type="text" value={formData.current_visa_type} onChange={(e) => setFormData({ ...formData, current_visa_type: e.target.value })} className={inputClass} placeholder="e.g. KITAS, KITAP, B211A" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Visa Expiry</label>
          <input type="date" value={formData.visa_expiry} onChange={(e) => setFormData({ ...formData, visa_expiry: e.target.value })} className={inputClass} />
        </div>
      </div>
    </Modal>
  );
}
