'use client';

import React from 'react';
import {
  Inbox,
  Send,
  FileText,
  Trash2,
  AlertOctagon,
  Folder,
  Plus,
  RefreshCw,
  LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { EmailFolder } from '@/lib/email.types';

const FOLDER_ICONS: Record<string, React.ElementType> = {
  inbox: Inbox,
  sent: Send,
  drafts: FileText,
  trash: Trash2,
  spam: AlertOctagon,
  custom: Folder,
};

interface FolderSidebarProps {
  folders: EmailFolder[];
  selectedFolderId: string | null;
  onSelectFolder: (folderId: string) => void;
  onCompose: () => void;
  onRefresh: () => void;
  onDisconnect: () => void;
  isLoading?: boolean;
  connectedEmail?: string;
}

export function FolderSidebar({
  folders,
  selectedFolderId,
  onSelectFolder,
  onCompose,
  onRefresh,
  onDisconnect,
  isLoading,
  connectedEmail,
}: FolderSidebarProps) {
  const sortedFolders = React.useMemo(() => {
    const order = ['inbox', 'sent', 'drafts', 'spam', 'trash'];
    return [...folders].sort((a, b) => {
      const aOrder = order.indexOf(a.folder_type);
      const bOrder = order.indexOf(b.folder_type);
      if (aOrder === -1 && bOrder === -1) return a.folder_name.localeCompare(b.folder_name);
      if (aOrder === -1) return 1;
      if (bOrder === -1) return -1;
      return aOrder - bOrder;
    });
  }, [folders]);

  return (
    <nav aria-label="Cartelle email" className="email-sidebar w-56 h-full flex flex-col border-r border-[var(--border)] bg-[var(--background-secondary)]">
      {/* Compose Button */}
      <div className="p-4">
        <button
          onClick={onCompose}
          className={cn(
            'w-full py-2.5 px-4 rounded-lg font-medium transition-all flex items-center justify-center gap-2',
            'bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white',
            'shadow-lg shadow-[var(--accent)]/20'
          )}
        >
          <Plus className="w-4 h-4" />
          Compose
        </button>
      </div>

      {/* Folders List */}
      <div className="flex-1 overflow-y-auto px-2">
        <div className="space-y-0.5">
          {isLoading
            ? Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 bg-[var(--background-elevated)] rounded-lg animate-pulse mx-2"
                />
              ))
            : sortedFolders.map((folder) => {
                const Icon = FOLDER_ICONS[folder.folder_type] || Folder;
                const isSelected = folder.folder_id === selectedFolderId;
                const hasUnread = folder.unread_count > 0;

                return (
                  <button
                    key={folder.folder_id}
                    onClick={() => onSelectFolder(folder.folder_id)}
                    aria-current={isSelected ? 'page' : undefined}
                    aria-label={hasUnread ? `${folder.folder_name} (${folder.unread_count} non lette)` : folder.folder_name}
                    className={cn(
                      'w-full px-3 py-2 rounded-lg text-sm transition-all',
                      'flex items-center justify-between gap-2',
                      isSelected
                        ? 'bg-[var(--accent)]/10 text-[var(--accent)] font-semibold'
                        : hasUnread
                          ? 'text-[var(--foreground)] font-semibold hover:bg-[var(--background-elevated)]'
                          : 'text-[var(--foreground-muted)] font-medium hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)]'
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Icon
                        className={cn(
                          'w-4 h-4 flex-shrink-0',
                          hasUnread && !isSelected && 'text-[var(--accent)]'
                        )}
                      />
                      <span className="truncate">{folder.folder_name}</span>
                    </div>
                    {hasUnread && (
                      <span
                        className={cn(
                          'text-xs font-bold px-2 py-0.5 rounded-full min-w-[22px] text-center',
                          'bg-[var(--accent)] text-white'
                        )}
                      >
                        {folder.unread_count > 99 ? '99+' : folder.unread_count}
                      </span>
                    )}
                  </button>
                );
              })}
        </div>
      </div>

      {/* Footer Actions */}
      <div className="p-3 border-t border-[var(--border)] space-y-2">
        {connectedEmail && (
          <div className="px-2 py-1.5 text-xs text-[var(--foreground-muted)] truncate">
            {connectedEmail}
          </div>
        )}
        <div className="flex items-center gap-1">
          <button
            onClick={onRefresh}
            className="flex-1 p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-elevated)] transition-colors"
            title="Refresh"
            aria-label="Aggiorna lista email"
          >
            <RefreshCw className="w-4 h-4 mx-auto" />
          </button>
          <button
            onClick={onDisconnect}
            className="flex-1 p-2 rounded-lg text-[var(--foreground-muted)] hover:text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
            title="Disconnect"
            aria-label="Disconnetti account Zoho Mail"
          >
            <LogOut className="w-4 h-4 mx-auto" />
          </button>
        </div>
      </div>
    </nav>
  );
}
