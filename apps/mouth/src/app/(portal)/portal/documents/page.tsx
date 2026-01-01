'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  Download,
  Eye,
  Search,
  Folder,
  Clock,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { PortalDocument } from '@/lib/api/portal/portal.types';

const categories = [
  { id: 'all', name: 'All Documents' },
  { id: 'immigration', name: 'Immigration' },
  { id: 'company', name: 'Company' },
  { id: 'tax', name: 'Tax' },
  { id: 'personal', name: 'Personal' },
];

export default function DocumentsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<PortalDocument[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const loadDocuments = useCallback(async () => {
    try {
      const data = await api.portal.getDocuments();
      setDocuments(data);
      setError(null);
    } catch (err) {
      console.error('Failed to load documents:', err);
      setError('Unable to load documents. Please try again.');
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setIsLoading(true);
      await loadDocuments();
      setIsLoading(false);
    };
    init();
  }, [loadDocuments]);

  const filteredDocuments = documents.filter((doc) => {
    const matchesCategory = selectedCategory === 'all' || doc.category === selectedCategory;
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'verified': return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'pending': return <Clock className="w-4 h-4 text-amber-400" />;
      default: return <Clock className="w-4 h-4 text-[#9AA0AE]" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'pending': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'expired': return 'bg-red-500/10 text-red-400 border-red-500/20';
      default: return 'bg-[#1A1D24] text-[#9AA0AE] border-white/10';
    }
  };

  const formatSize = (sizeStr: string) => {
    if (sizeStr.includes(' ')) return sizeStr;
    const kb = parseInt(sizeStr, 10);
    if (kb >= 1024) {
      return `${(kb / 1024).toFixed(1)} MB`;
    }
    return `${kb} KB`;
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-[#1A1D24] rounded w-64"></div>
        <div className="h-48 bg-[#1A1D24] rounded-xl"></div>
      </div>
    );
  }

  if (error && !documents.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-lg font-medium text-[#E6E7EB] mb-2">Unable to load documents</h2>
        <p className="text-[#9AA0AE] mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-[#4FD1C5] text-[#0B0E13] font-medium rounded-lg hover:bg-[#38B2AC] transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-[#E6E7EB]">Documents</h1>
        <p className="text-[#9AA0AE] mt-1">View and download your documents</p>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9AA0AE]" />
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-[#1A1D24] border border-white/10 rounded-lg text-[#E6E7EB] placeholder-[#9AA0AE] focus:outline-none focus:ring-2 focus:ring-[#4FD1C5] focus:border-transparent"
          />
        </div>

        {/* Category Filter */}
        <div className="flex gap-2 overflow-x-auto pb-2 md:pb-0">
          {categories.map((category) => (
            <button
              key={category.id}
              onClick={() => setSelectedCategory(category.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                selectedCategory === category.id
                  ? 'bg-[#4FD1C5]/10 text-[#4FD1C5] border border-[#4FD1C5]/20'
                  : 'bg-[#1A1D24] border border-white/10 text-[#9AA0AE] hover:bg-[#1F2329]'
              }`}
            >
              {category.name}
            </button>
          ))}
        </div>
      </div>

      {/* Document Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-[#1A1D24] rounded-xl border border-white/5">
          <div className="flex items-center gap-2 text-[#9AA0AE] mb-1">
            <FileText className="w-4 h-4" />
            <span className="text-sm">Total</span>
          </div>
          <p className="text-2xl font-semibold text-[#E6E7EB]">{documents.length}</p>
        </div>
        <div className="p-4 bg-[#1A1D24] rounded-xl border border-white/5">
          <div className="flex items-center gap-2 text-emerald-400 mb-1">
            <CheckCircle2 className="w-4 h-4" />
            <span className="text-sm">Verified</span>
          </div>
          <p className="text-2xl font-semibold text-[#E6E7EB]">
            {documents.filter((d) => d.status === 'verified').length}
          </p>
        </div>
        <div className="p-4 bg-[#1A1D24] rounded-xl border border-white/5">
          <div className="flex items-center gap-2 text-amber-400 mb-1">
            <Clock className="w-4 h-4" />
            <span className="text-sm">Pending</span>
          </div>
          <p className="text-2xl font-semibold text-[#E6E7EB]">
            {documents.filter((d) => d.status === 'pending').length}
          </p>
        </div>
        <div className="p-4 bg-[#1A1D24] rounded-xl border border-white/5">
          <div className="flex items-center gap-2 text-[#9AA0AE] mb-1">
            <Folder className="w-4 h-4" />
            <span className="text-sm">Categories</span>
          </div>
          <p className="text-2xl font-semibold text-[#E6E7EB]">{categories.length - 1}</p>
        </div>
      </div>

      {/* Document List */}
      <div className="bg-[#1A1D24] rounded-xl border border-white/5">
        {filteredDocuments.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="w-12 h-12 text-[#9AA0AE] mx-auto mb-4" />
            <h3 className="font-medium text-[#E6E7EB]">No documents found</h3>
            <p className="text-sm text-[#9AA0AE] mt-1">Your documents will appear here</p>
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {filteredDocuments.map((doc) => (
              <div key={doc.id} className="p-4 flex items-center justify-between hover:bg-[#1F2329] transition-colors">
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-blue-500/10 rounded-lg">
                    <FileText className="w-5 h-5 text-blue-400" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-[#E6E7EB]">{doc.name}</p>
                      {getStatusIcon(doc.status)}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-[#9AA0AE]">{formatSize(doc.size)}</span>
                      <span className="text-xs text-[#6B7280]">•</span>
                      <span className="text-xs text-[#9AA0AE]">Uploaded {doc.uploadDate}</span>
                      {doc.expiryDate && (
                        <>
                          <span className="text-xs text-[#6B7280]">•</span>
                          <span className="text-xs text-[#9AA0AE]">Expires {doc.expiryDate}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 text-xs rounded-full border ${getStatusColor(doc.status)}`}>
                    {doc.status}
                  </span>
                  <button className="p-2 text-[#9AA0AE] hover:text-[#4FD1C5] hover:bg-[#4FD1C5]/10 rounded-lg transition-colors">
                    <Eye className="w-4 h-4" />
                  </button>
                  {doc.downloadUrl && (
                    <a
                      href={doc.downloadUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-[#9AA0AE] hover:text-[#4FD1C5] hover:bg-[#4FD1C5]/10 rounded-lg transition-colors"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
