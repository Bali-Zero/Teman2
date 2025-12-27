'use client';

import { X, ExternalLink, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Source } from '@/types';

export interface ChatSourcesPanelProps {
  sources: Source[];
  isOpen: boolean;
  onClose: () => void;
}

export function ChatSourcesPanel({
  sources,
  isOpen,
  onClose,
}: ChatSourcesPanelProps) {
  if (!isOpen || sources.length === 0) {
    return null;
  }

  return (
    <div className="fixed right-0 top-14 bottom-0 w-80 bg-[var(--background-secondary)] border-l border-[var(--border)] shadow-lg z-40 animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <h3 className="text-sm font-semibold text-[var(--foreground)]">
          Sources ({sources.length})
        </h3>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-7 w-7"
          aria-label="Close sources panel"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Sources List */}
      <div className="overflow-y-auto h-[calc(100%-52px)] p-4 space-y-3">
        {sources.map((source, index) => (
          <div
            key={source.id || index}
            className="p-3 rounded-lg bg-[var(--background)] border border-[var(--border)] hover:border-[var(--accent)]/50 transition-colors"
          >
            {/* Source Header */}
            <div className="flex items-start gap-2 mb-2">
              <FileText className="w-4 h-4 text-[var(--accent)] flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-medium text-[var(--foreground)] truncate">
                  {source.title || 'Untitled Source'}
                </h4>
                {source.collection && (
                  <span className="text-[10px] text-[var(--foreground-muted)] uppercase tracking-wider">
                    {source.collection}
                  </span>
                )}
              </div>
            </div>

            {/* Snippet */}
            {(source.snippet || source.content) && (
              <p className="text-xs text-[var(--foreground-secondary)] line-clamp-3 mb-2">
                {source.snippet || source.content}
              </p>
            )}

            {/* Score & Link */}
            <div className="flex items-center justify-between">
              {source.score !== undefined && (
                <span className="text-[10px] text-[var(--foreground-muted)]">
                  Relevance: {Math.round(source.score * 100)}%
                </span>
              )}
              {source.url && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
                >
                  <ExternalLink className="w-3 h-3" />
                  Open
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
