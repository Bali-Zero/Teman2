'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  FileText,
  Upload,
  Download,
  Eye,
  Search,
  Folder,
  Clock,
  CheckCircle2,
  AlertCircle,
  X,
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

const documentTypes = [
  { id: 'passport', name: 'Passport Copy', category: 'personal' },
  { id: 'photo', name: 'Photo (4x6)', category: 'personal' },
  { id: 'kitas', name: 'KITAS Card', category: 'immigration' },
  { id: 'imta', name: 'Work Permit (IMTA)', category: 'immigration' },
  { id: 'sponsor_letter', name: 'Sponsor Letter', category: 'immigration' },
  { id: 'nib', name: 'NIB Certificate', category: 'company' },
  { id: 'oss', name: 'OSS License', category: 'company' },
  { id: 'akta', name: 'Company Deed', category: 'company' },
  { id: 'npwp', name: 'NPWP', category: 'tax' },
  { id: 'spt', name: 'SPT Tax Return', category: 'tax' },
  { id: 'other', name: 'Other', category: 'personal' },
];

export default function DocumentsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<PortalDocument[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedDocType, setSelectedDocType] = useState('');

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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      // Validate file size (10MB max)
      if (file.size > 10 * 1024 * 1024) {
        setUploadError('File too large. Maximum size is 10MB');
        return;
      }
      setSelectedFile(file);
      setUploadError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !selectedDocType) {
      setUploadError('Please select a file and document type');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      const newDoc = await api.portal.uploadDocument(selectedFile, selectedDocType);
      setDocuments((prev) => [newDoc, ...prev]);
      setShowUploadModal(false);
      setSelectedFile(null);
      setSelectedDocType('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      console.error('Upload failed:', err);
      setUploadError('Failed to upload document. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  const filteredDocuments = documents.filter((doc) => {
    const matchesCategory = selectedCategory === 'all' || doc.category === selectedCategory;
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'verified': return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
      case 'pending': return <Clock className="w-4 h-4 text-amber-600" />;
      default: return <Clock className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'verified': return 'bg-emerald-100 text-emerald-700';
      case 'pending': return 'bg-amber-100 text-amber-700';
      case 'expired': return 'bg-red-100 text-red-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  const formatSize = (sizeStr: string) => {
    // If it's already formatted like "2.4 MB", return as is
    if (sizeStr.includes(' ')) return sizeStr;
    // If it's just a number (KB), format it
    const kb = parseInt(sizeStr, 10);
    if (kb >= 1024) {
      return `${(kb / 1024).toFixed(1)} MB`;
    }
    return `${kb} KB`;
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-slate-200 rounded w-64"></div>
        <div className="h-48 bg-slate-200 rounded-xl"></div>
      </div>
    );
  }

  if (error && !documents.length) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-lg font-medium text-slate-800 mb-2">Unable to load documents</h2>
        <p className="text-slate-500 mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Documents</h1>
          <p className="text-slate-500 mt-1">View and manage your documents</p>
        </div>
        <button
          onClick={() => setShowUploadModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
        >
          <Upload className="w-4 h-4" />
          <span>Upload Document</span>
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
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
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {category.name}
            </button>
          ))}
        </div>
      </div>

      {/* Document Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <div className="flex items-center gap-2 text-slate-500 mb-1">
            <FileText className="w-4 h-4" />
            <span className="text-sm">Total</span>
          </div>
          <p className="text-2xl font-semibold text-slate-800">{documents.length}</p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <div className="flex items-center gap-2 text-emerald-500 mb-1">
            <CheckCircle2 className="w-4 h-4" />
            <span className="text-sm">Verified</span>
          </div>
          <p className="text-2xl font-semibold text-slate-800">
            {documents.filter((d) => d.status === 'verified').length}
          </p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <div className="flex items-center gap-2 text-amber-500 mb-1">
            <Clock className="w-4 h-4" />
            <span className="text-sm">Pending</span>
          </div>
          <p className="text-2xl font-semibold text-slate-800">
            {documents.filter((d) => d.status === 'pending').length}
          </p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <div className="flex items-center gap-2 text-slate-500 mb-1">
            <Folder className="w-4 h-4" />
            <span className="text-sm">Categories</span>
          </div>
          <p className="text-2xl font-semibold text-slate-800">{categories.length - 1}</p>
        </div>
      </div>

      {/* Document List */}
      <div className="bg-white rounded-xl border border-slate-200">
        {filteredDocuments.length === 0 ? (
          <div className="p-8 text-center">
            <FileText className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500">No documents found</p>
            <button
              onClick={() => setShowUploadModal(true)}
              className="mt-4 text-emerald-600 hover:text-emerald-700 font-medium"
            >
              Upload your first document
            </button>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredDocuments.map((doc) => (
              <div key={doc.id} className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <FileText className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-slate-800">{doc.name}</p>
                      {getStatusIcon(doc.status)}
                    </div>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-slate-500">{formatSize(doc.size)}</span>
                      <span className="text-xs text-slate-400">-</span>
                      <span className="text-xs text-slate-500">Uploaded {doc.uploadDate}</span>
                      {doc.expiryDate && (
                        <>
                          <span className="text-xs text-slate-400">-</span>
                          <span className="text-xs text-slate-500">Expires {doc.expiryDate}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(doc.status)}`}>
                    {doc.status}
                  </span>
                  <button className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
                    <Eye className="w-4 h-4" />
                  </button>
                  {doc.downloadUrl && (
                    <a
                      href={doc.downloadUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
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

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
            <div className="flex items-center justify-between p-4 border-b border-slate-100">
              <h2 className="text-lg font-semibold text-slate-800">Upload Document</h2>
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setSelectedFile(null);
                  setSelectedDocType('');
                  setUploadError(null);
                }}
                className="p-1 text-slate-400 hover:text-slate-600 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 space-y-4">
              {/* Document Type */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Document Type
                </label>
                <select
                  value={selectedDocType}
                  onChange={(e) => setSelectedDocType(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="">Select document type...</option>
                  {documentTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* File Input */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  File
                </label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-200 rounded-lg p-6 text-center cursor-pointer hover:border-emerald-400 transition-colors"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                  {selectedFile ? (
                    <div>
                      <FileText className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                      <p className="text-sm font-medium text-slate-800">{selectedFile.name}</p>
                      <p className="text-xs text-slate-500 mt-1">
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  ) : (
                    <div>
                      <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                      <p className="text-sm text-slate-600">Click to select a file</p>
                      <p className="text-xs text-slate-400 mt-1">
                        PDF, JPG, PNG, DOC up to 10MB
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Error */}
              {uploadError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-600">{uploadError}</p>
                </div>
              )}
            </div>

            <div className="flex gap-3 p-4 border-t border-slate-100">
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setSelectedFile(null);
                  setSelectedDocType('');
                  setUploadError(null);
                }}
                className="flex-1 px-4 py-2 border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleUpload}
                disabled={!selectedFile || !selectedDocType || isUploading}
                className={`flex-1 px-4 py-2 rounded-lg transition-colors ${
                  selectedFile && selectedDocType && !isUploading
                    ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                }`}
              >
                {isUploading ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
