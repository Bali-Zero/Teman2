'use client';

import React from 'react';
import {
  Globe,
  Plus,
  Calendar,
  Edit2,
  Trash2,
  Download,
  FileText,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { ClientDocument } from '@/lib/api/crm/crm.types';
import { ALERT_COLORS } from './constants';
import { extractDriveFileId, getDriveProxyUrl } from './utils';

export function ImmigrationTab({
  clientId,
  documents,
  formatDate,
  onAddClick,
  onEditClick,
  onRefresh,
}: {
  clientId: number;
  documents: ClientDocument[];
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onEditClick: (doc: ClientDocument) => void;
  onRefresh: () => void;
}) {
  const handleDelete = async (docId: number, fileName: string) => {
    if (confirm(`Archive document "${fileName || 'Document'}"?`)) {
      try {
        await api.crm.deleteDocument(clientId, docId);
        toast.success('Document archived');
        onRefresh();
      } catch (err) {
        toast.error('Error', { description: (err as Error).message });
      }
    }
  };

  // Categorize immigration documents
  const immigrationDocs = documents.filter(
    (d) =>
      d.document_category === 'immigration' ||
      d.document_type?.toLowerCase().includes('kitas') ||
      d.document_type?.toLowerCase().includes('kitap') ||
      d.document_type?.toLowerCase().includes('visa') ||
      d.document_type?.toLowerCase().includes('permit') ||
      d.document_type?.toLowerCase().includes('imta') ||
      d.document_type?.toLowerCase().includes('rptka') ||
      d.document_type?.toLowerCase().includes('evisa') ||
      d.document_type?.toLowerCase().includes('voa')
  );

  // Sort: most recent expiry first, then by type
  const sortedDocs = [...immigrationDocs].sort((a, b) => {
    if (a.expiry_date && b.expiry_date)
      return new Date(b.expiry_date).getTime() - new Date(a.expiry_date).getTime();
    if (a.expiry_date) return -1;
    return 1;
  });

  // Actual visa = most recent non-expired kitas/kitap/visa
  const now = new Date();
  const actualVisa = sortedDocs.find(
    (d) =>
      (d.document_type?.toLowerCase().includes('kitas') ||
        d.document_type?.toLowerCase().includes('kitap') ||
        d.document_type?.toLowerCase().includes('visa') ||
        d.document_type?.toLowerCase().includes('evisa')) &&
      (!d.expiry_date || new Date(d.expiry_date) > new Date(now.getTime() - 30 * 86400000)) // allow 30 days grace
  );

  // Previous visas = expired kitas/kitap/visa (not the actual one)
  const previousVisas = sortedDocs.filter(
    (d) =>
      d !== actualVisa &&
      (d.document_type?.toLowerCase().includes('kitas') ||
        d.document_type?.toLowerCase().includes('kitap') ||
        d.document_type?.toLowerCase().includes('visa') ||
        d.document_type?.toLowerCase().includes('evisa') ||
        d.document_type?.toLowerCase().includes('voa'))
  );

  // Working permits
  const workingPermits = sortedDocs.filter(
    (d) =>
      d.document_type?.toLowerCase().includes('permit') ||
      d.document_type?.toLowerCase().includes('imta') ||
      d.document_type?.toLowerCase().includes('rptka')
  );

  // Other immigration docs (not in above categories)
  const otherDocs = sortedDocs.filter(
    (d) => d !== actualVisa && !previousVisas.includes(d) && !workingPermits.includes(d)
  );

  const renderDocCard = (doc: ClientDocument) => (
    <div
      key={doc.id}
      className="rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(32,32,36,0.6)] backdrop-blur-md shadow-2xl overflow-hidden group"
    >
      {doc.google_drive_file_url && (
        <div className="relative">
          <div
            className={`aspect-[3/2] overflow-hidden border-b bg-[var(--bz-base)] ${
              doc.alert_color === 'expired' || doc.alert_color === 'red'
                ? 'border-red-500/50'
                : doc.alert_color === 'yellow'
                  ? 'border-yellow-500/50'
                  : 'border-[var(--bz-border)]'
            }`}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={getDriveProxyUrl(doc.google_drive_file_url) || doc.google_drive_file_url}
              alt={doc.document_type}
              className="w-full h-full object-contain"
              onError={(e) => {
                const img = e.target as HTMLImageElement;
                // Only attempt fallback once to prevent infinite error loop
                if (!img.dataset.fallbackAttempted && doc.google_drive_file_url) {
                  img.dataset.fallbackAttempted = 'true';
                  img.src = doc.google_drive_file_url.replace('/view', '/preview');
                } else {
                  img.style.display = 'none';
                }
              }}
            />
          </div>
        </div>
      )}
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-[var(--bz-text-1)] capitalize">
            {doc.document_type.replace(/_/g, ' ')}
          </span>
          <div className="flex items-center gap-1">
            {doc.google_drive_file_url && (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => {
                  const fileId = extractDriveFileId(doc.google_drive_file_url!);
                  if (fileId) {
                    const link = document.createElement('a');
                    link.href = `/api/documents/proxy/${fileId}`;
                    link.download = doc.file_name || `${doc.document_type}.pdf`;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                  }
                }}
              >
                <Download className="w-3 h-3" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={() => onEditClick(doc)}
            >
              <Edit2 className="w-3 h-3" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-red-400 hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
              onClick={() => handleDelete(doc.id, doc.file_name || doc.document_type)}
            >
              <Trash2 className="w-3 h-3" />
            </Button>
          </div>
        </div>
        {doc.file_name && (
          <p className="text-xs text-[var(--bz-text-2)] truncate mb-1" title={doc.file_name}>
            {doc.file_name}
          </p>
        )}
        {doc.expiry_date && (
          <div
            className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${ALERT_COLORS[doc.alert_color || 'green']}`}
          >
            <Calendar className="w-3 h-3" />
            {doc.alert_color === 'expired' ? 'Expired' : `Expires: ${formatDate(doc.expiry_date)}`}
          </div>
        )}
        {doc.family_member_name && (
          <p className="text-xs text-[var(--bz-text-2)] mt-1">{doc.family_member_name}</p>
        )}
      </div>
    </div>
  );

  const sections = [
    {
      title: 'Actual Visa',
      docs: actualVisa ? [actualVisa] : [],
      color: 'bg-blue-500/20 text-blue-400',
    },
    {
      title: 'Previous Visas',
      docs: previousVisas,
      color: 'bg-gray-500/20 text-gray-400',
    },
    {
      title: 'Working Permit',
      docs: workingPermits,
      color: 'bg-purple-500/20 text-purple-400',
    },
    {
      title: 'Other',
      docs: otherDocs,
      color: 'bg-orange-500/20 text-orange-400',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">Immigration</h3>
        <Button size="sm" className="gap-2" onClick={onAddClick}>
          <Plus className="w-4 h-4" />
          Add Document
        </Button>
      </div>

      {immigrationDocs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-12 text-center shadow-xl">
          <Globe className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
          <p className="text-[var(--bz-text-2)]">No immigration documents yet</p>
          <p className="text-sm text-[var(--bz-text-2)] mt-1">
            Upload KITAS, visa, or working permit documents
          </p>
        </div>
      ) : (
        sections.map(({ title, docs: sectionDocs, color }) => {
          if (sectionDocs.length === 0) return null;
          return (
            <div key={title} className="space-y-3">
              <h4 className="font-medium text-[var(--bz-text-1)] flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${color}`}>{title}</span>
                <span className="text-[var(--bz-text-2)]">({sectionDocs.length})</span>
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {sectionDocs.map(renderDocCard)}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
