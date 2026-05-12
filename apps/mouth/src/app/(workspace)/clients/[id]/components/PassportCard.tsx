'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { CreditCard, FileText, Loader2, Upload, Download, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { logger } from '@/lib/logger';
import { api } from '@/lib/api';
import { fileToBase64 } from '@/lib/utils';
import type { ClientProfile, ClientDocument } from '@/lib/api/crm/crm.types';
import {
  extractDriveFileId,
  getDriveProxyUrl,
  getPassportValidityColor,
  isBirthdayToday,
} from './utils';

export function PassportCard({
  client,
  documents,
  formatDate,
  onRefresh,
  clientId,
}: {
  client: ClientProfile['client'];
  documents: ClientDocument[];
  formatDate: (d: string) => string;
  onRefresh: () => Promise<void>;
  clientId: number;
}) {
  const [isExtracting, setIsExtracting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [ocrPolling, setOcrPolling] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ocrTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ocrAbortedRef = useRef(false);

  // Cleanup OCR polling timers when component unmounts
  useEffect(() => {
    ocrAbortedRef.current = false;
    return () => {
      ocrAbortedRef.current = true;
      if (ocrTimerRef.current) clearTimeout(ocrTimerRef.current);
    };
  }, []);

  // Poll OCR status after upload/extract
  const pollOcrStatus = useCallback(async () => {
    setOcrPolling(true);
    let attempts = 0;
    const maxAttempts = 10; // 3s * 10 = 30s max
    const poll = async () => {
      if (ocrAbortedRef.current) return;
      try {
        const status = (await api.request(`/api/crm/clients/${clientId}/ocr-status`)) as {
          pending_ocr: number;
        };
        if (status.pending_ocr === 0 || attempts >= maxAttempts) {
          if (!ocrAbortedRef.current) {
            setOcrPolling(false);
            await onRefresh();
          }
          return;
        }
        attempts++;
        ocrTimerRef.current = setTimeout(poll, 3000);
      } catch {
        if (!ocrAbortedRef.current) {
          setOcrPolling(false);
          await onRefresh();
        }
      }
    };
    ocrTimerRef.current = setTimeout(poll, 2000); // Initial delay for OCR to start
  }, [clientId, onRefresh]);

  // Find passport document from documents — only the client's own passport (no family members)
  const passportDoc = documents.find(
    (doc) =>
      !doc.family_member_id &&
      (doc.document_type?.toLowerCase().includes('passport') ||
        (doc.document_category === 'personal' && doc.document_type?.toLowerCase() === 'passport'))
  );

  // Get passport validity color and alert level
  const passportValidity = getPassportValidityColor(client.passport_expiry);
  const passportImageUrl = passportDoc?.google_drive_file_url;
  const passportIsPdf =
    passportDoc?.file_name?.toLowerCase().endsWith('.pdf') ||
    passportImageUrl?.toLowerCase().includes('.pdf') ||
    passportDoc?.file_name?.toLowerCase().includes('.pdf');

  // Check if birthday today
  const isBirthday = isBirthdayToday(client.date_of_birth);

  // Convert Drive view URL to direct download URL
  const getDownloadUrl = (url: string) => {
    const fileId = extractDriveFileId(url);
    if (fileId) {
      return `/api/documents/proxy/${fileId}`;
    }
    return url;
  };

  const handleDownload = (e: React.MouseEvent) => {
    e.preventDefault();
    if (passportImageUrl) {
      const downloadUrl = getDownloadUrl(passportImageUrl);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `passport_${client.full_name?.replace(/\s+/g, '_') || 'document'}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  const isExtractingRef = useRef(false);

  const blobToBase64 = async (blob: Blob): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = reader.result as string;
        resolve(result.split(',')[1] ?? result);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

  // Enhanced OCR extraction with Gemini Vision
  const handleExtractData = useCallback(async () => {
    if (!passportImageUrl || isExtractingRef.current) return;
    const fileId = extractDriveFileId(passportImageUrl);
    if (!fileId) {
      toast.error('Invalid document URL');
      return;
    }
    setIsExtracting(true);
    isExtractingRef.current = true;
    setOcrError(null);
    try {
      const proxyUrl = getDriveProxyUrl(passportImageUrl, 'full');
      if (!proxyUrl) {
        throw new Error('Passport document cannot be proxied for OCR');
      }

      const fileResponse = await fetch(proxyUrl);
      if (!fileResponse.ok) {
        throw new Error(`Passport download failed (${fileResponse.status})`);
      }

      const blob = await fileResponse.blob();
      const imageBase64 = await blobToBase64(blob);
      const mimeType = blob.type || (passportIsPdf ? 'application/pdf' : 'image/jpeg');
      const response = await api.crm.extractPassportForClient(imageBase64, mimeType, client.id);

      if (response.success) {
        const details = [];
        if (response.passport_number) details.push(`Passport: ${response.passport_number}`);
        if (response.passport_expiry) details.push(`Expiry: ${response.passport_expiry}`);
        if (response.gender) details.push(`Gender: ${response.gender}`);
        if (response.birthplace) details.push(`Birthplace: ${response.birthplace}`);
        if (response.name_match === false) {
          toast.warning('Name mismatch', {
            description: 'Passport name differs from client record',
          });
        }
        toast.success('Passport data extracted!', {
          description: details.join(' | '),
        });
        await onRefresh();
      } else {
        toast.warning('OCR failed', {
          description: response.message || 'Could not extract passport data',
        });
      }
    } catch (err) {
      logger.error('Passport OCR failed', { metadata: { error: String(err) } });
      setOcrError('OCR failed. Click to retry.');
      toast.error('Extraction failed', { description: (err as Error).message });
    } finally {
      setIsExtracting(false);
      isExtractingRef.current = false;
    }
  }, [passportImageUrl, passportIsPdf, client.id, onRefresh]);

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
        document_type: 'passport',
        mime_type: file.type,
      })) as {
        success: boolean;
        message?: string;
      };

      if (response.success) {
        toast.success('Passport uploaded — OCR in corso...');
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

  const doDelete = async () => {
    if (!passportDoc) return;
    setIsDeleting(true);
    try {
      await api.request(`/api/crm/documents/${passportDoc.id}`, {
        method: 'DELETE',
      });
      toast.success('Passport deleted');
      await onRefresh();
    } catch (err) {
      toast.error('Delete failed', { description: (err as Error).message });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDelete = () => {
    if (!passportDoc) return;
    toast('Delete passport document? This will mark it as deleted.', {
      action: { label: 'Delete', onClick: () => void doDelete() },
      cancel: { label: 'Cancel', onClick: () => toast.dismiss() },
    });
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
          <CreditCard className="w-5 h-5" />
          Passport
        </h3>
        {/* Gender Badge */}
        {client.gender && (
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-bold ${
              client.gender === 'M'
                ? 'bg-blue-500/20 text-blue-400'
                : 'bg-pink-500/20 text-pink-400'
            }`}
          >
            {client.gender === 'M' ? 'M' : 'F'}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col">
        {passportImageUrl ? (
          <div className="space-y-3 flex-1 flex flex-col">
            <button
              onClick={handleDownload}
              className="w-full block relative group cursor-pointer"
              title="Click to download passport"
              aria-label="Download passport"
            >
              <div className="aspect-[3/2] rounded-lg overflow-hidden border-2 border-dashed border-[var(--bz-border)] bg-[var(--bz-base)]">
                {passportIsPdf ? (
                  <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-[var(--bz-text-2)]">
                    <FileText className="w-12 h-12 opacity-60" />
                    <span className="text-xs font-medium">PDF Document</span>
                    <span className="text-[10px] opacity-60">Click to download</span>
                  </div>
                ) : (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={getDriveProxyUrl(passportImageUrl) || passportImageUrl}
                    alt="Passport"
                    className="w-full h-full object-contain"
                    onError={(e) => {
                      // Fallback to Google preview if proxy fails
                      (e.target as HTMLImageElement).src = passportImageUrl.replace(
                        '/view',
                        '/preview'
                      );
                    }}
                  />
                )}
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center">
                  <div className="flex items-center gap-2 bg-white/90 rounded-lg px-3 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Download className="w-4 h-4 text-gray-700" />
                    <span className="text-sm font-medium text-gray-700">Download</span>
                  </div>
                </div>
              </div>
            </button>

            {/* Passport Data with Alerts */}
            <div className="space-y-2">
              {/* Passport Number */}
              {client.passport_number && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[var(--bz-text-2)]">Number:</span>
                  <span className="font-mono text-[var(--bz-text-1)]">
                    {client.passport_number}
                  </span>
                </div>
              )}

              {/* Expiry Date with Alert */}
              {client.passport_expiry && (
                <div
                  className={`rounded-lg p-2 ${passportValidity.bgClass} border ${
                    passportValidity.alertLevel === 'critical'
                      ? 'border-red-500/50 animate-pulse'
                      : passportValidity.alertLevel === 'warning'
                        ? 'border-yellow-500/50'
                        : 'border-transparent'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase tracking-wider opacity-80">Expiry:</span>
                    <div className="flex items-center gap-1.5">
                      <span className={`text-xs font-semibold ${passportValidity.textClass}`}>
                        {formatDate(client.passport_expiry)}
                      </span>
                      {(() => {
                        const days = Math.ceil(
                          (new Date(client.passport_expiry!).getTime() - Date.now()) / 86400000
                        );
                        const label =
                          days < 0
                            ? `Exp ${Math.abs(days)}d ago`
                            : days === 0
                              ? 'today'
                              : days <= 365
                                ? `⏰ ${days}d`
                                : `${Math.floor(days / 30)}mo`;
                        return (
                          <span
                            className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                              days < 0
                                ? 'bg-red-500/20 text-red-400'
                                : days < 30
                                  ? 'bg-red-500/15 text-red-400'
                                  : days < 180
                                    ? 'bg-yellow-500/20 text-yellow-400'
                                    : 'bg-green-500/10 text-green-400'
                            }`}
                          >
                            {label}
                          </span>
                        );
                      })()}
                    </div>
                  </div>

                  {/* Alert Messages */}
                  {passportValidity.alertLevel === 'warning' && (
                    <div className="mt-1 text-[10px] text-yellow-600 dark:text-yellow-300">
                      ⚠️ 13 month alert: Contact embassy soon
                    </div>
                  )}
                  {passportValidity.alertLevel === 'critical' && (
                    <div className="mt-1 text-[10px] text-red-600 dark:text-red-300 font-bold">
                      🚨 URGENT: Contact embassy immediately!
                    </div>
                  )}
                  {passportValidity.alertLevel === 'expired' && (
                    <div className="mt-1 text-[10px] text-red-600 dark:text-red-300 font-bold">
                      ⛔ PASSPORT EXPIRED!
                    </div>
                  )}
                </div>
              )}

              {/* Date of Birth with Birthday Glow */}
              {client.date_of_birth && (
                <div
                  className={`flex items-center justify-between text-xs p-2 rounded-lg transition-all duration-500 ${
                    isBirthday
                      ? 'bg-gradient-to-r from-yellow-300/40 via-amber-300/40 to-yellow-300/40 animate-pulse shadow-[0_0_15px_rgba(255,215,0,0.5)]'
                      : ''
                  }`}
                >
                  <span
                    className={`${isBirthday ? 'text-yellow-700 dark:text-yellow-300 font-semibold' : 'text-[var(--bz-text-2)]'}`}
                  >
                    {isBirthday ? '🎂 DOB:' : 'DOB:'}
                  </span>
                  <span
                    className={`${isBirthday ? 'font-bold text-yellow-700 dark:text-yellow-300' : 'text-[var(--bz-text-1)]'}`}
                  >
                    {formatDate(client.date_of_birth)}
                    {isBirthday && ' (Today!)'}
                  </span>
                </div>
              )}
            </div>

            {/* OCR Error Message */}
            {ocrError && <p className="text-xs text-red-400 text-center">{ocrError}</p>}

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-2 pt-2 mt-auto">
              <Button
                variant="outline"
                size="sm"
                onClick={handleExtractData}
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
            {/* Show extracted data if available, even without image */}
            {client.passport_number || client.passport_expiry || client.date_of_birth ? (
              <div className="space-y-3 flex-1">
                <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-[var(--bz-border)] flex flex-col items-center justify-center gap-1.5 bg-[var(--bz-base)]/50">
                  <CreditCard className="w-8 h-8 text-[var(--bz-text-2)] opacity-40" />
                  <span className="text-xs text-[var(--bz-text-2)]">No scan uploaded</span>
                  <span className="text-[10px] text-[var(--bz-text-2)] opacity-60">
                    Data extracted from records
                  </span>
                </div>

                {/* Passport Data from OCR/records */}
                <div className="space-y-2">
                  {client.passport_number && (
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[var(--bz-text-2)]">Number:</span>
                      <span className="font-mono text-[var(--bz-text-1)] font-semibold">
                        {client.passport_number}
                      </span>
                    </div>
                  )}
                  {client.passport_expiry && (
                    <div
                      className={`rounded-lg p-2 ${passportValidity.bgClass} border ${
                        passportValidity.alertLevel === 'critical'
                          ? 'border-red-500/50 animate-pulse'
                          : passportValidity.alertLevel === 'warning'
                            ? 'border-yellow-500/50'
                            : 'border-transparent'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] uppercase tracking-wider opacity-80">
                          Expiry:
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-xs font-semibold ${passportValidity.textClass}`}>
                            {formatDate(client.passport_expiry)}
                          </span>
                          {(() => {
                            const days = Math.ceil(
                              (new Date(client.passport_expiry!).getTime() - Date.now()) / 86400000
                            );
                            const label =
                              days < 0
                                ? `Exp ${Math.abs(days)}d ago`
                                : days === 0
                                  ? 'today'
                                  : days <= 365
                                    ? `⏰ ${days}d`
                                    : `${Math.floor(days / 30)}mo`;
                            return (
                              <span
                                className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                                  days < 0
                                    ? 'bg-red-500/20 text-red-400'
                                    : days < 30
                                      ? 'bg-red-500/15 text-red-400'
                                      : days < 180
                                        ? 'bg-yellow-500/20 text-yellow-400'
                                        : 'bg-green-500/10 text-green-400'
                                }`}
                              >
                                {label}
                              </span>
                            );
                          })()}
                        </div>
                      </div>
                      {passportValidity.alertLevel === 'expired' && (
                        <div className="mt-1 text-[10px] text-red-600 dark:text-red-300 font-bold">
                          ⛔ PASSPORT EXPIRED!
                        </div>
                      )}
                      {passportValidity.alertLevel === 'critical' && (
                        <div className="mt-1 text-[10px] text-red-600 dark:text-red-300 font-bold">
                          🚨 URGENT: Contact embassy immediately!
                        </div>
                      )}
                      {passportValidity.alertLevel === 'warning' && (
                        <div className="mt-1 text-[10px] text-yellow-600 dark:text-yellow-300">
                          ⚠️ Expiring soon
                        </div>
                      )}
                    </div>
                  )}
                  {client.date_of_birth && (
                    <div
                      className={`flex items-center justify-between text-xs p-2 rounded-lg transition-all duration-500 ${
                        isBirthday
                          ? 'bg-gradient-to-r from-yellow-300/40 via-amber-300/40 to-yellow-300/40 animate-pulse shadow-[0_0_15px_rgba(255,215,0,0.5)]'
                          : ''
                      }`}
                    >
                      <span
                        className={`${isBirthday ? 'text-yellow-700 dark:text-yellow-300 font-semibold' : 'text-[var(--bz-text-2)]'}`}
                      >
                        {isBirthday ? '🎂 DOB:' : 'DOB:'}
                      </span>
                      <span
                        className={`${isBirthday ? 'font-bold text-yellow-700 dark:text-yellow-300' : 'text-[var(--bz-text-1)]'}`}
                      >
                        {formatDate(client.date_of_birth)}
                        {isBirthday && ' (Today!)'}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-[var(--bz-border)] flex flex-col items-center justify-center gap-2 bg-[var(--bz-base)]/50">
                <CreditCard className="w-10 h-10 text-[var(--bz-text-2)] opacity-50" />
                <span className="text-sm text-[var(--bz-text-2)]">No passport</span>
              </div>
            )}

            {/* Upload Button */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,application/pdf"
              aria-label="Upload passport"
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
              {isUploading
                ? 'Uploading...'
                : passportImageUrl
                  ? 'Upload Passport'
                  : client.passport_number
                    ? 'Upload Scan'
                    : 'Upload Passport'}
            </Button>
          </div>
        )}

        {/* Caption */}
        <p className="text-xs text-[var(--bz-text-2)] text-center mt-3">
          {passportImageUrl
            ? `${client.passport_number || 'Passport'} • ${client.nationality || ''}`
            : 'Upload passport (JPG, PNG, PDF - max 10MB)'}
        </p>
      </div>
    </div>
  );
}
