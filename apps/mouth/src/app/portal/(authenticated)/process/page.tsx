'use client';

import { useEffect, useState, useCallback, useRef, memo } from 'react';
import {
  Loader2,
  FileText,
  Upload,
  AlertCircle,
  CheckCircle,
  Clock,
  FolderOpen,
  AlertTriangle,
  X,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { useToast } from '@/components/ui/toast';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { FileUploadField } from '@/components/documents/FileUploadField';
import type { ClientRequiredDocument } from '@/lib/types/required-documents';

// Status configurations
const STATUS_CONFIG = {
  pending: {
    color: 'bg-amber-500/10 text-amber-500',
    icon: <Clock className="w-4 h-4" />,
    label: 'Pending',
  },
  uploaded: {
    color: 'bg-blue-500/10 text-blue-500',
    icon: <Upload className="w-4 h-4" />,
    label: 'Uploaded',
  },
  verified: {
    color: 'bg-green-500/10 text-green-500',
    icon: <CheckCircle className="w-4 h-4" />,
    label: 'Verified',
  },
  rejected: {
    color: 'bg-red-500/10 text-red-500',
    icon: <X className="w-4 h-4" />,
    label: 'Rejected',
  },
} as const;

// Process status mapping with colors (mirrored from CRM workspace)
const PROCESS_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  inquiry: { label: 'Inquiry', color: 'bg-slate-500/10 text-slate-400' },
  quotation_sent: { label: 'Quotation Sent', color: 'bg-blue-500/10 text-blue-400' },
  sending_invoice: { label: 'Sending Invoice', color: 'bg-blue-500/10 text-blue-400' },
  payment_pending: { label: 'Payment Pending', color: 'bg-amber-500/10 text-amber-400' },
  waiting_payment: { label: 'Waiting for Payment', color: 'bg-amber-500/10 text-amber-400' },
  in_progress: { label: 'In Progress', color: 'bg-sky-500/10 text-sky-400' },
  on_process: { label: 'On Process', color: 'bg-sky-500/10 text-sky-400' },
  waiting_documents: { label: 'Waiting for Documents', color: 'bg-orange-500/10 text-orange-400' },
  submitted_to_gov: { label: 'Submitted to Government', color: 'bg-purple-500/10 text-purple-400' },
  approved: { label: 'Approved', color: 'bg-emerald-500/10 text-emerald-400' },
  completed: { label: 'Completed', color: 'bg-green-500/10 text-green-400' },
  cancelled: { label: 'Cancelled', color: 'bg-red-500/10 text-red-400' },
};

// Keep compat for any old references
const PROCESS_STATUS_LABELS: Record<string, string> = Object.fromEntries(
  Object.entries(PROCESS_STATUS_CONFIG).map(([k, v]) => [k, v.label])
);

interface ProcessGroup {
  practiceId: number;
  processName: string;
  processStatus: string;
  documents: ClientRequiredDocument[];
}

// Status Badge Component
const StatusBadge = memo(({ status }: { status: keyof typeof STATUS_CONFIG }) => {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  return (
    <Badge variant="secondary" className={`${config.color} flex items-center gap-1`}>
      {config.icon}
      {config.label}
    </Badge>
  );
});
StatusBadge.displayName = 'StatusBadge';

// Document Upload Modal
function DocumentUploadModal({
  document,
  isOpen,
  onClose,
  onUpload,
  isUploading,
}: {
  document: ClientRequiredDocument | null;
  isOpen: boolean;
  onClose: () => void;
  onUpload: (file: string, fileName: string, notes: string) => Promise<void>;
  isUploading: boolean;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [notes, setNotes] = useState('');

  const handleFileSelect = (selectedFile: File | null, error: string | null) => {
    setFile(selectedFile);
    setFileError(error);
  };

  const handleSubmit = async () => {
    if (!file) return;

    // Convert file to base64
    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64 = reader.result as string;
      await onUpload(base64, file.name, notes);
    };
    reader.readAsDataURL(file);
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setFile(null);
      setFileError(null);
      setNotes('');
      onClose();
    }
  };

  if (!document) return null;

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Document</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div
            className="p-3 rounded-lg backdrop-blur-md"
            style={{ background: 'rgba(255,255,255,0.03)' }}
          >
            <p className="font-medium">{document.document_label}</p>
            {document.description && (
              <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
                {document.description}
              </p>
            )}
          </div>

          <FileUploadField
            id="doc-upload"
            label="Select Document"
            accept=".pdf,.jpg,.jpeg,.png"
            maxSize={10 * 1024 * 1024}
            onFileSelect={handleFileSelect}
            error={fileError}
            compact
          />

          <div>
            <label className="text-sm font-medium mb-1 block">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add any notes about this document..."
              className="w-full px-3 py-2 rounded-lg border text-sm min-h-[80px]"
              style={{
                background: 'rgba(255,255,255,0.03)',
                borderColor: 'rgba(255,255,255,0.05)',
                color: 'var(--bz-text-1)',
              }}
            />
          </div>

          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={onClose} disabled={isUploading}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={!file || isUploading}>
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4 mr-2" />
                  Upload
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Process Card Component
function ProcessCard({
  process,
  onUploadClick,
}: {
  process: ProcessGroup;
  onUploadClick: (doc: ClientRequiredDocument) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(true);

  const pendingCount = process.documents.filter((d) => d.status === 'pending').length;
  const uploadedCount = process.documents.filter((d) => d.status === 'uploaded').length;
  const verifiedCount = process.documents.filter((d) => d.status === 'verified').length;
  const totalCount = process.documents.length;
  const progress = totalCount > 0 ? Math.round((verifiedCount / totalCount) * 100) : 0;

  return (
    <div
      className="rounded-xl border shadow-2xl overflow-hidden backdrop-blur-xl transition-all duration-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
      style={{
        background: 'rgba(30,30,35,0.7)',
        borderColor: 'rgba(255,255,255,0.05)',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${process.processName}`}
        className="w-full p-4 flex items-center justify-between transition-colors"
        style={{ background: 'transparent' }}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(45,45,50,0.5)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
      >
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center">
            <FolderOpen className="w-5 h-5 text-[var(--accent)]" />
          </div>
          <div className="text-left">
            <h3 className="font-semibold">{process.processName}</h3>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${PROCESS_STATUS_CONFIG[process.processStatus]?.color || 'bg-slate-500/10 text-slate-400'}`}
            >
              {PROCESS_STATUS_CONFIG[process.processStatus]?.label || process.processStatus}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right hidden sm:block">
            <p className="text-sm font-medium">
              {verifiedCount}/{totalCount} documents
            </p>
            <div
              className="w-24 h-1.5 rounded-full mt-1 border border-[rgba(255,255,255,0.05)]"
              style={{ background: 'rgba(255,255,255,0.05)' }}
            >
              <div
                className="h-full bg-[var(--accent)] rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
          {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
        </div>
      </button>

      {/* Documents List */}
      {isExpanded && (
        <div
          className="border-t divide-y divide-[rgba(255,255,255,0.05)]"
          style={{ borderColor: 'rgba(255,255,255,0.05)' }}
        >
          {process.documents.length === 0 ? (
            <div className="p-6 text-center" style={{ color: 'var(--bz-text-2)' }}>
              <FileText className="w-10 h-10 mx-auto mb-2 opacity-30" />
              <p>No documents required</p>
            </div>
          ) : (
            process.documents.map((doc) => (
              <div
                key={doc.id}
                className={`p-4 flex items-start justify-between gap-3 ${
                  doc.is_required ? 'border-l-2 border-l-amber-500' : ''
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-medium">{doc.document_label}</span>
                    {doc.is_required && (
                      <Badge
                        variant="secondary"
                        className="text-[10px] bg-amber-500/10 text-amber-500"
                      >
                        Required
                      </Badge>
                    )}
                  </div>
                  {doc.description && (
                    <p className="text-sm mt-0.5" style={{ color: 'var(--bz-text-2)' }}>
                      {doc.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2">
                    <StatusBadge status={doc.status as keyof typeof STATUS_CONFIG} />
                    {doc.team_member_notes && (
                      <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                        Note: {doc.team_member_notes}
                      </span>
                    )}
                  </div>
                </div>

                {doc.status === 'pending' && (
                  <Button size="sm" onClick={() => onUploadClick(doc)}>
                    <Upload className="w-4 h-4 mr-1" />
                    Upload
                  </Button>
                )}
                {doc.status === 'uploaded' && (
                  <Badge variant="secondary" className="bg-blue-500/10 text-blue-500">
                    Under Review
                  </Badge>
                )}
                {doc.status === 'verified' && <CheckCircle className="w-5 h-5 text-green-500" />}
                {doc.status === 'rejected' && (
                  <Button size="sm" variant="destructive" onClick={() => onUploadClick(doc)}>
                    <Upload className="w-4 h-4 mr-1" />
                    Re-upload
                  </Button>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// Main Page Component
export default function PortalProcessPage() {
  const toast = useToast();
  const toastRef = useRef(toast);
  toastRef.current = toast;

  const [profile, setProfile] = useState<{
    id: number;
    fullName: string;
  } | null>(null);
  const [documents, setDocuments] = useState<ClientRequiredDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadDoc, setUploadDoc] = useState<ClientRequiredDocument | null>(null);

  // Load profile and documents — stable reference, no toast dependency in deps
  const loadData = useCallback(async () => {
    try {
      setIsLoading(true);

      // Get profile
      const profileData = await api.portal.getProfile();
      setProfile({ id: profileData.id, fullName: profileData.fullName });

      // Get required documents
      const docs = await api.crm.getClientRequiredDocuments(profileData.id);
      setDocuments(docs);
    } catch (err) {
      toastRef.current.error('Failed to load data', 'Please try again later');
      logger.error('Failed to load process data', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []); // stable — no deps that change every render

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle document upload
  const handleUpload = async (file: string, fileName: string, notes: string) => {
    if (!uploadDoc) return;

    setIsUploading(true);
    try {
      await api.crm.uploadClientDocument(uploadDoc.practice_id, {
        required_doc_id: uploadDoc.id,
        file,
        file_name: fileName,
        notes,
      });

      toastRef.current.success('Document uploaded', 'Your document has been submitted for review');
      setUploadDoc(null);
      await loadData(); // Refresh data
    } catch (err) {
      toastRef.current.error('Upload failed', 'Please try again');
      logger.error('Failed to upload document', {}, err as Error);
    } finally {
      setIsUploading(false);
    }
  };

  // Group documents by process
  const processGroups: ProcessGroup[] = documents.reduce((groups, doc) => {
    const existing = groups.find((g) => g.practiceId === doc.practice_id);
    if (existing) {
      existing.documents.push(doc);
    } else {
      groups.push({
        practiceId: doc.practice_id,
        processName: doc.process_name,
        processStatus: doc.process_status,
        documents: [doc],
      });
    }
    return groups;
  }, [] as ProcessGroup[]);

  // Stats
  const totalDocs = documents.length;
  const pendingDocs = documents.filter((d) => d.status === 'pending').length;
  const verifiedDocs = documents.filter((d) => d.status === 'verified').length;
  const completionRate = totalDocs > 0 ? Math.round((verifiedDocs / totalDocs) * 100) : 0;

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--bz-accent-warm)' }} />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-4xl mx-auto">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">My Processes</h1>
        <p style={{ color: 'var(--bz-text-2)' }}>
          Track your active processes and upload required documents
        </p>
      </section>

      {/* Stats Cards */}
      {totalDocs > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div
            className="rounded-xl border p-4 backdrop-blur-md shadow-lg"
            style={{
              background: 'rgba(30,30,35,0.6)',
              borderColor: 'rgba(255,255,255,0.05)',
            }}
          >
            <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
              Active Processes
            </p>
            <p className="text-2xl font-bold">{processGroups.length}</p>
          </div>
          <div
            className="rounded-xl border p-4"
            style={{
              background: 'rgba(30,30,35,0.7)',
              borderColor: 'rgba(255,255,255,0.05)',
              backdropFilter: 'blur(24px)',
            }}
          >
            <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
              Documents Required
            </p>
            <p className="text-2xl font-bold">{totalDocs}</p>
          </div>
          <div
            className="rounded-xl border p-4"
            style={{
              background: 'rgba(30,30,35,0.7)',
              borderColor: 'rgba(255,255,255,0.05)',
              backdropFilter: 'blur(24px)',
            }}
          >
            <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
              Pending Upload
            </p>
            <p className="text-2xl font-bold text-amber-400">{pendingDocs}</p>
          </div>
          <div
            className="rounded-xl border p-4"
            style={{
              background: 'rgba(30,30,35,0.7)',
              borderColor: 'rgba(255,255,255,0.05)',
              backdropFilter: 'blur(24px)',
            }}
          >
            <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
              Completion
            </p>
            <p className="text-2xl font-bold text-green-400">{completionRate}%</p>
          </div>
        </div>
      )}

      {/* Process List */}
      {processGroups.length === 0 ? (
        <div
          className="rounded-xl border p-12 text-center backdrop-blur-lg"
          style={{
            background: 'rgba(30,30,35,0.5)',
            borderColor: 'rgba(255,255,255,0.05)',
          }}
        >
          <FolderOpen className="w-16 h-16 mx-auto mb-4" style={{ color: 'var(--bz-text-3)' }} />
          <h3 className="text-lg font-medium mb-2">No Active Processes</h3>
          <p className="max-w-md mx-auto" style={{ color: 'var(--bz-text-2)' }}>
            You don&apos;t have any active processes at the moment. When your team leader creates a
            process for you, it will appear here with any documents you need to upload.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {pendingDocs > 0 && (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-4 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-amber-600">Documents Required</p>
                <p className="text-sm text-amber-600/80">
                  You have {pendingDocs} document{pendingDocs > 1 ? 's' : ''} waiting to be
                  uploaded. Please upload them to proceed with your process.
                </p>
              </div>
            </div>
          )}

          {processGroups.map((process) => (
            <ProcessCard key={process.practiceId} process={process} onUploadClick={setUploadDoc} />
          ))}
        </div>
      )}

      {/* Upload Modal */}
      <DocumentUploadModal
        document={uploadDoc}
        isOpen={!!uploadDoc}
        onClose={() => setUploadDoc(null)}
        onUpload={handleUpload}
        isUploading={isUploading}
      />
    </div>
  );
}
