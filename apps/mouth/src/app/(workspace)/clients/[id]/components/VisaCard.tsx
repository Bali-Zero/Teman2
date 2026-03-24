'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  FileText,
  Loader2,
  Upload,
  Trash2,
  ExternalLink,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { fileToBase64 } from '@/lib/utils';
import type { ClientProfile, ClientDocument } from '@/lib/api/crm/crm.types';
import { extractDriveFileId, getDriveProxyUrl, getVisaAlertStatus } from './utils';

export function VisaCard({
  client,
  documents,
  activePractices,
  formatDate,
  formatCurrency,
  onRefresh,
  clientId,
}: {
  client: ClientProfile['client'];
  documents: ClientDocument[];
  activePractices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  onRefresh: () => Promise<void>;
  clientId: number;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [ocrPolling, setOcrPolling] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const hasTriggeredVisaOcr = useRef(false);

  // Poll OCR status after upload
  const pollOcrStatus = useCallback(async () => {
    setOcrPolling(true);
    let attempts = 0;
    const maxAttempts = 10;
    const poll = async () => {
      try {
        const status = (await api.request(`/api/crm/clients/${clientId}/ocr-status`)) as {
          pending_ocr: number;
        };
        if (status.pending_ocr === 0 || attempts >= maxAttempts) {
          setOcrPolling(false);
          await onRefresh();
          return;
        }
        attempts++;
        setTimeout(poll, 3000);
      } catch {
        setOcrPolling(false);
        await onRefresh();
      }
    };
    setTimeout(poll, 2000);
  }, [clientId, onRefresh]);

  // Find latest visa/KITAS document
  const visaDocs = documents.filter(
    (doc) =>
      doc.document_category === 'immigration' &&
      (doc.document_type?.toLowerCase().includes('visa') ||
        doc.document_type?.toLowerCase().includes('kitas') ||
        doc.document_type?.toLowerCase().includes('kitap') ||
        doc.document_type?.toLowerCase().includes('e-visa') ||
        doc.document_type?.toLowerCase().includes('evisa'))
  );

  const sortedVisaDocs = visaDocs.sort((a, b) => {
    if (!a.expiry_date) return 1;
    if (!b.expiry_date) return -1;
    return new Date(b.expiry_date).getTime() - new Date(a.expiry_date).getTime();
  });

  const latestVisa = sortedVisaDocs[0];

  // Find active visa process
  const visaProcess = activePractices.find(
    (p) =>
      p.practice_type_code?.toLowerCase().includes('visa') ||
      p.practice_type_code?.toLowerCase().includes('kitas') ||
      p.practice_type_code?.toLowerCase().includes('kitap') ||
      p.practice_type_name?.toLowerCase().includes('visa') ||
      p.practice_type_name?.toLowerCase().includes('kitas')
  );

  // Get visa alert status
  const visaAlert = getVisaAlertStatus(latestVisa?.expiry_date);

  // Get visa dates from document metadata or practice
  const visaStartDate = latestVisa?.issue_date || visaProcess?.start_date;
  const visaExpiryDate = latestVisa?.expiry_date;

  // Auto-extract visa dates via OCR when visa doc exists but no dates
  const handleExtractVisa = useCallback(async () => {
    if (!latestVisa?.google_drive_file_url || isExtracting) return;
    const fileId = extractDriveFileId(latestVisa.google_drive_file_url);
    if (!fileId) return;
    setIsExtracting(true);
    try {
      const response = (await api.post(`/api/crm/clients/${clientId}/extract-visa`, {
        file_id: fileId,
        doc_id: latestVisa.id,
      })) as {
        success: boolean;
        extracted?: {
          expiry_date?: string;
          issue_date?: string;
          visa_type?: string;
        };
      };
      if (response.success && response.extracted) {
        const details = [];
        if (response.extracted.visa_type) details.push(`Type: ${response.extracted.visa_type}`);
        if (response.extracted.issue_date) details.push(`Issue: ${response.extracted.issue_date}`);
        if (response.extracted.expiry_date)
          details.push(`Expiry: ${response.extracted.expiry_date}`);
        if (details.length > 0) {
          toast.success('Visa data extracted!', {
            description: details.join(' | '),
          });
        }
        await onRefresh();
      }
    } catch {
      // Silent fail for auto-extract
    } finally {
      setIsExtracting(false);
    }
  }, [latestVisa, isExtracting, clientId, onRefresh]);

  // Auto-trigger visa OCR when visa doc exists but no expiry date
  useEffect(() => {
    if (
      latestVisa?.google_drive_file_url &&
      !latestVisa?.expiry_date &&
      !isExtracting &&
      !hasTriggeredVisaOcr.current
    ) {
      hasTriggeredVisaOcr.current = true;
      handleExtractVisa();
    }
  }, [latestVisa, isExtracting, handleExtractVisa]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Invalid file type', {
        description: 'Please upload JPG, PNG, or PDF',
      });
      return;
    }

    // Validate file size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error('File too large', {
        description: 'Maximum file size is 10MB',
      });
      return;
    }

    setIsUploading(true);
    try {
      // Convert file to base64 using utility function
      const base64 = await fileToBase64(file);

      const response = (await api.post(`/api/crm/clients/${client.id}/documents/upload`, {
        file: base64,
        file_name: file.name,
        document_type: 'visa',
        mime_type: file.type,
      })) as {
        success: boolean;
        message?: string;
      };

      if (response.success) {
        toast.success('Visa uploaded — OCR in corso...');
        pollOcrStatus();
      } else {
        toast.error('Upload failed', { description: response.message });
      }
    } catch (err) {
      toast.error('Upload failed', { description: (err as Error).message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async () => {
    if (!latestVisa) return;

    if (!confirm('Delete visa document? This will mark it as deleted.')) {
      return;
    }

    setIsDeleting(true);
    try {
      await api.request(`/api/crm/documents/${latestVisa.id}`, {
        method: 'DELETE',
      });
      toast.success('Visa deleted');
      await onRefresh();
    } catch (err) {
      toast.error('Delete failed', { description: (err as Error).message });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      className="rounded-xl border shadow-xl backdrop-blur-xl transition-all duration-300 overflow-hidden flex flex-col h-full hover:shadow-2xl hover:-translate-y-1"
      style={{
        border: '1px solid rgba(255, 255, 255, 0.05)',
        background: 'rgba(32, 32, 36, 0.65)',
      }}
    >
      {/* OCR Processing Indicator */}
      {ocrPolling && (
        <div className="flex items-center gap-2 px-4 py-2 bg-blue-500/10 border-b border-blue-500/20 text-blue-400 text-xs">
          <Loader2 className="w-3 h-3 animate-spin" />
          OCR in corso...
        </div>
      )}
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255,255,255,0.05)' }}
      >
        <h3 className="text-base font-semibold text-[var(--bz-text-1)] flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Actual Visa
        </h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col">
        {visaProcess && !latestVisa?.google_drive_file_url ? (
          /* Visa in Process */
          <div className="flex-1 flex flex-col">
            <div className="aspect-[3/2] rounded-lg bg-blue-500/10 border-2 border-dashed border-blue-500/30 flex flex-col items-center justify-center gap-2">
              <Loader2 className="w-10 h-10 text-blue-400 animate-spin" />
              <p className="text-sm font-medium text-blue-400">Visa on process</p>
            </div>

            {/* Process Dates */}
            {visaProcess.start_date && (
              <div className="mt-3 space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--bz-text-2)]">Start:</span>
                  <span className="text-[var(--bz-text-1)]">
                    {formatDate(visaProcess.start_date)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--bz-text-2)]">Finish:</span>
                  <span className="text-[var(--bz-text-1)]">
                    {visaProcess.completion_date ? formatDate(visaProcess.completion_date) : 'TBD'}
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : latestVisa?.google_drive_file_url ? (
          <div className="space-y-3 flex-1 flex flex-col">
            {/* Visa Image */}
            <a
              href={latestVisa.google_drive_file_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block relative group"
            >
              <div className="aspect-[3/2] rounded-lg overflow-hidden border-2 border-dashed border-[var(--bz-border)] bg-[var(--bz-base)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={
                    getDriveProxyUrl(latestVisa.google_drive_file_url) ||
                    latestVisa.google_drive_file_url
                  }
                  alt="Visa"
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    if (latestVisa.google_drive_file_url) {
                      (e.target as HTMLImageElement).src = latestVisa.google_drive_file_url.replace(
                        '/view',
                        '/preview'
                      );
                    }
                  }}
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                  <ExternalLink className="w-5 h-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            </a>

            {/* Visa Data with Start/Finish/Exp */}
            <div className="space-y-2">
              {/* Visa Type */}
              {latestVisa.document_type && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--bz-text-2)]">Type:</span>
                  <span className="font-medium text-[var(--bz-text-1)]">
                    {latestVisa.document_type}
                  </span>
                </div>
              )}

              {/* Start Date */}
              {visaStartDate && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--bz-text-2)]">Start:</span>
                  <span className="text-[var(--bz-text-1)]">{formatDate(visaStartDate)}</span>
                </div>
              )}

              {/* Expiry Date with Alert */}
              {visaExpiryDate && (
                <div
                  className={`rounded-lg p-2 ${
                    visaAlert.alertLevel === 'critical'
                      ? 'bg-red-500 text-white border border-red-600 animate-pulse'
                      : visaAlert.alertLevel === 'warning'
                        ? 'bg-yellow-500 text-black border border-yellow-600'
                        : 'bg-[var(--bz-base)] border border-[var(--bz-border)]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-[10px] uppercase tracking-wider ${
                        visaAlert.alertLevel === 'critical' || visaAlert.alertLevel === 'warning'
                          ? 'opacity-90'
                          : 'text-[var(--bz-text-2)]'
                      }`}
                    >
                      Exp Visa:
                    </span>
                    <span
                      className={`text-xs font-semibold ${
                        visaAlert.alertLevel === 'critical' || visaAlert.alertLevel === 'warning'
                          ? ''
                          : 'text-[var(--bz-text-1)]'
                      }`}
                    >
                      {formatDate(visaExpiryDate)}
                    </span>
                  </div>

                  {/* Alert Messages */}
                  {visaAlert.alertLevel === 'critical' && (
                    <div className="mt-1 text-[10px] font-bold">
                      🚨 URGENT: Plan renewal or communicate departure!
                    </div>
                  )}
                  {visaAlert.alertLevel === 'warning' && (
                    <div className="mt-1 text-[10px]">⚠️ Start planning your visa renewal</div>
                  )}
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-2 pt-2 mt-auto">
              <Button
                variant="outline"
                size="sm"
                onClick={handleExtractVisa}
                disabled={isExtracting}
              >
                {isExtracting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <FileText className="w-4 h-4 mr-2" />
                )}
                {isExtracting ? 'Extracting...' : 'Extract'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDelete}
                disabled={isDeleting}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4 mr-2" />
                )}
                {isDeleting ? '...' : 'Del'}
              </Button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col">
            <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-[var(--bz-border)] flex flex-col items-center justify-center gap-2 bg-[var(--bz-base)]/50">
              <FileText className="w-10 h-10 text-[var(--bz-text-2)] opacity-50" />
              <span className="text-sm text-[var(--bz-text-2)]">No visa</span>
            </div>

            {/* Upload Button */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,application/pdf"
              onChange={handleFileUpload}
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-3"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 mr-2" />
              )}
              {isUploading ? 'Uploading...' : 'Upload Visa'}
            </Button>
          </div>
        )}

        {/* Caption */}
        <p className="text-xs text-[var(--bz-text-2)] text-center mt-3">
          {latestVisa?.google_drive_file_url
            ? `${latestVisa.document_type || 'Visa'} • ${visaAlert.alertLevel !== 'ok' ? '⚠️ Action needed' : 'Valid'}`
            : 'Upload visa (JPG, PNG, PDF - max 10MB)'}
        </p>
      </div>
    </div>
  );
}
