'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import {
  ZohoConnectBanner,
  FolderSidebar,
  EmailList,
  EmailViewer,
  EmailCompose,
  type ComposeData,
} from '@/components/email';
import type {
  ZohoConnectionStatus,
  EmailFolder,
  EmailSummary,
  EmailDetail,
} from '@/lib/api/email/email.types';

// Helper function to convert HTML to plain text (handles Zoho email HTML with embedded styles)
function htmlToPlainText(html: string): string {
  if (!html) return '';

  // Pre-process: Remove CSS blocks that might not be in proper style tags
  // Zoho emails often have CSS with unique selectors like div.zm_xxxxx
  let cleanedHtml = html
    // Remove inline style blocks with Zoho patterns
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    // Remove any text that looks like CSS rules (Zoho specific patterns)
    .replace(/div\.zm_[\w]+_parse_[\w]+[^{]*\{[^}]*\}/g, '')
    // Remove CSS rule declarations that leaked as text
    .replace(/[\w.-]+\s*\{[^}]*\}/g, '');

  // Create a temporary element to parse HTML
  const temp = document.createElement('div');
  temp.innerHTML = cleanedHtml;

  // Remove style tags (prevents CSS rules from appearing in text)
  const styleTags = temp.querySelectorAll('style');
  styleTags.forEach(tag => tag.remove());

  // Remove script tags (safety)
  const scriptTags = temp.querySelectorAll('script');
  scriptTags.forEach(tag => tag.remove());

  // Remove head tag if present
  const headTags = temp.querySelectorAll('head');
  headTags.forEach(tag => tag.remove());

  // Convert <br> to newlines before extracting text
  const brTags = temp.querySelectorAll('br');
  brTags.forEach(tag => tag.replaceWith('\n'));

  // Convert block elements to ensure newlines
  const blockElements = temp.querySelectorAll('p, div, h1, h2, h3, h4, h5, h6, li, tr');
  blockElements.forEach(el => {
    if (el.textContent?.trim()) {
      el.insertAdjacentText('afterend', '\n');
    }
  });

  // Get text content
  let text = temp.textContent || temp.innerText || '';

  // Post-process: Remove any remaining CSS-like patterns that leaked through
  text = text
    // Remove Zoho CSS selector patterns (div.zm_xxx, span.zm_xxx, etc.)
    .replace(/(?:div|span|td|tr|a|p|html|body)\.zm_[\w]+[\w\s,.-]*(?:\{[^}]*\})?/gi, '')
    // Remove CSS property declarations that leaked (property: value !important; patterns)
    .replace(/[\w-]+:\s*[^;{}\n]+\s*!?important?\s*;?/gi, (match) => {
      // Only remove if it looks like CSS (has common CSS properties)
      const cssProps = ['border', 'margin', 'padding', 'color', 'font', 'text', 'display', 'background', 'width', 'height', 'outline'];
      if (cssProps.some(prop => match.toLowerCase().startsWith(prop))) {
        return '';
      }
      return match;
    })
    // Remove standalone CSS-like class selectors
    .replace(/^[>\s]*[.#]?[\w-]+\s*,?\s*$/gm, '');

  // Clean up whitespace
  text = text
    .replace(/\t/g, ' ')                    // Replace tabs with spaces
    .replace(/ {2,}/g, ' ')                 // Collapse multiple spaces
    .replace(/\n{3,}/g, '\n\n')             // Normalize multiple newlines
    .replace(/^\s+|\s+$/gm, '')             // Trim each line
    .split('\n')
    .filter((line, i, arr) => line.trim() || (arr[i-1]?.trim() && arr[i+1]?.trim())) // Remove consecutive empty lines
    .join('\n');

  return text.trim();
}

// Helper function to format date safely
function formatDateSafe(dateStr: string | undefined): string {
  if (!dateStr) return 'Unknown date';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return 'Unknown date';
    return date.toLocaleString();
  } catch {
    return 'Unknown date';
  }
}

export default function EmailPage() {
  // Connection state
  const [connectionStatus, setConnectionStatus] = useState<ZohoConnectionStatus | null>(null);
  const [isCheckingConnection, setIsCheckingConnection] = useState(true);
  const [isConnecting, setIsConnecting] = useState(false);

  // Folders state
  const [folders, setFolders] = useState<EmailFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [isFoldersLoading, setIsFoldersLoading] = useState(false);

  // Emails state
  const [emails, setEmails] = useState<EmailSummary[]>([]);
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const [selectedEmail, setSelectedEmail] = useState<EmailDetail | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isEmailsLoading, setIsEmailsLoading] = useState(false);
  const [isEmailDetailLoading, setIsEmailDetailLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [hasMore, setHasMore] = useState(false);
  const [totalEmails, setTotalEmails] = useState(0);

  // Compose state
  const [isComposeOpen, setIsComposeOpen] = useState(false);
  const [composeMode, setComposeMode] = useState<'new' | 'reply' | 'replyAll' | 'forward'>('new');
  const [composeInitialData, setComposeInitialData] = useState<Partial<ComposeData>>({});
  const [isSending, setIsSending] = useState(false);

  // Check connection status
  const checkConnection = useCallback(async () => {
    setIsCheckingConnection(true);
    try {
      const status = await api.email.getConnectionStatus();
      setConnectionStatus(status);

      if (status.connected) {
        await loadFolders();
      }
    } catch (error) {
      console.error('Failed to check connection:', error);
      setConnectionStatus({ connected: false, email: null, account_id: null, expires_at: null });
    } finally {
      setIsCheckingConnection(false);
    }
  }, []);

  // Load folders
  const loadFolders = async () => {
    setIsFoldersLoading(true);
    try {
      const response = await api.email.getFolders();
      setFolders(response.folders);

      // Select inbox by default
      const inbox = response.folders.find((f) => f.folder_type === 'inbox');
      if (inbox && !selectedFolderId) {
        setSelectedFolderId(inbox.folder_id);
      }
    } catch (error) {
      console.error('Failed to load folders:', error);
    } finally {
      setIsFoldersLoading(false);
    }
  };

  // Load emails
  const loadEmails = useCallback(async (folderId: string, search?: string) => {
    setIsEmailsLoading(true);
    try {
      const response = await api.email.listEmails({
        folder_id: folderId,
        query: search,
        limit: 50,
      });
      setEmails(response.emails);
      setHasMore(response.has_more);
      setTotalEmails(response.total);
    } catch (error) {
      console.error('Failed to load emails:', error);
    } finally {
      setIsEmailsLoading(false);
    }
  }, []);

  // Load email detail
  const loadEmailDetail = async (messageId: string, folderId?: string) => {
    setIsEmailDetailLoading(true);
    try {
      const email = await api.email.getEmail(messageId, folderId);
      setSelectedEmail(email);

      // Mark as read if unread
      if (!email.is_read) {
        await api.email.markRead({ message_ids: [messageId], is_read: true });
        setEmails((prev) =>
          prev.map((e) => (e.message_id === messageId ? { ...e, is_read: true } : e))
        );
      }
    } catch (error) {
      console.error('Failed to load email:', error);
    } finally {
      setIsEmailDetailLoading(false);
    }
  };

  // Handle connect
  const handleConnect = async () => {
    setIsConnecting(true);
    try {
      const { auth_url } = await api.email.getAuthUrl();
      // Redirect to Zoho OAuth
      window.location.href = auth_url;
    } catch (error) {
      console.error('Failed to get auth URL:', error);
      setIsConnecting(false);
    }
  };

  // Handle disconnect
  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect your Zoho Mail account?')) return;

    try {
      await api.email.disconnect();
      setConnectionStatus({ connected: false, email: null, account_id: null, expires_at: null });
      setFolders([]);
      setEmails([]);
      setSelectedEmail(null);
    } catch (error) {
      console.error('Failed to disconnect:', error);
    }
  };

  // Handle folder selection
  const handleSelectFolder = (folderId: string) => {
    setSelectedFolderId(folderId);
    setSelectedEmailId(null);
    setSelectedEmail(null);
    setSelectedIds(new Set());
    setSearchQuery('');
  };

  // Handle email selection
  const handleSelectEmail = (emailId: string) => {
    setSelectedEmailId(emailId);
    loadEmailDetail(emailId, selectedFolderId || undefined);
  };

  // Handle toggle select
  const handleToggleSelect = (emailId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(emailId)) {
        next.delete(emailId);
      } else {
        next.add(emailId);
      }
      return next;
    });
  };

  // Handle select all
  const handleSelectAll = (select: boolean) => {
    if (select) {
      setSelectedIds(new Set(emails.map((e) => e.message_id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  // Handle mark read
  const handleMarkRead = async (emailIds: string[], isRead: boolean) => {
    try {
      await api.email.markRead({ message_ids: emailIds, is_read: isRead });
      setEmails((prev) =>
        prev.map((e) => (emailIds.includes(e.message_id) ? { ...e, is_read: isRead } : e))
      );
      setSelectedIds(new Set());
    } catch (error) {
      console.error('Failed to mark emails:', error);
    }
  };

  // Handle toggle flag
  const handleToggleFlag = async (emailId: string) => {
    const email = emails.find((e) => e.message_id === emailId);
    if (!email) return;

    const newFlagged = !email.is_flagged;
    try {
      await api.email.toggleFlag(emailId, newFlagged);
      setEmails((prev) =>
        prev.map((e) => (e.message_id === emailId ? { ...e, is_flagged: newFlagged } : e))
      );
      if (selectedEmail?.message_id === emailId) {
        setSelectedEmail({ ...selectedEmail, is_flagged: newFlagged });
      }
    } catch (error) {
      console.error('Failed to toggle flag:', error);
    }
  };

  // Handle delete
  const handleDelete = async (emailIds: string[]) => {
    if (!confirm(`Delete ${emailIds.length} email(s)?`)) return;

    try {
      await api.email.deleteEmails(emailIds);
      setEmails((prev) => prev.filter((e) => !emailIds.includes(e.message_id)));
      if (selectedEmailId && emailIds.includes(selectedEmailId)) {
        setSelectedEmailId(null);
        setSelectedEmail(null);
      }
      setSelectedIds(new Set());
    } catch (error) {
      console.error('Failed to delete emails:', error);
    }
  };

  // Handle search
  const handleSearch = (query: string) => {
    setSearchQuery(query);
    if (selectedFolderId) {
      loadEmails(selectedFolderId, query);
    }
  };

  // Handle compose
  const handleCompose = () => {
    setComposeMode('new');
    setComposeInitialData({});
    setIsComposeOpen(true);
  };

  // Handle reply
  const handleReply = () => {
    if (!selectedEmail) return;
    setComposeMode('reply');

    // Convert HTML to plain text for the textarea
    const originalContent = htmlToPlainText(selectedEmail.html_content || selectedEmail.text_content || '');
    const quotedContent = originalContent.split('\n').map(line => `> ${line}`).join('\n');

    setComposeInitialData({
      to: [selectedEmail.from.address],
      subject: `Re: ${selectedEmail.subject}`,
      htmlContent: `\n\nOn ${formatDateSafe(selectedEmail.date)}, ${
        selectedEmail.from.name || selectedEmail.from.address
      } wrote:\n\n${quotedContent}`,
    });
    setIsComposeOpen(true);
  };

  // Handle reply all
  const handleReplyAll = () => {
    if (!selectedEmail) return;
    const allRecipients = [
      selectedEmail.from.address,
      ...selectedEmail.to.map((t) => t.address),
      ...(selectedEmail.cc?.map((c) => c.address) || []),
    ];
    // Remove duplicates
    const uniqueRecipients = [...new Set(allRecipients)];

    // Convert HTML to plain text for the textarea
    const originalContent = htmlToPlainText(selectedEmail.html_content || selectedEmail.text_content || '');
    const quotedContent = originalContent.split('\n').map(line => `> ${line}`).join('\n');

    setComposeMode('replyAll');
    setComposeInitialData({
      to: uniqueRecipients,
      subject: `Re: ${selectedEmail.subject}`,
      htmlContent: `\n\nOn ${formatDateSafe(selectedEmail.date)}, ${
        selectedEmail.from.name || selectedEmail.from.address
      } wrote:\n\n${quotedContent}`,
    });
    setIsComposeOpen(true);
  };

  // Handle forward
  const handleForward = () => {
    if (!selectedEmail) return;
    setComposeMode('forward');

    // Convert HTML to plain text for the textarea
    const originalContent = htmlToPlainText(selectedEmail.html_content || selectedEmail.text_content || '');

    setComposeInitialData({
      to: [],
      subject: `Fwd: ${selectedEmail.subject}`,
      htmlContent: `\n\n---------- Forwarded message ----------
From: ${selectedEmail.from.name || selectedEmail.from.address} <${selectedEmail.from.address}>
Date: ${formatDateSafe(selectedEmail.date)}
Subject: ${selectedEmail.subject}
To: ${selectedEmail.to.map((t) => `${t.name || ''} <${t.address}>`).join(', ')}

${originalContent}`,
    });
    setIsComposeOpen(true);
  };

  // Handle send email
  const handleSendEmail = async (data: ComposeData) => {
    setIsSending(true);
    try {
      if (composeMode === 'reply' || composeMode === 'replyAll') {
        if (selectedEmailId) {
          await api.email.replyEmail(selectedEmailId, {
            content: data.htmlContent,
            reply_all: composeMode === 'replyAll',
          });
        }
      } else if (composeMode === 'forward') {
        if (selectedEmailId) {
          await api.email.forwardEmail(selectedEmailId, {
            to: data.to,
            cc: data.cc,
            content: data.htmlContent,
          });
        }
      } else {
        await api.email.sendEmail({
          to: data.to,
          cc: data.cc,
          bcc: data.bcc,
          subject: data.subject,
          html_content: data.htmlContent,
        });
      }

      setIsComposeOpen(false);
      // Refresh emails if in sent folder
      if (selectedFolderId) {
        loadEmails(selectedFolderId, searchQuery);
      }
    } catch (error) {
      console.error('Failed to send email:', error);
      alert('Failed to send email. Please try again.');
    } finally {
      setIsSending(false);
    }
  };

  // Handle download attachment
  const handleDownloadAttachment = async (attachmentId: string, filename: string) => {
    if (!selectedEmailId) return;

    try {
      const blob = await api.email.downloadAttachment(selectedEmailId, attachmentId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download attachment:', error);
    }
  };

  // Handle add to CRM
  const handleAddToCRM = async (email: string, name: string) => {
    const displayName = name || email.split('@')[0];
    if (!confirm(`Aggiungere "${displayName}" (${email}) come nuovo cliente in CRM?`)) return;

    try {
      const client = await api.crm.createClient(
        {
          full_name: name || email.split('@')[0],
          email: email,
        },
        connectionStatus?.email || 'email_import'
      );

      alert(`Cliente "${client.full_name}" creato con successo! ID: ${client.id}`);

      // Reload email detail to refresh the CRM badge
      if (selectedEmailId && selectedFolderId) {
        loadEmailDetail(selectedEmailId, selectedFolderId);
      }
    } catch (error) {
      console.error('Failed to create client:', error);
      alert('Errore nella creazione del cliente. Riprova.');
    }
  };

  // Handle refresh
  const handleRefresh = async () => {
    await loadFolders();
    if (selectedFolderId) {
      await loadEmails(selectedFolderId, searchQuery);
    }
  };

  // Initial load
  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  // Load emails when folder changes
  useEffect(() => {
    if (selectedFolderId && connectionStatus?.connected) {
      loadEmails(selectedFolderId, searchQuery);
    }
  }, [selectedFolderId, connectionStatus?.connected, loadEmails]);

  // Loading state
  if (isCheckingConnection) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-10 h-10 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-[var(--foreground-muted)]">Checking connection...</p>
        </div>
      </div>
    );
  }

  // Not connected state
  if (!connectionStatus?.connected) {
    return <ZohoConnectBanner onConnect={handleConnect} isConnecting={isConnecting} />;
  }

  // Main email interface
  return (
    <div className="email-module h-[calc(100vh-8rem)] -m-4 md:-m-6 lg:-m-8 flex">
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
          onLoadMore={() => {}}
          totalEmails={totalEmails}
        />
      </div>

      {/* Email Viewer */}
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

      {/* Compose Modal */}
      <EmailCompose
        isOpen={isComposeOpen}
        onClose={() => setIsComposeOpen(false)}
        onSend={handleSendEmail}
        onSaveDraft={() => {}}
        initialData={composeInitialData}
        mode={composeMode}
        isSending={isSending}
      />
    </div>
  );
}
