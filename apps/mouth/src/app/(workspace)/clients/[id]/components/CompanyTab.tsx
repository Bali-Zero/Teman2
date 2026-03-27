'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Building2,
  FileText,
  Loader2,
  Upload,
  Download,
  Eye,
  CheckCircle2,
  Edit2,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { fileToBase64 } from '@/lib/utils';
import type { ClientProfile, ClientDocument, CompanyDocument } from '@/lib/api/crm/crm.types';

// ============================================
// COMPANY DOC UPLOAD (internal)
// ============================================
function CompanyDocUpload({
  clientId,
  companyId,
  companyName,
  docType,
  label,
  hint,
  existingDoc,
  onUploaded,
}: {
  clientId: number;
  companyId: number;
  companyName: string;
  docType: string;
  label: string;
  hint: string;
  existingDoc?: CompanyDocument | null;
  onUploaded?: () => void;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [ocrPolling, setOcrPolling] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ocrTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ocrAbortedRef = useRef(false);
  const onUploadedRef = useRef(onUploaded);
  onUploadedRef.current = onUploaded;

  useEffect(() => {
    ocrAbortedRef.current = false;
    return () => {
      ocrAbortedRef.current = true;
      if (ocrTimerRef.current) clearTimeout(ocrTimerRef.current);
    };
  }, []);

  const pollOcrStatus = useCallback(async () => {
    setOcrPolling(true);
    let attempts = 0;
    const poll = async () => {
      if (ocrAbortedRef.current) return;
      try {
        const status = (await api.request(`/api/crm/clients/${clientId}/ocr-status`)) as {
          pending_ocr: number;
        };
        if (status.pending_ocr === 0 || attempts >= 10) {
          if (!ocrAbortedRef.current) {
            setOcrPolling(false);
            onUploadedRef.current?.();
          }
          return;
        }
        attempts++;
        ocrTimerRef.current = setTimeout(poll, 3000);
      } catch {
        if (!ocrAbortedRef.current) setOcrPolling(false);
      }
    };
    ocrTimerRef.current = setTimeout(poll, 2000);
  }, [clientId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Invalid file type', {
        description: 'Please upload JPG, PNG, or PDF',
      });
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File too large', { description: 'Maximum 10MB' });
      return;
    }
    setIsUploading(true);
    try {
      const base64 = await fileToBase64(file);
      const response = (await api.post(`/api/crm/clients/${clientId}/documents/upload`, {
        file: base64,
        file_name: file.name,
        document_type: docType,
        document_category: 'pma',
        mime_type: file.type,
        company_id: companyId,
      })) as { success: boolean; message?: string };
      if (response.success) {
        setUploadedFile(file.name);
        toast.success(`${label} uploaded for ${companyName} — OCR in corso...`);
        pollOcrStatus();
      } else {
        toast.error('Upload failed', { description: response.message });
      }
    } catch (err) {
      toast.error('Upload failed', { description: (err as Error).message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const hasDoc = existingDoc?.google_drive_file_id || uploadedFile;

  const docIcon: Record<string, string> = {
    akta_pendirian: '\u{1F4DC}',
    npwp: '\u{1F3DB}\uFE0F',
    nib: '\u{1F4CB}',
    company_profile: '\u{1F3E2}',
    sk_decree: '\u2696\uFE0F',
  };

  return (
    <div
      className={`rounded-xl overflow-hidden transition-all ${
        hasDoc
          ? 'bg-gradient-to-br from-[var(--bz-base)] to-[var(--bz-surface)] border border-[var(--bz-border)] shadow-sm'
          : 'border border-dashed border-[var(--bz-border)] hover:border-[var(--bz-accent)]/40 bg-[var(--bz-base)]/50'
      }`}
    >
      {/* Top accent bar */}
      {hasDoc && <div className="h-1 bg-gradient-to-r from-green-500/60 to-emerald-500/30" />}

      <div className="p-3.5">
        <div className="flex items-start gap-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0 ${
              hasDoc ? 'bg-green-500/10' : 'bg-[var(--bz-text-2)]/5'
            }`}
          >
            {docIcon[docType] || '\u{1F4C4}'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-[var(--bz-text-1)]">{label}</span>
              {hasDoc ? (
                <CheckCircle2 className="w-4 h-4 text-green-400 flex-shrink-0" />
              ) : (
                <span className="text-[10px] text-[var(--bz-text-2)]">{hint}</span>
              )}
            </div>

            {/* Existing doc filename */}
            {existingDoc?.file_name && !uploadedFile && (
              <p className="text-[11px] text-[var(--bz-text-2)] truncate mt-0.5">
                {existingDoc.file_name}
              </p>
            )}
            {uploadedFile && (
              <p className="text-[11px] text-green-400 mt-0.5 truncate">{uploadedFile}</p>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-1.5 mt-3">
          {existingDoc?.google_drive_file_id && !uploadedFile && (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-xs h-7 px-2.5 flex-1 hover:bg-[var(--bz-accent)]/10 hover:text-[var(--bz-accent)]"
                onClick={() => {
                  window.open(`/api/documents/proxy/${existingDoc.google_drive_file_id}`, '_blank');
                }}
              >
                <Eye className="w-3 h-3" />
                View
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 text-xs h-7 px-2.5 flex-1 hover:bg-blue-500/10 hover:text-blue-400"
                onClick={() => {
                  window.open(`/api/documents/proxy/${existingDoc.google_drive_file_id}`, '_blank');
                }}
              >
                <Download className="w-3 h-3" />
                Download
              </Button>
            </>
          )}

          <input
            ref={fileInputRef}
            type="file"
            accept=".jpg,.jpeg,.png,.pdf"
            className="hidden"
            onChange={handleUpload}
            disabled={isUploading}
          />
          <Button
            variant="outline"
            size="sm"
            className={`gap-1.5 text-xs h-7 ${hasDoc ? 'px-2.5' : 'w-full px-3'}`}
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || ocrPolling}
          >
            {isUploading || ocrPolling ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Upload className="w-3 h-3" />
            )}
            {isUploading ? '...' : ocrPolling ? 'OCR...' : hasDoc ? '' : `Upload`}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// EDIT COMPANY MODAL (internal to CompanyTab)
// ============================================
function EditCompanyModal({
  companyId,
  initialData,
  onClose,
  onSave,
  formatDate,
}: {
  companyId: number;
  initialData: {
    company_name?: string;
    company_type?: string;
    kbli_code?: string;
    nib?: string;
    npwp_company?: string;
    registered_address?: string;
    office_address?: string;
    city?: string;
    province?: string;
    akta_pendirian_no?: string;
    akta_pendirian_date?: string;
    akta_perubahan_no?: string;
    akta_perubahan_date?: string;
    sk_menhumkam_no?: string;
    sk_menhumkam_date?: string;
    company_status?: string;
  };
  onClose: () => void;
  onSave: () => void;
  formatDate: (d: string) => string;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [form, setForm] = useState({
    company_name: initialData.company_name || '',
    company_type: initialData.company_type || 'PT PMA',
    kbli_code: initialData.kbli_code || '',
    nib: initialData.nib || '',
    npwp_company: initialData.npwp_company || '',
    registered_address: initialData.registered_address || initialData.office_address || '',
    city: initialData.city || '',
    province: initialData.province || '',
    akta_pendirian_no: initialData.akta_pendirian_no || '',
    akta_pendirian_date: initialData.akta_pendirian_date?.split('T')[0] || '',
    akta_perubahan_no: initialData.akta_perubahan_no || '',
    akta_perubahan_date: initialData.akta_perubahan_date?.split('T')[0] || '',
    sk_menhumkam_no: initialData.sk_menhumkam_no || '',
    sk_menhumkam_date: initialData.sk_menhumkam_date?.split('T')[0] || '',
    status: initialData.company_status || 'active',
  });

  const inputClass =
    'w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50';

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Only send non-empty fields
      const updates: Record<string, string> = {};
      Object.entries(form).forEach(([k, v]) => {
        if (v !== '') updates[k] = v;
      });
      await api.crm.updateCompany(companyId, updates);
      toast.success('Company updated');
      onSave();
    } catch (err) {
      toast.error('Failed to update company', {
        description: (err as Error).message,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-2xl rounded-2xl overflow-hidden shadow-2xl max-h-[90vh] flex flex-col"
        style={{
          background: 'var(--bz-card)',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-6 py-4 border-b"
          style={{ borderColor: 'rgba(255,255,255,0.06)' }}
        >
          <h2 className="text-lg font-semibold text-[var(--bz-text-1)]">Edit Company</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-white/10 text-[var(--bz-text-2)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-4">
          {/* Company Name + Type */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Company Name
              </label>
              <input
                className={inputClass}
                value={form.company_name}
                onChange={(e) => setForm((f) => ({ ...f, company_name: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Type
              </label>
              <select
                className={inputClass}
                value={form.company_type}
                onChange={(e) => setForm((f) => ({ ...f, company_type: e.target.value }))}
              >
                <option value="PT PMA">PT PMA</option>
                <option value="PT Perorangan">PT Perorangan</option>
                <option value="CV">CV</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          {/* KBLI + NIB + NPWP */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                KBLI Code
              </label>
              <input
                className={inputClass}
                value={form.kbli_code}
                placeholder="e.g. 56101"
                onChange={(e) => setForm((f) => ({ ...f, kbli_code: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                NIB
              </label>
              <input
                className={inputClass}
                value={form.nib}
                placeholder="Nomor Induk Berusaha"
                onChange={(e) => setForm((f) => ({ ...f, nib: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                NPWP
              </label>
              <input
                className={inputClass}
                value={form.npwp_company}
                placeholder="NPWP Perusahaan"
                onChange={(e) => setForm((f) => ({ ...f, npwp_company: e.target.value }))}
              />
            </div>
          </div>

          {/* Address */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-3 sm:col-span-1">
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Address
              </label>
              <input
                className={inputClass}
                value={form.registered_address}
                onChange={(e) => setForm((f) => ({ ...f, registered_address: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                City
              </label>
              <input
                className={inputClass}
                value={form.city}
                onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Province
              </label>
              <input
                className={inputClass}
                value={form.province}
                onChange={(e) => setForm((f) => ({ ...f, province: e.target.value }))}
              />
            </div>
          </div>

          {/* Akta Pendirian */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Pendirian No.
              </label>
              <input
                className={inputClass}
                value={form.akta_pendirian_no}
                onChange={(e) => setForm((f) => ({ ...f, akta_pendirian_no: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Pendirian Date
              </label>
              <input
                type="date"
                className={inputClass}
                value={form.akta_pendirian_date}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    akta_pendirian_date: e.target.value,
                  }))
                }
              />
            </div>
          </div>

          {/* Akta Perubahan */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Perubahan No.
              </label>
              <input
                className={inputClass}
                value={form.akta_perubahan_no}
                onChange={(e) => setForm((f) => ({ ...f, akta_perubahan_no: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                Akta Perubahan Date
              </label>
              <input
                type="date"
                className={inputClass}
                value={form.akta_perubahan_date}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    akta_perubahan_date: e.target.value,
                  }))
                }
              />
            </div>
          </div>

          {/* SK Kemenkumham */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                SK Kemenkumham No.
              </label>
              <input
                className={inputClass}
                value={form.sk_menhumkam_no}
                onChange={(e) => setForm((f) => ({ ...f, sk_menhumkam_no: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
                SK Date
              </label>
              <input
                type="date"
                className={inputClass}
                value={form.sk_menhumkam_date}
                onChange={(e) => setForm((f) => ({ ...f, sk_menhumkam_date: e.target.value }))}
              />
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-1 block">
              Status
            </label>
            <select
              className={inputClass}
              value={form.status}
              onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
            >
              <option value="active">Active</option>
              <option value="in_setup">In Setup</option>
              <option value="dormant">Dormant</option>
              <option value="dissolved">Dissolved</option>
            </select>
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-3 px-6 py-4 border-t"
          style={{ borderColor: 'rgba(255,255,255,0.06)' }}
        >
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-[var(--bz-border)] text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] hover:border-[var(--bz-text-2)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 text-sm rounded-lg bg-[var(--bz-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2 transition-opacity"
          >
            {isSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================
// COMPANY TAB (main export)
// ============================================
export function CompanyTab({
  clientId,
  client,
  documents,
  formatDate,
  onRefresh,
}: {
  clientId: number;
  client: ClientProfile['client'];
  documents: ClientDocument[];
  formatDate: (d: string) => string;
  onRefresh: () => Promise<void>;
}) {
  // Company docs from client's documents (category = pma)
  const pmaDocs = documents.filter((d) => d.document_category === 'pma');

  // Company data: try linked companies first, then fallback to search by name
  const [companyData, setCompanyData] = useState<{
    company_name: string;
    company_type: string;
    kbli_code?: string;
    kbli_description?: string;
    nib?: string;
    npwp_company?: string;
    akta_pendirian_no?: string;
    akta_pendirian_date?: string;
    akta_perubahan_no?: string;
    akta_perubahan_date?: string;
    sk_menhumkam_no?: string;
    sk_menhumkam_date?: string;
    registered_address?: string;
    office_address?: string;
    city?: string;
    province?: string;
    company_status?: string;
    shares_count?: number;
    share_nominal_value?: number;
    setup_progress?: number;
    company_id?: number;
  } | null>(null);

  const [associates, setAssociates] = useState<
    Array<{
      client_name?: string;
      role: string;
      ownership_percentage?: number;
      shares_count?: number;
    }>
  >([]);

  const [companyDocs, setCompanyDocs] = useState<CompanyDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditingCompany, setIsEditingCompany] = useState(false);
  const [reloadTrigger, setReloadTrigger] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadCompanyData() {
      try {
        // Step 1: Try linked companies
        const linked = await api.crm.getClientCompanies(clientId);
        if (!cancelled && linked.length > 0) {
          const co = linked[0];
          setCompanyData({
            company_name: co.company_name,
            company_type: co.company_type,
            kbli_code: co.kbli_code,
            kbli_description: co.kbli_description,
            nib: co.nib,
            npwp_company: co.npwp_company,
            akta_pendirian_no: co.akta_pendirian_no,
            akta_pendirian_date: co.akta_pendirian_date,
            akta_perubahan_no: co.akta_perubahan_no,
            akta_perubahan_date: co.akta_perubahan_date,
            sk_menhumkam_no: co.sk_menhumkam_no,
            sk_menhumkam_date: co.sk_menhumkam_date,
            registered_address: co.registered_address,
            office_address: co.office_address,
            city: co.city,
            province: co.province,
            company_status: co.company_status,
            shares_count: co.shares_count,
            share_nominal_value: co.share_nominal_value,
            setup_progress: co.setup_progress,
            company_id: co.company_id,
          });
          setAssociates(
            linked.map((l) => ({
              client_name: client.full_name,
              role: l.role,
              ownership_percentage: l.ownership_percentage,
              shares_count: l.shares_count,
            }))
          );
          // Load company documents if we have a company_id
          if (co.company_id) {
            api.crm
              .getCompanyDocuments(co.company_id)
              .then((docs) => !cancelled && setCompanyDocs(docs))
              .catch((err) => {
                toast.error('Failed to load company documents', {
                  description: (err as Error).message,
                });
              });
          }
          return;
        }

        // Step 2: Fallback — search by client.company_name
        if (client.company_name) {
          const found = await api.crm.searchCompanyByName(client.company_name);
          if (!cancelled && found) {
            setCompanyData({
              company_name: found.company_name,
              company_type: found.company_type,
              kbli_code: found.kbli_code,
              kbli_description: found.kbli_description,
              nib: found.nib,
              npwp_company: found.npwp_company,
              akta_pendirian_no: found.akta_pendirian_no,
              akta_pendirian_date: found.akta_pendirian_date,
              akta_perubahan_no: found.akta_perubahan_no,
              akta_perubahan_date: found.akta_perubahan_date,
              sk_menhumkam_no: found.sk_menhumkam_no,
              sk_menhumkam_date: found.sk_menhumkam_date,
              registered_address: found.registered_address,
              office_address: found.office_address,
              city: found.city,
              province: found.province,
              company_status: found.status,
              company_id: found.id,
            });
            if (found.associates?.length) {
              setAssociates(
                found.associates.map((a) => ({
                  client_name: a.client_name,
                  role: a.role,
                  ownership_percentage: a.ownership_percentage,
                  shares_count: a.shares_count,
                }))
              );
            }
            // Load company documents
            api.crm
              .getCompanyDocuments(found.id)
              .then((docs) => !cancelled && setCompanyDocs(docs))
              .catch((err) => {
                toast.error('Failed to load company documents', {
                  description: (err as Error).message,
                });
              });
            return;
          }
        }

        // Step 3: No company data found — companyData stays null
      } catch (err) {
        if (!cancelled) {
          toast.error('Failed to load company data', {
            description: (err as Error).message,
          });
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadCompanyData();
    return () => {
      cancelled = true;
    };
  }, [clientId, client.company_name, client.full_name, reloadTrigger]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--bz-text-2)]" />
      </div>
    );
  }

  const hasCompanyName = !!client.company_name;
  const hasAnyDoc = pmaDocs.length > 0;

  if (!companyData && !hasCompanyName && !hasAnyDoc) {
    return (
      <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] p-12 text-center">
        <Building2 className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
        <p className="text-[var(--bz-text-2)]">No company information</p>
      </div>
    );
  }

  const co = companyData;

  // Format capital
  const formatCapital = (shares?: number, nominal?: number) => {
    if (!shares) return null;
    const nom = nominal || 1000000;
    const total = shares * nom;
    if (total >= 1e12) return `Rp ${(total / 1e12).toFixed(total % 1e12 === 0 ? 0 : 1)}T`;
    if (total >= 1e9) return `Rp ${(total / 1e9).toFixed(total % 1e9 === 0 ? 0 : 1)}B`;
    if (total >= 1e6) return `Rp ${(total / 1e6).toFixed(0)}M`;
    return `Rp ${total.toLocaleString('en-US')}`;
  };

  const companyName = co?.company_name || client.company_name || 'Company';
  const companyType = co?.company_type || '';
  const capital = formatCapital(co?.shares_count, co?.share_nominal_value);

  // Merge client pma docs + company docs for the strip
  const allDocs = [
    ...pmaDocs.map((d) => ({
      key: `client-${d.id}`,
      name: d.file_name || d.document_type,
      url: d.google_drive_file_url,
      type: d.document_type,
    })),
    ...companyDocs
      .filter((cd) => cd.google_drive_file_url || cd.google_drive_file_id)
      .map((cd) => ({
        key: `company-${cd.id}`,
        name: cd.file_name || cd.document_type,
        url:
          cd.google_drive_file_url ||
          (cd.google_drive_file_id
            ? `https://drive.google.com/file/d/${cd.google_drive_file_id}/view`
            : undefined),
        type: cd.document_type,
      })),
  ];

  // Determine founding year
  const foundingYear = co?.akta_pendirian_date
    ? new Date(co.akta_pendirian_date).getFullYear()
    : co?.sk_menhumkam_date
      ? new Date(co.sk_menhumkam_date).getFullYear()
      : null;

  // Address string
  const addressStr = [co?.registered_address || co?.office_address, co?.city, co?.province]
    .filter(Boolean)
    .join(', ');

  return (
    <div className="space-y-5">
      {/* COMPANY CARD */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          border: '1px solid rgba(255,255,255,0.06)',
          background: 'rgba(32,32,36,0.7)',
        }}
      >
        {/* Header band */}
        <div className="px-6 py-5 bg-gradient-to-r from-purple-500/8 to-blue-500/8">
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center shrink-0">
              <Building2 className="w-7 h-7 text-purple-400" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-bold text-[var(--bz-text-1)] truncate">
                  {companyName}
                </h3>
                {co?.company_id && (
                  <button
                    onClick={() => setIsEditingCompany(true)}
                    className="shrink-0 p-1 rounded hover:bg-white/10 text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] transition-colors"
                    title="Edit company"
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {companyType && (
                  <span className="px-2 py-0.5 rounded text-xs bg-purple-500/20 text-purple-400 font-medium">
                    {companyType}
                  </span>
                )}
                {(co?.company_status || 'active') !== 'dissolved' && (
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      (co?.company_status || 'active') === 'active'
                        ? 'bg-green-500/20 text-green-400'
                        : (co?.company_status || '') === 'in_setup'
                          ? 'bg-yellow-500/20 text-yellow-400'
                          : 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {(co?.company_status || 'active').replace(/_/g, ' ')}
                  </span>
                )}
                {foundingYear && (
                  <span className="text-xs text-[var(--bz-text-2)]">Est. {foundingYear}</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Info grid */}
        <div className="px-6 py-4 space-y-4">
          {/* Row 1: KBLI + NIB + NPWP */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-0.5">
                KBLI
              </p>
              <p className="text-sm text-[var(--bz-text-1)] font-medium font-mono">
                {co?.kbli_code || '\u2014'}
              </p>
              {co?.kbli_description && (
                <p className="text-xs text-[var(--bz-text-2)] truncate">{co.kbli_description}</p>
              )}
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-0.5">
                NIB
              </p>
              <p className="text-sm text-[var(--bz-text-1)] font-mono">{co?.nib || '\u2014'}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-0.5">
                NPWP
              </p>
              <p className="text-sm text-[var(--bz-text-1)] font-mono">
                {co?.npwp_company || '\u2014'}
              </p>
            </div>
          </div>

          {/* Row 2: Address + Capital */}
          <div className="grid grid-cols-2 gap-4">
            {addressStr && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-0.5">
                  Address
                </p>
                <p className="text-sm text-[var(--bz-text-1)]">{addressStr}</p>
              </div>
            )}
            {capital && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-0.5">
                  Capital
                </p>
                <p className="text-sm text-[var(--bz-text-1)] font-semibold">{capital}</p>
                {co?.shares_count && (
                  <p className="text-xs text-[var(--bz-text-2)]">
                    {co.shares_count.toLocaleString('en-US')} shares
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Shareholders */}
          {associates.length > 0 && (
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] mb-2">
                Shareholders
              </p>
              <div className="space-y-1.5">
                {associates.map((a, i) => (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-[var(--bz-text-1)]">
                      {a.role || 'Shareholder'} —{' '}
                      <span className="font-medium">{a.client_name || client.full_name}</span>
                    </span>
                    <span className="text-[var(--bz-text-2)]">
                      {a.ownership_percentage ? `${a.ownership_percentage}%` : ''}
                      {a.shares_count ? ` · ${a.shares_count.toLocaleString('en-US')} shares` : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Akta & SK */}
          {(co?.akta_pendirian_no || co?.akta_perubahan_no || co?.sk_menhumkam_no) && (
            <div className="pt-3 border-t border-[var(--bz-border)]">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                {co?.akta_pendirian_no && (
                  <div>
                    <span className="text-[var(--bz-text-2)]">Akta Pendirian</span>
                    <p className="text-[var(--bz-text-1)] font-mono">No. {co.akta_pendirian_no}</p>
                    {co.akta_pendirian_date && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <p className="text-[var(--bz-text-2)]">
                          {formatDate(co.akta_pendirian_date)}
                        </p>
                        {(() => {
                          const ageDays = Math.floor(
                            (Date.now() - new Date(co.akta_pendirian_date!).getTime()) / 86400000
                          );
                          if (ageDays < 30) return null;
                          const label =
                            ageDays >= 365
                              ? `${Math.floor(ageDays / 365)}y old`
                              : `${Math.floor(ageDays / 30)}mo old`;
                          return (
                            <span
                              className="text-[9px] px-1 py-0.5 rounded tabular-nums"
                              style={{
                                background: 'rgba(255,255,255,0.04)',
                                color: 'var(--bz-text-3)',
                              }}
                            >
                              {label}
                            </span>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                )}
                {co?.akta_perubahan_no && (
                  <div>
                    <span className="text-[var(--bz-text-2)]">Akta Perubahan</span>
                    <p className="text-[var(--bz-text-1)] font-mono">No. {co.akta_perubahan_no}</p>
                    {co.akta_perubahan_date && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <p className="text-[var(--bz-text-2)]">
                          {formatDate(co.akta_perubahan_date)}
                        </p>
                        {(() => {
                          const ageDays = Math.floor(
                            (Date.now() - new Date(co.akta_perubahan_date!).getTime()) / 86400000
                          );
                          if (ageDays < 30) return null;
                          const label =
                            ageDays >= 365
                              ? `${Math.floor(ageDays / 365)}y ago`
                              : `${Math.floor(ageDays / 30)}mo ago`;
                          return (
                            <span
                              className="text-[9px] px-1 py-0.5 rounded tabular-nums"
                              style={{
                                background: 'rgba(255,255,255,0.04)',
                                color: 'var(--bz-text-3)',
                              }}
                            >
                              {label}
                            </span>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                )}
                {co?.sk_menhumkam_no && (
                  <div>
                    <span className="text-[var(--bz-text-2)]">SK Kemenkumham</span>
                    <p className="text-[var(--bz-text-1)] font-mono">{co.sk_menhumkam_no}</p>
                    {co.sk_menhumkam_date && (
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <p className="text-[var(--bz-text-2)]">
                          {formatDate(co.sk_menhumkam_date)}
                        </p>
                        {(() => {
                          const ageDays = Math.floor(
                            (Date.now() - new Date(co.sk_menhumkam_date!).getTime()) / 86400000
                          );
                          if (ageDays < 30) return null;
                          const label =
                            ageDays >= 365
                              ? `${Math.floor(ageDays / 365)}y old`
                              : `${Math.floor(ageDays / 30)}mo old`;
                          return (
                            <span
                              className="text-[9px] px-1 py-0.5 rounded tabular-nums"
                              style={{
                                background: 'rgba(255,255,255,0.04)',
                                color: 'var(--bz-text-3)',
                              }}
                            >
                              {label}
                            </span>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Documents strip */}
        {allDocs.length > 0 && (
          <div className="px-6 py-3 border-t border-[var(--bz-border)] bg-[rgba(0,0,0,0.15)]">
            <div className="flex items-center gap-4">
              <span className="text-[10px] uppercase tracking-wider text-[var(--bz-text-2)] shrink-0">
                Documents
              </span>
              <div className="flex items-center gap-2 overflow-x-auto">
                {allDocs.map((doc) => (
                  <a
                    key={doc.key}
                    href={doc.url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={doc.name}
                    className="shrink-0 w-10 h-10 rounded border border-[var(--bz-border)] overflow-hidden bg-[var(--bz-base)] hover:border-[var(--bz-accent)] transition-colors flex items-center justify-center flex-col gap-1"
                  >
                    <FileText className="w-4 h-4 text-[var(--bz-text-2)]" />
                    <span className="text-[8px] text-[var(--bz-text-2)] truncate max-w-[36px] text-center">
                      {doc.type}
                    </span>
                  </a>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Edit Company Modal */}
      {isEditingCompany && co?.company_id && (
        <EditCompanyModal
          companyId={co.company_id}
          initialData={co}
          onClose={() => setIsEditingCompany(false)}
          onSave={() => {
            setIsEditingCompany(false);
            setReloadTrigger((t) => t + 1);
          }}
          formatDate={formatDate}
        />
      )}
    </div>
  );
}
