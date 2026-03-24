'use client';

import React, { useState, useCallback } from 'react';
import {
  Building2,
  CreditCard,
  MapPin,
  Users,
  FileText,
  Upload,
  Plus,
  X,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { fileToBase64 } from '@/lib/utils';

// ============================================
// ADD COMPANY MODAL - TYPES
// ============================================
type DocumentType = 'akta' | 'sk' | 'businessId' | 'nib' | 'npwp' | 'profilePerseroan';

interface CompanyDocuments {
  akta?: File;
  sk?: File;
  businessId?: File;
  nib?: File;
  npwp?: File;
  profilePerseroan?: File;
}

interface CompanyFormData {
  company_name: string;
  company_type: string;
  kbli_code: string;
  nib: string;
  npwp_company: string;
  registered_address: string;
  city: string;
  province: string;
  company_email: string;
  company_phone: string;
  role: string;
  is_primary: boolean;
  ownership_percentage: string;
}

interface FormErrors {
  company_name?: string;
  company_email?: string;
  ownership_percentage?: string;
  nib?: string;
  npwp_company?: string;
}

const INITIAL_FORM_DATA: CompanyFormData = {
  company_name: '',
  company_type: 'PT PMA',
  kbli_code: '',
  nib: '',
  npwp_company: '',
  registered_address: '',
  city: '',
  province: '',
  company_email: '',
  company_phone: '',
  role: 'Director',
  is_primary: false,
  ownership_percentage: '',
};

// ============================================
// CUSTOM HOOK: useCompanyForm
// ============================================
function useCompanyForm(clientId: number, onSuccess: () => void) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExtractingNpwp, setIsExtractingNpwp] = useState(false);
  const [isExtractingNib, setIsExtractingNib] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<Partial<Record<DocumentType, string>>>({});
  const [errors, setErrors] = useState<FormErrors>({});
  const [documents, setDocuments] = useState<CompanyDocuments>({});
  const [formData, setFormData] = useState<CompanyFormData>(INITIAL_FORM_DATA);

  const updateField = useCallback(
    <K extends keyof CompanyFormData>(field: K, value: CompanyFormData[K]) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      if (errors[field as keyof FormErrors]) {
        setErrors((prev) => ({ ...prev, [field]: undefined }));
      }
    },
    [errors]
  );

  const updateDocument = useCallback(
    (type: DocumentType, file: File | undefined) => {
      setDocuments((prev) => ({ ...prev, [type]: file }));
      if (uploadErrors[type]) {
        setUploadErrors((prev) => ({ ...prev, [type]: undefined }));
      }
    },
    [uploadErrors]
  );

  const validateForm = useCallback((): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.company_name.trim()) {
      newErrors.company_name = 'Company name is required';
    } else if (formData.company_name.length < 3) {
      newErrors.company_name = 'Company name must be at least 3 characters';
    } else if (formData.company_name.length > 200) {
      newErrors.company_name = 'Company name must be less than 200 characters';
    }

    if (formData.company_email) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(formData.company_email)) {
        newErrors.company_email = 'Invalid email format';
      }
    }

    if (formData.ownership_percentage) {
      const percentage = parseFloat(formData.ownership_percentage);
      if (isNaN(percentage) || percentage < 0 || percentage > 100) {
        newErrors.ownership_percentage = 'Ownership must be between 0 and 100';
      }
    }

    if (formData.nib && !/^\d+$/.test(formData.nib)) {
      newErrors.nib = 'NIB should contain only numbers';
    }

    if (formData.npwp_company) {
      const npwpClean = formData.npwp_company.replace(/\D/g, '');
      if (npwpClean.length !== 15) {
        newErrors.npwp_company = 'NPWP must be 15 digits';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  const extractNpwp = useCallback(async (): Promise<boolean> => {
    if (!documents.npwp) {
      toast.error('Please upload NPWP file first');
      return false;
    }

    setIsExtractingNpwp(true);
    try {
      const base64 = await fileToBase64(documents.npwp);
      const response = (await api.post('/api/crm/clients/extract-npwp', {
        file: base64,
        file_name: documents.npwp.name,
      })) as {
        success: boolean;
        npwp?: string;
        address?: string;
        city?: string;
        message?: string;
      };

      if (response.success) {
        setFormData((prev) => ({
          ...prev,
          npwp_company: response.npwp || prev.npwp_company,
          registered_address: response.address || prev.registered_address,
          city: response.city || prev.city,
        }));
        toast.success('NPWP data extracted', {
          description: 'Address and NPWP number auto-filled',
        });
        return true;
      } else {
        toast.warning('OCR failed', { description: response.message });
        return false;
      }
    } catch (err) {
      toast.error('Extraction failed', { description: (err as Error).message });
      return false;
    } finally {
      setIsExtractingNpwp(false);
    }
  }, [documents.npwp]);

  const extractNib = useCallback(async (): Promise<boolean> => {
    if (!documents.nib) {
      toast.error('Please upload NIB file first');
      return false;
    }

    setIsExtractingNib(true);
    try {
      const base64 = await fileToBase64(documents.nib);
      const response = (await api.post('/api/crm/clients/extract-nib', {
        file: base64,
        file_name: documents.nib.name,
      })) as {
        success: boolean;
        nib?: string;
        company_name?: string;
        kbli_code?: string;
        message?: string;
      };

      if (response.success) {
        setFormData((prev) => ({
          ...prev,
          nib: response.nib || prev.nib,
          company_name: response.company_name || prev.company_name,
          kbli_code: response.kbli_code || prev.kbli_code,
        }));
        toast.success('NIB data extracted', {
          description: 'NIB number auto-filled',
        });
        return true;
      } else {
        toast.warning('OCR failed', { description: response.message });
        return false;
      }
    } catch (err) {
      toast.error('Extraction failed', { description: (err as Error).message });
      return false;
    } finally {
      setIsExtractingNib(false);
    }
  }, [documents.nib]);

  const submit = useCallback(async (): Promise<boolean> => {
    if (!validateForm()) {
      toast.error('Please fix form errors');
      return false;
    }

    setIsSubmitting(true);
    try {
      const company = await api.crm.createCompany({
        company_name: formData.company_name,
        company_type: formData.company_type,
        kbli_code: formData.kbli_code || undefined,
        nib: formData.nib || undefined,
        npwp_company: formData.npwp_company || undefined,
        registered_address: formData.registered_address || undefined,
        city: formData.city || undefined,
        province: formData.province || undefined,
        company_email: formData.company_email || undefined,
        company_phone: formData.company_phone || undefined,
      });

      await api.crm.linkClientToCompany(clientId, company.id, {
        role: formData.role,
        is_primary: formData.is_primary,
        ownership_percentage: formData.ownership_percentage
          ? parseFloat(formData.ownership_percentage)
          : undefined,
      });

      // Upload documents if any
      const uploadPromises = Object.entries(documents)
        .filter(([, file]) => file !== undefined)
        .map(async ([type, file]) => {
          try {
            const base64 = await fileToBase64(file!);
            await api.post(`/api/crm/companies/${company.id}/documents`, {
              file: base64,
              file_name: file!.name,
              document_type: type,
            });
          } catch (err) {
            logger.error(`Failed to upload ${type}:`, {}, err as Error);
            setUploadErrors((prev) => ({
              ...prev,
              [type as DocumentType]: 'Upload failed',
            }));
          }
        });

      await Promise.all(uploadPromises);

      toast.success('Company created and linked successfully');
      onSuccess();
      return true;
    } catch (err) {
      logger.error('Failed to create company:', {}, err as Error);
      toast.error('Failed to create company', {
        description: (err as Error).message,
      });
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }, [formData, documents, clientId, onSuccess, validateForm]);

  const reset = useCallback(() => {
    setFormData(INITIAL_FORM_DATA);
    setDocuments({});
    setErrors({});
    setUploadErrors({});
  }, []);

  return {
    formData,
    documents,
    errors,
    uploadErrors,
    isSubmitting,
    isExtractingNpwp,
    isExtractingNib,
    updateField,
    updateDocument,
    validateForm,
    extractNpwp,
    extractNib,
    submit,
    reset,
  };
}

// ============================================
// ADD COMPANY MODAL
// ============================================
interface AddCompanyModalProps {
  clientId: number;
  onClose: () => void;
  onSuccess: () => void;
}

export function AddCompanyModal({ clientId, onClose, onSuccess }: AddCompanyModalProps) {
  const {
    formData,
    documents,
    errors,
    uploadErrors,
    isSubmitting,
    isExtractingNpwp,
    isExtractingNib,
    updateField,
    updateDocument,
    extractNpwp,
    extractNib,
    submit,
    reset,
  } = useCompanyForm(clientId, onSuccess);

  // Handle close with cleanup
  const handleClose = useCallback(() => {
    reset();
    onClose();
  }, [reset, onClose]);

  const inputClass =
    'w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50 text-sm';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-[var(--bz-border)] bg-[var(--bz-base)] p-6 shadow-xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">Add New Company</h3>
            <p className="text-sm text-[var(--bz-text-2)]">Create a new PT PMA and link it to this client</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close modal">
            <X className="w-5 h-5" />
          </Button>
        </div>

        <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-4">
          {/* Company Basic Info */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-[var(--bz-text-1)] flex items-center gap-2">
              <Building2 className="w-4 h-4" /> Basic Information
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="md:col-span-2">
                <label className="block text-xs font-medium mb-1.5">Company Name *</label>
                <input type="text" value={formData.company_name} onChange={(e) => updateField('company_name', e.target.value)} className={inputClass} placeholder="e.g. PT Bali Investment Mandiri" required />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5">Company Type</label>
                <select value={formData.company_type} onChange={(e) => updateField('company_type', e.target.value)} className={inputClass}>
                  <option value="PT PMA">PT PMA</option>
                  <option value="PT Perorangan">PT Perorangan</option>
                  <option value="CV">CV</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5">KBLI Code</label>
                <input type="text" value={formData.kbli_code} onChange={(e) => updateField('kbli_code', e.target.value)} className={inputClass} placeholder="e.g. 68111" />
              </div>
            </div>
          </div>

          {/* Business IDs */}
          <div className="space-y-3 pt-4 border-t border-[var(--bz-border)]">
            <h4 className="text-sm font-medium text-[var(--bz-text-1)] flex items-center gap-2">
              <CreditCard className="w-4 h-4" /> Business Identification
            </h4>
            {/* NIB */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1.5">NIB (Business ID) <span className="text-[var(--bz-text-2)]">- Number</span></label>
                <input type="text" value={formData.nib} onChange={(e) => updateField('nib', e.target.value)} className={inputClass} placeholder="Nomor Induk Berusaha" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5">NIB Document <span className="text-[var(--bz-text-2)]">- Upload + OCR</span></label>
                <div className="flex items-center gap-2">
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => updateDocument('nib', e.target.files?.[0])} className="hidden" id="nib-doc-upload" />
                  <label htmlFor="nib-doc-upload" className="flex-1 px-3 py-2 rounded-lg border border-dashed border-[var(--bz-border)] bg-[var(--bz-surface)] cursor-pointer hover:border-[var(--accent)] transition-colors text-sm truncate">
                    {documents.nib ? documents.nib.name : 'Upload NIB file'}
                  </label>
                  {documents.nib && (
                    <>
                      <Button type="button" variant="outline" size="sm" className="gap-1 text-xs" onClick={extractNib} disabled={isExtractingNib}>
                        {isExtractingNib ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />} Extract
                      </Button>
                      <Button type="button" variant="ghost" size="sm" className="h-8 w-8 p-0 text-red-500" onClick={() => updateDocument('nib', undefined)}>
                        <X className="w-4 h-4" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
            {/* NPWP */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1.5">NPWP Company <span className="text-[var(--bz-text-2)]">- Number (auto from OCR)</span></label>
                <input type="text" value={formData.npwp_company} onChange={(e) => updateField('npwp_company', e.target.value)} className={inputClass} placeholder="Company Tax ID" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5">NPWP Document <span className="text-[var(--bz-text-2)]">- Upload + OCR</span></label>
                <div className="flex items-center gap-2">
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => updateDocument('npwp', e.target.files?.[0])} className="hidden" id="npwp-upload" />
                  <label htmlFor="npwp-upload" className="flex-1 px-3 py-2 rounded-lg border border-dashed border-[var(--bz-border)] bg-[var(--bz-surface)] cursor-pointer hover:border-[var(--accent)] transition-colors text-sm truncate">
                    {documents.npwp ? documents.npwp.name : 'Upload NPWP'}
                  </label>
                  {documents.npwp && (
                    <>
                      <Button type="button" variant="outline" size="sm" className="gap-1 text-xs" onClick={extractNpwp} disabled={isExtractingNpwp}>
                        {isExtractingNpwp ? <Loader2 className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />} Extract
                      </Button>
                      <Button type="button" variant="ghost" size="sm" className="h-8 w-8 p-0 text-red-500" onClick={() => updateDocument('npwp', undefined)}>
                        <X className="w-4 h-4" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Document Uploads */}
          <div className="space-y-3 pt-4 border-t border-[var(--bz-border)]">
            <h4 className="text-sm font-medium text-[var(--bz-text-1)] flex items-center gap-2">
              <Upload className="w-4 h-4" /> Document Uploads
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(['akta', 'sk', 'businessId', 'profilePerseroan'] as const).map((docType) => {
                const labels: Record<string, string> = { akta: 'AKTA', sk: 'SK', businessId: 'Business Identification', profilePerseroan: 'Profile Perseroan' };
                return (
                  <div key={docType}>
                    <label className="block text-xs font-medium mb-1.5">{labels[docType]}</label>
                    <div className="flex items-center gap-2">
                      <input type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => updateDocument(docType, e.target.files?.[0])} className="hidden" id={`${docType}-upload`} />
                      <label htmlFor={`${docType}-upload`} className="flex-1 px-3 py-2 rounded-lg border border-dashed border-[var(--bz-border)] bg-[var(--bz-surface)] cursor-pointer hover:border-[var(--accent)] transition-colors text-sm truncate">
                        {documents[docType] ? documents[docType]!.name : `Upload ${labels[docType]}`}
                      </label>
                      {documents[docType] && (
                        <Button type="button" variant="ghost" size="sm" className="h-8 w-8 p-0 text-red-500" onClick={() => updateDocument(docType, undefined)}>
                          <X className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Address */}
          <div className="space-y-3 pt-4 border-t border-[var(--bz-border)]">
            <h4 className="text-sm font-medium text-[var(--bz-text-1)] flex items-center gap-2">
              <MapPin className="w-4 h-4" /> Address
            </h4>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-1.5">Registered Address</label>
                <textarea value={formData.registered_address} onChange={(e) => updateField('registered_address', e.target.value)} className={inputClass} rows={2} placeholder="Full registered address" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1.5">City</label>
                  <input type="text" value={formData.city} onChange={(e) => updateField('city', e.target.value)} className={inputClass} placeholder="e.g. Denpasar" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5">Province</label>
                  <input type="text" value={formData.province} onChange={(e) => updateField('province', e.target.value)} className={inputClass} placeholder="e.g. Bali" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1.5">Email</label>
                  <input type="email" value={formData.company_email} onChange={(e) => updateField('company_email', e.target.value)} className={inputClass} placeholder="company@email.com" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5">Phone</label>
                <input type="tel" value={formData.company_phone} onChange={(e) => updateField('company_phone', e.target.value)} className={inputClass} placeholder="+62 xxx xxxx xxxx" />
              </div>
            </div>
          </div>

          {/* Client Link */}
          <div className="space-y-3 pt-4 border-t border-[var(--bz-border)]">
            <h4 className="text-sm font-medium text-[var(--bz-text-1)] flex items-center gap-2">
              <Users className="w-4 h-4" /> Client Association
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1.5">Role in Company</label>
                <select value={formData.role} onChange={(e) => updateField('role', e.target.value)} className={inputClass}>
                  <option value="Director">Director</option>
                  <option value="Commissioner">Commissioner</option>
                  <option value="Shareholder">Shareholder</option>
                  <option value="Employee">Employee</option>
                  <option value="Agent">Agent</option>
                  <option value="Beneficial_Owner">Beneficial Owner</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1.5">Ownership %</label>
                <input type="number" min="0" max="100" step="0.01" value={formData.ownership_percentage} onChange={(e) => updateField('ownership_percentage', e.target.value)} className={inputClass} placeholder="e.g. 51" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="is_primary" checked={formData.is_primary} onChange={(e) => updateField('is_primary', e.target.checked)} className="rounded border-[var(--bz-border)] bg-[var(--bz-surface)]" />
              <label htmlFor="is_primary" className="text-sm text-[var(--bz-text-1)]">Set as primary company for this client</label>
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-6 border-t border-[var(--bz-border)]">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating...</>) : (<><Plus className="w-4 h-4 mr-2" />Create Company</>)}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
