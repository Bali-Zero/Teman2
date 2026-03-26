'use client';

import React, { useState } from 'react';
import {
  User,
  Globe,
  Building2,
  DollarSign,
  Users,
  FileText,
  Plus,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
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

  // Compute expiry urgency for a document
  const getExpiryBadge = (doc: ClientDocument) => {
    if (!doc.expiry_date) return null;
    const daysLeft = Math.ceil((new Date(doc.expiry_date).getTime() - Date.now()) / 86400000);
    if (daysLeft < 0)
      return { label: `Expired ${Math.abs(daysLeft)}d ago`, cls: 'bg-red-500/20 text-red-400' };
    if (daysLeft === 0) return { label: 'Expires today', cls: 'bg-red-500/20 text-red-400' };
    if (daysLeft <= 30)
      return { label: `⏰ ${daysLeft}d left`, cls: 'bg-red-500/15 text-red-400' };
    if (daysLeft <= 90)
      return { label: `⏰ ${daysLeft}d left`, cls: 'bg-yellow-500/15 text-yellow-400' };
    if (daysLeft <= 365)
      return { label: `⏰ ${daysLeft}d left`, cls: 'bg-[var(--bz-base)] text-[var(--bz-text-2)]' };
    return {
      label: `${Math.floor(daysLeft / 30)}mo left`,
      cls: 'bg-[var(--bz-base)] text-[var(--bz-text-2)]',
    };
  };

  // Count expiring docs per category
  const getUrgentCount = (docs: ClientDocument[]) =>
    docs.filter((d) => {
      if (!d.expiry_date) return false;
      const days = Math.ceil((new Date(d.expiry_date).getTime() - Date.now()) / 86400000);
      return days <= 90;
    }).length;

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggleCollapse = (cat: string) => setCollapsed((prev) => ({ ...prev, [cat]: !prev[cat] }));

  // Total urgent docs across all categories
  const totalUrgent = documents.filter((d) => {
    if (!d.expiry_date) return false;
    return Math.ceil((new Date(d.expiry_date).getTime() - Date.now()) / 86400000) <= 90;
  }).length;

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
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--bz-text-1)]">Documents</h3>
          <p className="text-sm text-[var(--bz-text-2)]">
            {documents.length} docs · {sortedCategories.length} categories
            {totalUrgent > 0 && (
              <span className="ml-2 inline-flex items-center gap-1 text-orange-400 font-medium">
                <AlertTriangle className="w-3 h-3" />
                {totalUrgent} expiring soon
              </span>
            )}
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
        const urgentCount = getUrgentCount(catDocs);
        const isCollapsed = collapsed[cat];

        // Sort: urgent first, then by expiry date
        const sortedCatDocs = [...catDocs].sort((a, b) => {
          const aUrgent = a.expiry_date
            ? Math.ceil((new Date(a.expiry_date).getTime() - Date.now()) / 86400000)
            : 9999;
          const bUrgent = b.expiry_date
            ? Math.ceil((new Date(b.expiry_date).getTime() - Date.now()) / 86400000)
            : 9999;
          return aUrgent - bUrgent;
        });

        return (
          <div key={cat} className="space-y-1">
            <button
              onClick={() => toggleCollapse(cat)}
              className="w-full flex items-center gap-2 pb-1.5 border-b border-[var(--bz-border)] hover:border-[var(--bz-accent)]/40 transition-colors group"
            >
              {isCollapsed ? (
                <ChevronRight className="w-3.5 h-3.5 text-[var(--bz-text-2)] group-hover:text-[var(--bz-text-1)]" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-[var(--bz-text-2)] group-hover:text-[var(--bz-text-1)]" />
              )}
              <Icon className="w-4 h-4 text-[var(--bz-accent)]" />
              <h4 className="text-sm font-semibold text-[var(--bz-text-1)] capitalize">
                {categoryLabels[cat] || cat}
              </h4>
              <span className="text-xs text-[var(--bz-text-2)] bg-[var(--bz-surface)] px-2 py-0.5 rounded-full">
                {catDocs.length}
              </span>
              {urgentCount > 0 && (
                <span className="text-xs bg-orange-500/20 text-orange-400 px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
                  <AlertTriangle className="w-2.5 h-2.5" />
                  {urgentCount}
                </span>
              )}
            </button>
            {!isCollapsed && (
              <div className="space-y-1 pt-1">
                {sortedCatDocs.map((doc) => {
                  const badge = getExpiryBadge(doc);
                  const isUrgent =
                    doc.expiry_date &&
                    Math.ceil((new Date(doc.expiry_date).getTime() - Date.now()) / 86400000) <= 30;
                  return (
                    <div
                      key={doc.id}
                      className={`flex items-center justify-between rounded-lg border bg-[var(--bz-surface)] p-3 hover:bg-[var(--bz-surface)]/80 transition-colors ${
                        isUrgent ? 'border-red-500/30' : 'border-[var(--bz-border)]'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <FileText
                          className={`w-4 h-4 shrink-0 ${isUrgent ? 'text-red-400' : 'text-[var(--bz-text-2)]'}`}
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-[var(--bz-text-1)] truncate">
                            {doc.file_name || doc.document_type}
                          </p>
                          <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                            <span className="text-xs text-[var(--bz-text-2)] capitalize">
                              {doc.document_type?.replace(/_/g, ' ')}
                            </span>
                            {badge && (
                              <span
                                className={`text-xs px-1.5 py-0.5 rounded ${badge.cls}`}
                                title={doc.expiry_date ? `Expires: ${formatDate(doc.expiry_date)}` : undefined}
                              >
                                {badge.label}
                              </span>
                            )}
                            {doc.status === 'verified' && (
                              <span className="text-xs text-green-500">✓ Verified</span>
                            )}
                          </div>
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
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
