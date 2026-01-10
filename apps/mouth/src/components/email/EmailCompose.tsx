'use client';

import React from 'react';
import {
  X,
  Send,
  Paperclip,
  Trash2,
  Minimize2,
  Maximize2,
  ChevronDown,
  Save,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { AttachmentObject } from '@/lib/api/email/email.types';

interface EmailComposeProps {
  isOpen: boolean;
  onClose: () => void;
  onSend: (data: ComposeData) => Promise<void>;
  onSaveDraft: (data: ComposeData) => Promise<void>;
  initialData?: Partial<ComposeData>;
  mode?: 'new' | 'reply' | 'replyAll' | 'forward';
  isSending?: boolean;
}

export interface ComposeData {
  to: string[];
  cc: string[];
  bcc: string[];
  subject: string;
  htmlContent: string;
  attachmentIds: AttachmentObject[];
}

interface AttachmentItem {
  file: File;
  data?: AttachmentObject;
  isUploading: boolean;
}

export function EmailCompose({
  isOpen,
  onClose,
  onSend,
  onSaveDraft,
  initialData,
  mode = 'new',
  isSending,
}: EmailComposeProps) {
  const [isMinimized, setIsMinimized] = React.useState(false);
  const [showCcBcc, setShowCcBcc] = React.useState(false);
  const [to, setTo] = React.useState(initialData?.to?.join(', ') || '');
  const [cc, setCc] = React.useState(initialData?.cc?.join(', ') || '');
  const [bcc, setBcc] = React.useState(initialData?.bcc?.join(', ') || '');
  const [subject, setSubject] = React.useState(initialData?.subject || '');
  const [content, setContent] = React.useState(initialData?.htmlContent || '');
  
  // Attachments state with upload status
  const [attachments, setAttachments] = React.useState<AttachmentItem[]>([]);
  const [isSavingDraft, setIsSavingDraft] = React.useState(false);

  React.useEffect(() => {
    if (initialData) {
      setTo(initialData.to?.join(', ') || '');
      setCc(initialData.cc?.join(', ') || '');
      setBcc(initialData.bcc?.join(', ') || '');
      setSubject(initialData.subject || '');
      setContent(initialData.htmlContent || '');
    }
  }, [initialData]);

  const getComposeData = (): ComposeData => ({
    to: to.split(',').map((e) => e.trim()).filter(Boolean),
    cc: cc.split(',').map((e) => e.trim()).filter(Boolean),
    bcc: bcc.split(',').map((e) => e.trim()).filter(Boolean),
    subject,
    htmlContent: content,
    attachmentIds: attachments.map(a => a.data).filter((d): d is AttachmentObject => !!d),
  });

  const handleSend = async () => {
    const pendingUploads = attachments.some(a => a.isUploading);
    if (pendingUploads) {
      alert('Please wait for files to finish uploading.');
      return;
    }
    await onSend(getComposeData());
  };

  const handleSave = async () => {
    const pendingUploads = attachments.some(a => a.isUploading);
    if (pendingUploads) {
      alert('Please wait for files to finish uploading.');
      return;
    }
    
    setIsSavingDraft(true);
    try {
      await onSaveDraft(getComposeData());
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleAttachFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newAttachments = Array.from(files).map(file => ({
      file,
      isUploading: true,
    }));

    setAttachments(prev => [...prev, ...newAttachments]);

    // Upload each file
    for (const attachment of newAttachments) {
      try {
        const response = await api.email.uploadAttachment(attachment.file);
        
        setAttachments(prev => prev.map(item => 
          item.file === attachment.file 
            ? { ...item, data: response, isUploading: false }
            : item
        ));
      } catch (error) {
        console.error(`Failed to upload ${attachment.file.name}:`, error);
        alert(`Failed to upload ${attachment.file.name}`);
        setAttachments(prev => prev.filter(item => item.file !== attachment.file));
      }
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };

  if (!isOpen) return null;

  const modeLabels = {
    new: 'New Message',
    reply: 'Reply',
    replyAll: 'Reply All',
    forward: 'Forward',
  };

  const hasPendingUploads = attachments.some(a => a.isUploading);
  const isActionDisabled = isSending || isSavingDraft || hasPendingUploads || !to.trim();

  return (
    <div
      className={cn(
        'fixed z-50 bg-[var(--background-secondary)] border border-[var(--border)] rounded-t-xl shadow-2xl',
        'flex flex-col transition-all duration-200',
        isMinimized
          ? 'bottom-0 right-4 w-80 h-12'
          : 'bottom-0 right-4 w-[600px] h-[500px] max-h-[80vh]'
      )}
    >
      {/* Header */}
      <div
        className={cn(
          'flex items-center justify-between px-4 py-3 border-b border-[var(--border)]',
          'bg-[var(--background-elevated)] rounded-t-xl cursor-pointer'
        )}
        onClick={() => isMinimized && setIsMinimized(false)}
      >
        <span className="text-sm font-medium text-[var(--foreground)]">
          {modeLabels[mode]}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsMinimized(!isMinimized);
            }}
            className="p-1.5 rounded hover:bg-[var(--background-secondary)] transition-colors"
          >
            {isMinimized ? (
              <Maximize2 className="w-4 h-4 text-[var(--foreground-muted)]" />
            ) : (
              <Minimize2 className="w-4 h-4 text-[var(--foreground-muted)]" />
            )}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClose();
            }}
            className="p-1.5 rounded hover:bg-[var(--background-secondary)] transition-colors"
          >
            <X className="w-4 h-4 text-[var(--foreground-muted)]" />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Form Fields */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* To Field */}
            <div className="flex items-center border-b border-[var(--border)]">
              <label className="w-16 px-4 py-2 text-sm text-[var(--foreground-muted)]">
                To
              </label>
              <input
                type="text"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="Recipients"
                className={cn(
                  'flex-1 px-2 py-2 text-sm bg-transparent',
                  'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                  'focus:outline-none'
                )}
              />
              <button
                onClick={() => setShowCcBcc(!showCcBcc)}
                className="px-3 py-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
              >
                Cc/Bcc
                <ChevronDown
                  className={cn(
                    'w-3 h-3 inline ml-1 transition-transform',
                    showCcBcc && 'rotate-180'
                  )}
                />
              </button>
            </div>

            {/* Cc/Bcc Fields */}
            {showCcBcc && (
              <>
                <div className="flex items-center border-b border-[var(--border)]">
                  <label className="w-16 px-4 py-2 text-sm text-[var(--foreground-muted)]">
                    Cc
                  </label>
                  <input
                    type="text"
                    value={cc}
                    onChange={(e) => setCc(e.target.value)}
                    placeholder="Carbon copy"
                    className={cn(
                      'flex-1 px-2 py-2 text-sm bg-transparent',
                      'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                      'focus:outline-none'
                    )}
                  />
                </div>
                <div className="flex items-center border-b border-[var(--border)]">
                  <label className="w-16 px-4 py-2 text-sm text-[var(--foreground-muted)]">
                    Bcc
                  </label>
                  <input
                    type="text"
                    value={bcc}
                    onChange={(e) => setBcc(e.target.value)}
                    placeholder="Blind carbon copy"
                    className={cn(
                      'flex-1 px-2 py-2 text-sm bg-transparent',
                      'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                      'focus:outline-none'
                    )}
                  />
                </div>
              </>
            )}

            {/* Subject */}
            <div className="flex items-center border-b border-[var(--border)]">
              <label className="w-16 px-4 py-2 text-sm text-[var(--foreground-muted)]">
                Subject
              </label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Subject"
                className={cn(
                  'flex-1 px-2 py-2 text-sm bg-transparent',
                  'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                  'focus:outline-none'
                )}
              />
            </div>

            {/* Content */}
            <div className="flex-1 overflow-hidden">
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Write your message..."
                className={cn(
                  'w-full h-full p-4 text-sm bg-transparent resize-none',
                  'text-[var(--foreground)] placeholder:text-[var(--foreground-muted)]',
                  'focus:outline-none'
                )}
              />
            </div>

            {/* Attachments */}
            {attachments.length > 0 && (
              <div className="px-4 py-2 border-t border-[var(--border)]">
                <div className="flex flex-wrap gap-2">
                  {attachments.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-2 px-2 py-1 rounded bg-[var(--background-elevated)] text-sm"
                    >
                      <Paperclip className="w-3 h-3 text-[var(--foreground-muted)]" />
                      <span className="text-[var(--foreground)] truncate max-w-[100px]">
                        {item.file.name}
                      </span>
                      {item.isUploading && (
                        <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
                      )}
                      <button
                        onClick={() => removeAttachment(index)}
                        className="text-[var(--foreground-muted)] hover:text-[var(--error)]"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--border)]">
            <div className="flex items-center gap-2">
              <label className="cursor-pointer">
                <input
                  type="file"
                  multiple
                  onChange={handleAttachFile}
                  className="hidden"
                />
                <div className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors" title="Attach file">
                  <Paperclip className="w-5 h-5" />
                </div>
              </label>
              
              <button
                onClick={onClose}
                className="p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
                title="Discard"
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleSave}
                disabled={isActionDisabled || !subject}
                className={cn(
                  'px-3 py-2 rounded-lg font-medium transition-all flex items-center gap-2',
                  'text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)]',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {isSavingDraft ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                    <Save className="w-4 h-4" />
                )}
                Save Draft
              </button>
              
              <button
                onClick={handleSend}
                disabled={isActionDisabled}
                className={cn(
                  'px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2',
                  'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {isSending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send className="w-4 h-4" />
                    Send
                  </>
                )}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
