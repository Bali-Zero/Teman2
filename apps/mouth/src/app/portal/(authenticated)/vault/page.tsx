'use client';

import React, { useEffect, useState } from 'react';
import { Loader2, Upload, FileText, Download, Filter, X, Check } from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { formatDate } from '@/lib/utils/format-date';
import { logger } from '@/lib/logger';
import type { PortalDocument } from '@/lib/api/portal/portal.types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export default function VaultPage() {
  const { success, error } = useToast();
  const [documents, setDocuments] = useState<PortalDocument[]>([]);
  const [filteredDocs, setFilteredDocs] = useState<PortalDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const categories = ['all', 'passport', 'visa', 'tax', 'company', 'other'];

  useEffect(() => {
    loadDocuments();
  }, []);

  useEffect(() => {
    filterDocuments();
  }, [documents, selectedCategory, searchQuery]);

  const loadDocuments = async () => {
    try {
      setIsLoading(true);
      const docs = await api.portal.getDocuments();
      setDocuments(docs);
    } catch (err) {
      error('Failed to load documents', 'Please try again later');
      logger.error(
        'Failed to load documents',
        { component: 'VaultPage', action: 'loadDocuments' },
        err as Error
      );
    } finally {
      setIsLoading(false);
    }
  };

  const filterDocuments = () => {
    let filtered = documents;

    if (selectedCategory !== 'all') {
      filtered = filtered.filter(
        (doc) => doc.category.toLowerCase() === selectedCategory.toLowerCase()
      );
    }

    if (searchQuery) {
      filtered = filtered.filter((doc) =>
        doc.name.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    setFilteredDocs(filtered);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      error('File too large', 'Maximum file size is 10MB');
      return;
    }

    try {
      setIsUploading(true);
      const uploadedDoc = await api.portal.uploadDocument(file, 'general');
      setDocuments((prev) => [uploadedDoc, ...prev]);
      success('Document uploaded', `${file.name} was uploaded successfully`);
      e.target.value = '';
    } catch (err) {
      error('Upload failed', 'Could not upload document. Please try again.');
      logger.error(
        'Upload failed',
        { component: 'VaultPage', action: 'handleFileUpload' },
        err as Error
      );
    } finally {
      setIsUploading(false);
    }
  };

  const getStatusStyle = (status: string): React.CSSProperties => {
    switch (status) {
      case 'verified':
        return { background: 'rgba(16,185,129,0.12)', color: '#34d399' };
      case 'pending':
      case 'received':
        return { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' };
      case 'rejected':
        return { background: 'rgba(239,68,68,0.12)', color: '#f87171' };
      case 'expired':
        return { background: 'rgba(239,68,68,0.08)', color: '#fca5a5' };
      default:
        return {
          background: 'rgba(255,255,255,0.05)',
          color: 'var(--bz-text-2)',
        };
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-44 rounded animate-pulse"
            style={{ background: 'var(--bz-border)' }}
          />
          <div
            className="h-4 w-56 rounded mt-2 animate-pulse"
            style={{ background: 'var(--bz-border)', opacity: 0.5 }}
          />
        </section>
        <div
          className="rounded-lg border border-dashed p-6 h-28 animate-pulse"
          style={{ borderColor: 'rgba(201,169,110,0.4)', background: 'rgba(201,169,110,0.05)' }}
        />
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-lg border p-4 h-20 animate-pulse"
              style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
            />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Document Vault</h1>
        <p style={{ color: 'var(--bz-text-2)' }}>Manage your important documents</p>
      </section>

      {/* Upload Section */}
      <section
        className="rounded-lg border border-dashed p-6 text-center"
        style={{
          borderColor: 'rgba(201,169,110,0.4)',
          background: 'rgba(201,169,110,0.05)',
        }}
      >
        <label htmlFor="file-upload" className="flex flex-col items-center gap-2 cursor-pointer">
          {isUploading ? (
            <Loader2
              className="w-10 h-10 animate-spin"
              style={{ color: 'var(--bz-accent-warm)' }}
            />
          ) : (
            <Upload className="w-10 h-10" style={{ color: 'var(--bz-accent-warm)' }} />
          )}
          <div className="text-sm font-medium">
            {isUploading ? 'Uploading...' : 'Click to upload document'}
          </div>
          <div className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
            PDF, JPG, PNG up to 10MB
          </div>
          <input
            id="file-upload"
            type="file"
            className="hidden"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={handleFileUpload}
            disabled={isUploading}
          />
        </label>
      </section>

      {/* Filters */}
      <section className="space-y-3">
        <Input
          type="text"
          placeholder="Search documents..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full"
        />

        <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              aria-pressed={selectedCategory === cat}
              className="px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-colors"
              style={
                selectedCategory === cat
                  ? {
                      background:
                        'linear-gradient(135deg, var(--bz-accent-warm), rgba(212,132,90,0.8))',
                      color: '#0c0c0e',
                      boxShadow: '0 4px 14px 0 rgba(212,132,90,0.39)',
                    }
                  : {
                      background: 'rgba(35,35,40,0.5)',
                      backdropFilter: 'blur(12px)',
                      color: 'var(--bz-text-2)',
                    }
              }
            >
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </button>
          ))}
        </div>
      </section>

      {/* Documents List */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold" style={{ color: 'var(--bz-text-2)' }}>
            {filteredDocs.length} Document{filteredDocs.length !== 1 ? 's' : ''}
          </h2>
          {(searchQuery || selectedCategory !== 'all') && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearchQuery('');
                setSelectedCategory('all');
              }}
            >
              <X className="w-4 h-4 mr-1" />
              Clear filters
            </Button>
          )}
        </div>

        {filteredDocs.length === 0 ? (
          <div className="text-center py-12" style={{ color: 'var(--bz-text-2)' }}>
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No documents found</p>
            {documents.length === 0 && (
              <Button variant="outline" size="sm" onClick={loadDocuments} className="mt-3">
                Refresh
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredDocs.map((doc) => (
              <div
                key={doc.id}
                className="rounded-lg border p-4 transition-all duration-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)] hover:-translate-y-1 backdrop-blur-xl"
                style={{
                  background: 'rgba(30,30,35,0.7)',
                  borderColor: 'rgba(255,255,255,0.05)',
                }}
              >
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-md" style={{ background: 'rgba(201,169,110,0.12)' }}>
                    <FileText className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-sm truncate" title={doc.name}>
                      {doc.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={getStatusStyle(doc.status)}
                      >
                        {doc.status}
                      </span>
                      <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                        {doc.category}
                      </span>
                      <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                        •
                      </span>
                      <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                        {doc.size}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                      <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                        Uploaded: {formatDate(doc.uploadDate)}
                      </span>
                      {(() => {
                        const ageDays = Math.floor(
                          (Date.now() - new Date(doc.uploadDate).getTime()) / 86400000
                        );
                        if (ageDays < 7) return null;
                        const label =
                          ageDays >= 365
                            ? `${Math.floor(ageDays / 365)}y ago`
                            : ageDays >= 30
                              ? `${Math.floor(ageDays / 30)}mo ago`
                              : `${ageDays}d ago`;
                        return (
                          <span
                            className="text-[10px] px-1.5 py-0.5 rounded-full"
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
                    {doc.expiryDate &&
                      (() => {
                        const daysLeft = Math.ceil(
                          (new Date(doc.expiryDate).getTime() - Date.now()) / 86400000
                        );
                        const isExpired = daysLeft < 0;
                        const chipColor = isExpired
                          ? 'bg-red-500/20 text-red-400'
                          : daysLeft <= 30
                            ? 'bg-red-500/15 text-red-400'
                            : daysLeft <= 90
                              ? 'bg-amber-500/15 text-amber-400'
                              : 'bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)]';
                        const chipLabel = isExpired
                          ? `Expired ${Math.abs(daysLeft)}d ago`
                          : daysLeft === 0
                            ? 'Expires today'
                            : daysLeft <= 365
                              ? `⏰ ${daysLeft}d left`
                              : `${Math.floor(daysLeft / 30)}mo left`;
                        return (
                          <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                            <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                              Expires: {formatDate(doc.expiryDate)}
                            </span>
                            <span
                              className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${chipColor}`}
                              title={formatDate(doc.expiryDate)}
                            >
                              {chipLabel}
                            </span>
                          </div>
                        );
                      })()}
                  </div>
                  {doc.downloadUrl && (
                    <Button variant="ghost" size="icon" asChild>
                      <a
                        href={doc.downloadUrl}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Download document"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
