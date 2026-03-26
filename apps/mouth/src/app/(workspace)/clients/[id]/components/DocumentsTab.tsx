'use client';

import React from 'react';
import {
  User,
  Globe,
  Building2,
  DollarSign,
  Users,
  FileText,
  Plus,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ClientDocument } from '@/lib/api/crm/crm.types';

export function DocumentsTab({
  clientId,
  documents,
  documentsByCategory,
  formatDate,
  onAddClick,
  onEditClick,
  onRefresh,
}: {
  clientId: number;
  documents: ClientDocument[];
  documentsByCategory: Record<string, ClientDocument[]>;
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onEditClick: (doc: ClientDocument) => void;
  onRefresh: () => Promise<void>;
}) {
  const categoryLabels: Record<string, string> = {
    immigration: 'Immigration',
    pma: 'Company',
    tax: 'Tax',
    personal: 'Personal',
    family: 'Family',
    other: 'Other',
  };

  const categoryIcons: Record<string, React.ElementType> = {
    immigration: Globe,
    pma: Building2,
    tax: DollarSign,
    personal: User,
    family: Users,
    other: FileText,
  };

  const sortedCategories = Object.keys(documentsByCategory).sort((a, b) => {
    const order = ['immigration', 'pma', 'tax', 'personal', 'family', 'other'];
    return order.indexOf(a) - order.indexOf(b);
  });

  if (documents.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[rgba(255,255,255,0.1)] bg-[rgba(26,26,30,0.5)] backdrop-blur-sm p-12 text-center shadow-xl">
        <FileText className="w-12 h-12 mx-auto text-[var(--bz-text-2)] mb-3 opacity-50" />
        <p className="text-[var(--bz-text-2)]">No documents yet</p>
        <p className="text-sm text-[var(--bz-text-2)] mt-1 mb-4">
          Upload passport, visa, or company documents
        </p>
        <Button size="sm" onClick={onAddClick} className="gap-2">
          <Plus className="w-4 h-4" />
          Add Document
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">Documents</h3>
          <p className="text-sm text-[var(--bz-text-2)]">
            {documents.length} documents across {sortedCategories.length} categories
          </p>
        </div>
        <Button size="sm" onClick={onAddClick} className="gap-2">
          <Plus className="w-4 h-4" />
          Add Document
        </Button>
      </div>

      {sortedCategories.map((cat) => {
        const catDocs = documentsByCategory[cat];
        const Icon = categoryIcons[cat] || FileText;
        return (
          <div key={cat} className="space-y-2">
            <div className="flex items-center gap-2 pb-1 border-b border-[var(--bz-border)]">
              <Icon className="w-4 h-4 text-[var(--bz-accent)]" />
              <h4 className="text-sm font-semibold text-[var(--bz-text-1)] capitalize">
                {categoryLabels[cat] || cat}
              </h4>
              <span className="text-xs text-[var(--bz-text-2)] bg-[var(--bz-surface)] px-2 py-0.5 rounded-full">
                {catDocs.length}
              </span>
            </div>
            <div className="space-y-1">
              {catDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] p-3 hover:bg-[var(--bz-surface)]/80 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="w-4 h-4 shrink-0 text-[var(--bz-text-2)]" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-[var(--bz-text-1)] truncate">
                        {doc.file_name || doc.document_type}
                      </p>
                      <p className="text-xs text-[var(--bz-text-2)] capitalize">
                        {doc.document_type?.replace(/_/g, ' ')}
                        {doc.expiry_date ? ` · Expires ${formatDate(doc.expiry_date)}` : ''}
                        {doc.status === 'verified' && (
                          <span className="ml-1 text-green-500">· ✓ Verified</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {doc.google_drive_file_url && (
                      <a
                        href={doc.google_drive_file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-[var(--bz-accent)] hover:underline px-2 py-1 rounded border border-[var(--bz-border)] hover:bg-[var(--bz-base)]"
                      >
                        View
                      </a>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => onEditClick(doc)}
                    >
                      Edit
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
