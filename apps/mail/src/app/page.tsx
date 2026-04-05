'use client';

import React, { useState, useEffect, useCallback, Suspense, lazy } from 'react';
import { emailApi } from '@/lib/api';
import { logger } from '@/lib/logger';
import {
  ZohoConnectBanner,
  FolderSidebar,
  EmailList,
  ThreadView,
  type ComposeData,
} from '@/components/email';
import type {
  ZohoConnectionStatus,
  EmailFolder,
  EmailSummary,
  EmailDetail,
} from '@/lib/email.types';

const EmailViewer = lazy(() =>
  import('@/components/email').then((m) => ({ default: m.EmailViewer }))
);
const EmailCompose = lazy(() =>
  import('@/components/email').then((m) => ({ default: m.EmailCompose }))
);

const ViewerSkeleton = () => (
  <div className="flex-1 flex flex-col bg-[var(--background)] animate-pulse">
    <div className="h-16 border-b border-[var(--border)] bg-[var(--background-secondary)]" />
    <div className="flex-1 p-6 space-y-4">
      <div className="h-8 bg-[var(--background-elevated)] rounded w-3/4" />
      <div className="h-4 bg-[var(--background-elevated)] rounded w-1/2" />
      <div className="space-y-2 mt-8">
        <div className="h-4 bg-[var(--background-elevated)] rounded" />
        <div className="h-4 bg-[var(--background-elevated)] rounded" />
        <div className="h-4 bg-[var(--background-elevated)] rounded w-2/3" />
      </div>
    </div>
  </div>
);

const ComposeSkeleton = () => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
    <div className="w-[600px] h-[500px] bg-[var(--background-secondary)] rounded-lg animate-pulse">
      <div className="h-14 border-b border-[var(--border)] bg-[var(--background-elevated)]" />
      <div className="p-6 space-y-4">
        <div className="h-10 bg-[var(--background-elevated)] rounded" />
        <div className="h-10 bg-[var(--background-elevated)] rounded" />
        <div className="h-64 bg-[var(--background-elevated)] rounded" />
      </div>
    </div>
  </div>
);

function htmlToPlainText(html: string): string {
  if (!html) return '';
  let cleanedHtml = html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/div\.zm_[\w]+_parse_[\w]+[^{]*\{[^}]*\}/g, '')
    .replace(/[\w.-]+\s*\{[^}]*\}/g, '');

  if (typeof document === 'undefined') return '';

  const temp = document.createElement('div');
  temp.innerHTML = cleanedHtml;

  temp.querySelectorAll('style').forEach((t) => t.remove());
  temp.querySelectorAll('script').forEach((t) => t.remove());
  temp.querySelectorAll('head').forEach((t) => t.remove());
  temp.querySelectorAll('br').forEach((t) => t.replaceWith('\n'));
  temp.querySelectorAll('p, div, h1, h2, h3, h4, h5, h6, li, tr').forEach((el) => {
    if (el.textContent?.trim()) el.insertAdjacentText('afterend', '\n');
  });

  let text = temp.textContent || '';
  text = text
    .replace(/(?:div|span|td|tr|a|p|html|body)\.zm_[\w]+[\w\s,.-]*(?:\{[^}]*\})?/gi, '')
    .replace(/[\w-]+:\s*[^;{}\n]+\s*!?important?\s*;?/gi, (match) => {
      const cssProps = [
        'border',
        'margin',
        'padding',
        'color',
        'font',
        'text',
        'display',
        'background',
        'width',
        'height',
        'outline',
      ];
      return cssProps.some((p) => match.toLowerCase().startsWith(p)) ? '' : match;
    })
    .replace(/^[>\s]*[.#]?[\w-]+\s*,?\s*$/gm, '')
    .replace(/\t/g, ' ')
    .replace(/ {2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/^\s+|\s+$/gm, '')
    .split('\n')
    .filter((line, i, arr) => line.trim() || (arr[i - 1]?.trim() && arr[i + 1]?.trim()))
    .join('\n');

  return text.trim();
}

function formatDateSafe(dateStr: string | undefined): string {
  if (!dateStr) return 'Unknown date';
  try {
    const timestamp = Number(dateStr);
    const date =
      !isNaN(timestamp) && timestamp > 1000000000000 ? new Date(timestamp) : new Date(dateStr);
    if (isNaN(date.getTime())) return 'Unknown date';
    return date.toLocaleString('it-IT', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return 'Unknown date';
  }
}

export default function MailPage() {
  const [connectionStatus, setConnectionStatus] = useState<ZohoConnectionStatus | null>(null);
  const [isCheckingConnection, setIsCheckingConnection] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);

  const [folders, setFolders] = useState<EmailFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [isFoldersLoading, setIsFoldersLoading] = useState(false);

  const [emails, setEmails] = useState<EmailSummary[]>([]);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [selectedEmail, setSelectedEmail] = useState<EmailDetail | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isEmailsLoading, setIsEmailsLoading] = useState(false);
  const [isEmailDetailLoading, setIsEmailDetailLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [hasMore, setHasMore] = useState(false);
  const [totalEmails, setTotalEmails] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);

  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const [composeMode, setComposeMode] = useState<'new' | 'reply' | 'replyAll' | 'forward'>('new');
  const [composeInitialData, setComposeInitialData] = useState<Partial<ComposeData>>({});
  const [isSending, setIsSending] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const showToast = (message: string, type: 'success' | 'error' = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadFolders = useCallback(async () => {
    setIsFoldersLoading(true);
    try {
      const response = await emailApi.getFolders();
      setFolders(response.folders);
      const inbox = response.folders.find((f) => f.folder_type === 'inbox');
      if (inbox) {
        setSelectedFolderId((prev) => prev ?? inbox.folder_id);
      }
    } catch (error) {
      logger.error(
        'Failed to load folders',
        { component: 'MailPage', action: 'loadFolders' },
        error instanceof Error ? error : undefined
      );
    } finally {
      setIsFoldersLoading(false);
    }
  }, []);

  const checkConnection = useCallback(async () => {
    setIsCheckingConnection(true);
    try {
      const status = await emailApi.getConnectionStatus();
      setConnectionStatus(status);
      if (status.connected) await loadFolders();
    } catch (error) {
      logger.error(
        'Failed to check connection',
        { component: 'MailPage', action: 'checkConnection' },
        error instanceof Error ? error : undefined
      );
      setConnectionStatus({
        connected: false,
        email: null,
        account_id: null,
        expires_at: null,
      });
    } finally {
      setIsCheckingConnection(false);
    }
  }, [loadFolders]);

  const loadEmails = useCallback(async (folderId: string, search?: string, page: number = 1) => {
    setIsEmailsLoading(true);
    try {
      const response = await emailApi.listEmails({
        folder_id: folderId,
        query: search,
        limit: 50,
        offset: (page - 1) * 50,
      });
      setEmails(response.emails);
      setHasMore(response.has_more);
      setTotalEmails(response.total);
    } catch (error) {
      logger.error(
        'Failed to load emails',
        { component: 'MailPage', action: 'loadEmails' },
        error instanceof Error ? error : undefined
      );
    } finally {
      setIsEmailsLoading(false);
    }
  }, []);

  const loadEmailDetail = async (messageId: string, folderId?: string) => {
    setIsEmailDetailLoading(true);
    try {
      const email = await emailApi.getEmail(messageId, folderId);
      setSelectedEmail(email);
      if (!email.is_read) {
        await emailApi.markRead({ message_ids: [messageId], is_read: true });
        setEmails((prev) =>
          prev.map((e) => (e.message_id === messageId ? { ...e, is_read: true } : e))
        );
      }
    } catch (error) {
      logger.error(
        'Failed to load email',
        { component: 'MailPage', action: 'loadEmail' },
        error instanceof Error ? error : undefined
      );
    } finally {
      setIsEmailDetailLoading(false);
    }
  };

  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      const { auth_url } = await emailApi.getAuthUrl();
      window.location.href = auth_url;
    } catch (error) {
      logger.error(
        'Failed to get auth URL',
        { component: 'MailPage', action: 'getAuthUrl' },
        error instanceof Error ? error : undefined
      );
      setIsConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect your Zoho Mail account?')) return;
    try {
      await emailApi.disconnect();
      setConnectionStatus({
        connected: false,
        email: null,
        account_id: null,
        expires_at: null,
      });
      setFolders([]);
      setEmails([]);
      setSelectedEmail(null);
    } catch (error) {
      logger.error(
        'Failed to disconnect',
        { component: 'MailPage', action: 'disconnect' },
        error instanceof Error ? error : undefined
      );
    }
  };

  const handleSelectFolder = (folderId: string) => {
    setSelectedFolderId(folderId);
    setSelectedEmailId(null);
    setSelectedEmail(null);
    setSelectedIds(new Set());
    setSearchQuery('');
    setCurrentPage(1);
  };

  const handleSelectEmail = (emailId: string) => {
    setSelectedEmailId(emailId);
    loadEmailDetail(emailId, selectedFolderId || undefined);
  };

  const handleToggleSelect = (emailId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(emailId) ? next.delete(emailId) : next.add(emailId);
      return next;
    });
  };

  const handleSelectAll = (select: boolean) => {
    setSelectedIds(select ? new Set(emails.map((e) => e.message_id)) : new Set());
  };

  const handleMarkRead = async (emailIds: string[], isRead: boolean) => {
    try {
      await emailApi.markRead({ message_ids: emailIds, is_read: isRead });
      setEmails((prev) =>
        prev.map((e) => (emailIds.includes(e.message_id) ? { ...e, is_read: isRead } : e))
      );
      setSelectedIds(new Set());
    } catch (error) {
      logger.error(
        'Failed to mark emails',
        { component: 'MailPage', action: 'markEmails' },
        error instanceof Error ? error : undefined
      );
    }
  };

  const handleToggleFlag = async (emailId: string) => {
    const email = emails.find((e) => e.message_id === emailId);
    if (!email) return;
    const newFlagged = !email.is_flagged;
    try {
      await emailApi.toggleFlag(emailId, newFlagged);
      setEmails((prev) =>
        prev.map((e) => (e.message_id === emailId ? { ...e, is_flagged: newFlagged } : e))
      );
      if (selectedEmail?.message_id === emailId) {
        setSelectedEmail({ ...selectedEmail, is_flagged: newFlagged });
      }
    } catch (error) {
      logger.error(
        'Failed to toggle flag',
        { component: 'MailPage', action: 'toggleFlag' },
        error instanceof Error ? error : undefined
      );
    }
  };

  const handleDelete = async (emailIds: string[]) => {
    if (!confirm(`Eliminare ${emailIds.length} email?`)) return;
    try {
      const result = await emailApi.deleteEmails(emailIds);
      if (result.success) {
        setEmails((prev) => prev.filter((e) => !emailIds.includes(e.message_id)));
        if (selectedEmailId && emailIds.includes(selectedEmailId)) {
          setSelectedEmailId(null);
          setSelectedEmail(null);
        }
        setSelectedIds(new Set());
        showToast(`${emailIds.length} email eliminate con successo`);
      } else {
        throw new Error('Delete operation failed');
      }
    } catch (error) {
      logger.error(
        'Failed to delete emails',
        { component: 'MailPage', action: 'deleteEmails' },
        error instanceof Error ? error : undefined
      );
      showToast('Impossibile eliminare le email', 'error');
    }
  };

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    setCurrentPage(1);
    if (selectedFolderId) loadEmails(selectedFolderId, query, 1);
  };

  const handleLoadMore = () => {
    if (!hasMore) return;
    const nextPage = currentPage + 1;
    setCurrentPage(nextPage);
    if (selectedFolderId) loadEmails(selectedFolderId, searchQuery, nextPage);
  };

  const handlePreviousPage = () => {
    if (currentPage <= 1) return;
    const prevPage = currentPage - 1;
    setCurrentPage(prevPage);
    if (selectedFolderId) loadEmails(selectedFolderId, searchQuery, prevPage);
  };

  const handleSaveDraft = async (data: ComposeData) => {
    try {
      await emailApi.saveDraft({
        to: data.to,
        cc: data.cc,
        bcc: data.bcc,
        subject: data.subject,
        html_content: data.htmlContent,
        attachment_ids: data.attachmentIds,
      });
      setIsComposeOpen(false);
      showToast('Bozza salvata');
      if (selectedFolderId) loadEmails(selectedFolderId, searchQuery, currentPage);
    } catch (error) {
      logger.error(
        'Failed to save draft',
        { component: 'MailPage', action: 'saveDraft' },
        error instanceof Error ? error : undefined
      );
      showToast('Impossibile salvare la bozza', 'error');
    }
  };

  const handleCompose = () => {
    setComposeMode('new');
    setComposeInitialData({});
    setIsComposeOpen(true);
  };

  const handleReply = () => {
    if (!selectedEmail) return;
    setComposeMode('reply');
    const original = htmlToPlainText(
      selectedEmail.html_content || selectedEmail.text_content || ''
    );
    const quoted = original
      .split('\n')
      .map((l) => `> ${l}`)
      .join('\n');
    setComposeInitialData({
      to: [selectedEmail.from.address],
      subject: `Re: ${selectedEmail.subject}`,
      htmlContent: `\n\nOn ${formatDateSafe(selectedEmail.date)}, ${
        selectedEmail.from.name || selectedEmail.from.address
      } wrote:\n\n${quoted}`,
    });
    setIsComposeOpen(true);
  };

  const handleReplyAll = () => {
    if (!selectedEmail) return;
    const allRecipients = [
      selectedEmail.from.address,
      ...selectedEmail.to.map((t) => t.address),
      ...(selectedEmail.cc?.map((c) => c.address) || []),
    ];
    const uniqueRecipients = Array.from(new Set(allRecipients));
    const original = htmlToPlainText(
      selectedEmail.html_content || selectedEmail.text_content || ''
    );
    const quoted = original
      .split('\n')
      .map((l) => `> ${l}`)
      .join('\n');
    setComposeMode('replyAll');
    setComposeInitialData({
      to: uniqueRecipients,
      subject: `Re: ${selectedEmail.subject}`,
      htmlContent: `\n\nOn ${formatDateSafe(selectedEmail.date)}, ${
        selectedEmail.from.name || selectedEmail.from.address
      } wrote:\n\n${quoted}`,
    });
    setIsComposeOpen(true);
  };

  const handleForward = () => {
    if (!selectedEmail) return;
    setComposeMode('forward');
    const original = htmlToPlainText(
      selectedEmail.html_content || selectedEmail.text_content || ''
    );
    setComposeInitialData({
      to: [],
      subject: `Fwd: ${selectedEmail.subject}`,
      htmlContent: `\n\n---------- Forwarded message ----------
From: ${selectedEmail.from.name || selectedEmail.from.address} <${selectedEmail.from.address}>
Date: ${formatDateSafe(selectedEmail.date)}
Subject: ${selectedEmail.subject}
To: ${selectedEmail.to.map((t) => `${t.name || ''} <${t.address}>`).join(', ')}

${original}`,
    });
    setIsComposeOpen(true);
  };

  const handleSendEmail = async (data: ComposeData) => {
    setIsSending(true);
    try {
      if (composeMode === 'reply' || composeMode === 'replyAll') {
        if (selectedEmailId) {
          const toAddress = data.to[0] || selectedEmail?.from.address || '';
          const ccAddresses =
            composeMode === 'replyAll' && data.cc?.length ? data.cc.join(',') : undefined;
          await emailApi.replyEmail(selectedEmailId, {
            content: data.htmlContent,
            reply_all: composeMode === 'replyAll',
            to: toAddress,
            cc: ccAddresses,
          });
        }
      } else if (composeMode === 'forward') {
        if (selectedEmailId) {
          await emailApi.forwardEmail(selectedEmailId, {
            to: data.to,
            cc: data.cc,
            content: data.htmlContent,
          });
        }
      } else {
        await emailApi.sendEmail({
          to: data.to,
          cc: data.cc,
          bcc: data.bcc,
          subject: data.subject,
          html_content: data.htmlContent,
          attachment_ids: data.attachmentIds,
        });
      }
      setIsComposeOpen(false);
      if (selectedFolderId) loadEmails(selectedFolderId, searchQuery);
    } catch (error) {
      logger.error(
        'Failed to send email',
        { component: 'MailPage', action: 'sendEmail' },
        error instanceof Error ? error : undefined
      );
      showToast('Impossibile inviare email', 'error');
    } finally {
      setIsSending(false);
    }
  };

  const handleDownloadAttachment = async (attachmentId: string, filename: string) => {
    if (!selectedEmailId) return;
    try {
      const blob = await emailApi.downloadAttachment(selectedEmailId, attachmentId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      logger.error(
        'Failed to download attachment',
        { component: 'MailPage', action: 'downloadAttachment' },
        error instanceof Error ? error : undefined
      );
    }
  };

  const handleAddToCRM = async (email: string, name: string) => {
    const displayName = name || email.split('@')[0];
    if (!confirm(`Aggiungere "${displayName}" (${email}) come nuovo cliente in CRM?`)) return;
    try {
      const client = await emailApi.createClient(
        {
          full_name: name || email.split('@')[0],
          email,
        },
        connectionStatus?.email || 'email_import'
      );
      showToast(`Cliente "${client.full_name}" creato`);
      if (selectedEmailId && selectedFolderId) {
        loadEmailDetail(selectedEmailId, selectedFolderId);
      }
    } catch (error) {
      logger.error(
        'Failed to create client',
        { component: 'MailPage', action: 'createClient' },
        error instanceof Error ? error : undefined
      );
      showToast('Errore nella creazione del cliente', 'error');
    }
  };

  const handleRefresh = async () => {
    await loadFolders();
    if (selectedFolderId) await loadEmails(selectedFolderId, searchQuery);
  };

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    if (selectedFolderId && connectionStatus?.connected) {
      loadEmails(selectedFolderId, searchQuery, 1);
    }
  }, [selectedFolderId, connectionStatus?.connected, loadEmails]);

  if (isCheckingConnection) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[var(--foreground-muted)]">Checking connection...</p>
        </div>
      </div>
    );
  }

  if (!connectionStatus?.connected) {
    return <ZohoConnectBanner onConnect={handleConnect} isConnecting={isConnecting} />;
  }

  return (
    <div className="h-full flex">
      {/* Folder Sidebar */}
      <FolderSidebar
        folders={folders}
        selectedFolderId={selectedFolderId}
        onSelectFolder={handleSelectFolder}
        onCompose={handleCompose}
        onRefresh={handleRefresh}
        onDisconnect={handleDisconnect}
        isLoading={isFoldersLoading}
        connectedEmail={connectionStatus.email || undefined}
      />

      {/* Email List */}
      <div className="w-96 border-r border-[var(--border)] bg-[var(--background)]">
        <EmailList
          emails={emails}
          selectedEmailId={selectedEmailId}
          selectedIds={selectedIds}
          onSelectEmail={handleSelectEmail}
          onToggleSelect={handleToggleSelect}
          onSelectAll={handleSelectAll}
          onMarkRead={handleMarkRead}
          onToggleFlag={handleToggleFlag}
          onDelete={handleDelete}
          onSearch={handleSearch}
          searchQuery={searchQuery}
          isLoading={isEmailsLoading}
          hasMore={hasMore}
          onLoadMore={handleLoadMore}
          onPreviousPage={handlePreviousPage}
          currentPage={currentPage}
          totalEmails={totalEmails}
        />
      </div>

      {/* Email Viewer + Thread View */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Suspense fallback={<ViewerSkeleton />}>
          <EmailViewer
            email={selectedEmail}
            onClose={() => {
              setSelectedEmailId(null);
              setSelectedEmail(null);
            }}
            onReply={handleReply}
            onReplyAll={handleReplyAll}
            onForward={handleForward}
            onToggleFlag={() => selectedEmailId && handleToggleFlag(selectedEmailId)}
            onDelete={() => selectedEmailId && handleDelete([selectedEmailId])}
            onDownloadAttachment={handleDownloadAttachment}
            isLoading={isEmailDetailLoading}
            onAddToCRM={handleAddToCRM}
          />
        </Suspense>
        <ThreadView
          emails={emails}
          selectedEmail={selectedEmail}
          selectedEmailId={selectedEmailId}
          onSelectEmail={handleSelectEmail}
          onReply={handleReply}
          onDownloadAttachment={handleDownloadAttachment}
        />
      </div>

      {/* Compose Modal */}
      {isComposeOpen && (
        <Suspense fallback={<ComposeSkeleton />}>
          <EmailCompose
            isOpen={isComposeOpen}
            onClose={() => setIsComposeOpen(false)}
            onSend={handleSendEmail}
            onSaveDraft={handleSaveDraft}
            initialData={composeInitialData}
            mode={composeMode}
            isSending={isSending}
          />
        </Suspense>
      )}

      {/* Toast notification */}
      {toast && (
        <div
          role="alert"
          className={`fixed bottom-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-lg text-sm font-medium shadow-lg backdrop-blur-sm transition-all ${
            toast.type === 'error'
              ? 'bg-red-900/80 text-red-200 border border-red-700/50'
              : 'bg-emerald-900/80 text-emerald-200 border border-emerald-700/50'
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
