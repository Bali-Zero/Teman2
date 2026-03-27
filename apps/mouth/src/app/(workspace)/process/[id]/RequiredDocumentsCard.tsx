'use client';

import { useState, memo } from 'react';
import {
  FileText,
  Plus,
  Trash2,
  CheckCircle,
  Upload,
  AlertCircle,
  FileCheck,
  X,
  ChevronDown,
  Eye,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { FileUploadField } from '@/components/documents/FileUploadField';
import { toast } from 'sonner';
import { useRequiredDocuments } from '@/lib/hooks/useRequiredDocuments';
import {
  RequiredDocument,
  DocumentStatus,
  DOCUMENT_TYPE_OPTIONS,
} from '@/lib/types/required-documents';

interface RequiredDocumentsCardProps {
  practiceId: number;
}

// Status Badge Component
const StatusBadge = memo(({ status }: { status: DocumentStatus }) => {
  const configs: Record<DocumentStatus, { color: string; icon: React.ReactNode; label: string }> = {
    pending: {
      color: 'bg-amber-500/10 text-amber-500',
      icon: <AlertCircle className="w-3 h-3" />,
      label: 'Pending',
    },
    uploaded: {
      color: 'bg-blue-500/10 text-blue-500',
      icon: <Upload className="w-3 h-3" />,
      label: 'Uploaded',
    },
    verified: {
      color: 'bg-green-500/10 text-green-500',
      icon: <CheckCircle className="w-3 h-3" />,
      label: 'Verified',
    },
    rejected: {
      color: 'bg-red-500/10 text-red-500',
      icon: <X className="w-3 h-3" />,
      label: 'Rejected',
    },
  };
  const config = configs[status];
  return (
    <Badge variant="secondary" className={`${config.color} flex items-center gap-1`}>
      {config.icon}
      {config.label}
    </Badge>
  );
});
StatusBadge.displayName = 'StatusBadge';

// Add Document Modal
function AddDocumentModal({
  isOpen,
  onClose,
  onAdd,
  isLoading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onAdd: (data: {
    document_type: string;
    document_label: string;
    description: string;
    is_required: boolean;
  }) => Promise<void>;
  isLoading: boolean;
}) {
  const [selectedType, setSelectedType] = useState('');
  const [customLabel, setCustomLabel] = useState('');
  const [description, setDescription] = useState('');
  const [isRequired, setIsRequired] = useState(true);

  const selectedOption = DOCUMENT_TYPE_OPTIONS.find((o) => o.value === selectedType);

  const handleSubmit = async () => {
    if (!selectedType) return;
    await onAdd({
      document_type: selectedType,
      document_label: customLabel || selectedOption?.label || selectedType,
      description,
      is_required: isRequired,
    });
    setSelectedType('');
    setCustomLabel('');
    setDescription('');
    onClose();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Required Document</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label>Document Type</Label>
            <Select value={selectedType} onValueChange={setSelectedType}>
              <SelectTrigger>
                <SelectValue placeholder="Select document type..." />
              </SelectTrigger>
              <SelectContent>
                {DOCUMENT_TYPE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    <div className="flex flex-col">
                      <span>{option.label}</span>
                      <span className="text-xs text-muted-foreground">{option.description}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Custom Label (optional)</Label>
            <Input
              value={customLabel}
              onChange={(e) => setCustomLabel(e.target.value)}
              placeholder={selectedOption?.label || 'Document name...'}
            />
          </div>

          <div>
            <Label>Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={selectedOption?.description || 'Add notes for the client...'}
              rows={2}
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is-required"
              checked={isRequired}
              onChange={(e) => setIsRequired(e.target.checked)}
              className="rounded border-gray-300"
            />
            <Label htmlFor="is-required" className="mb-0">
              Required document
            </Label>
          </div>

          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={!selectedType || isLoading}>
              {isLoading ? 'Adding...' : 'Add Document'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Document Review Modal
function DocumentReviewModal({
  document,
  isOpen,
  onClose,
  onUpdate,
  isLoading,
}: {
  document: RequiredDocument | null;
  isOpen: boolean;
  onClose: () => void;
  onUpdate: (
    docId: number,
    data: { status: DocumentStatus; team_member_notes: string }
  ) => Promise<void>;
  isLoading: boolean;
}) {
  const [status, setStatus] = useState<DocumentStatus>('pending');
  const [notes, setNotes] = useState('');

  // Reset when document changes
  const handleOpenChange = (open: boolean) => {
    if (open && document) {
      setStatus(document.status);
      setNotes(document.team_member_notes || '');
    }
    if (!open) onClose();
  };

  const handleSubmit = async () => {
    if (!document) return;
    await onUpdate(document.id, { status, team_member_notes: notes });
    onClose();
  };

  if (!document) return null;

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Review Document</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="p-3 bg-muted rounded-lg">
            <p className="font-medium">{document.document_label}</p>
            <p className="text-sm text-muted-foreground">{document.document_type}</p>
            {document.client_notes && (
              <p className="text-sm mt-2">
                <strong>Client notes:</strong> {document.client_notes}
              </p>
            )}
          </div>

          <div>
            <Label>Status</Label>
            <Select value={status} onValueChange={(v) => setStatus(v as DocumentStatus)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="uploaded">Uploaded</SelectItem>
                <SelectItem value="verified">Verified</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label>Team Notes</Label>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add notes for the team..."
              rows={3}
            />
          </div>

          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={onClose} disabled={isLoading}>
              Cancel
            </Button>
            <Button onClick={handleSubmit} disabled={isLoading}>
              {isLoading ? 'Saving...' : 'Save Review'}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// Main Component
export function RequiredDocumentsCard({ practiceId }: RequiredDocumentsCardProps) {
  const { documents, isLoading, stats, addDocument, updateDocument, deleteDocument } =
    useRequiredDocuments({ practiceId });

  const [showAddModal, setShowAddModal] = useState(false);
  const [reviewDoc, setReviewDoc] = useState<RequiredDocument | null>(null);
  const [processingId, setProcessingId] = useState<number | null>(null);

  const handleDelete = (docId: number) => {
    toast('Remove this document requirement?', {
      action: {
        label: 'Remove',
        onClick: async () => {
          setProcessingId(docId);
          try {
            await deleteDocument(docId);
          } finally {
            setProcessingId(null);
          }
        },
      },
      cancel: { label: 'Cancel', onClick: () => toast.dismiss() },
    });
  };

  return (
    <div className="bg-card rounded-xl border shadow-sm">
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-[var(--accent)]" />
            <h3 className="font-semibold">Required Documents</h3>
            <Badge variant="secondary" className="ml-2">
              {stats.verified}/{stats.total}
            </Badge>
          </div>
          <Button size="sm" onClick={() => setShowAddModal(true)}>
            <Plus className="w-4 h-4 mr-1" />
            Add
          </Button>
        </div>

        {/* Progress Bar */}
        {stats.total > 0 && (
          <div className="mt-3">
            <div className="flex justify-between text-xs text-muted-foreground mb-1">
              <span>Completion</span>
              <span>{stats.completionPercentage}%</span>
            </div>
            <div className="h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--accent)] transition-all"
                style={{ width: `${stats.completionPercentage}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Document List */}
      <div className="divide-y">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            <div className="animate-spin w-6 h-6 border-2 border-[var(--accent)] border-t-transparent rounded-full mx-auto mb-2" />
            Loading documents...
          </div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p>No required documents set</p>
            <p className="text-sm">Add documents that the client needs to provide</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => setShowAddModal(true)}
            >
              <Plus className="w-4 h-4 mr-1" />
              Add First Document
            </Button>
          </div>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className={`p-3 hover:bg-muted/50 transition-colors ${
                doc.is_required ? 'border-l-2 border-l-amber-500' : ''
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{doc.document_label}</span>
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
                    <p className="text-xs text-muted-foreground truncate">{doc.description}</p>
                  )}
                  <div className="flex items-center gap-2 mt-1">
                    <StatusBadge status={doc.status} />
                    {doc.uploaded_by_client && (
                      <span className="text-xs text-green-600 flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" />
                        Uploaded
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1">
                  {doc.uploaded_by_client && (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8"
                      onClick={() => setReviewDoc(doc)}
                      title="Review document"
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    onClick={() => handleDelete(doc.id)}
                    disabled={processingId === doc.id}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Modals */}
      <AddDocumentModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onAdd={addDocument}
        isLoading={isLoading}
      />

      <DocumentReviewModal
        document={reviewDoc}
        isOpen={!!reviewDoc}
        onClose={() => setReviewDoc(null)}
        onUpdate={updateDocument}
        isLoading={isLoading}
      />
    </div>
  );
}
