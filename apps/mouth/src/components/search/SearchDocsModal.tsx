'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { X, Loader2, ExternalLink, Copy, Check, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api, KnowledgeSearchResult } from '@/lib/api';

function formatCitation(result: KnowledgeSearchResult): string {
  const title = result.metadata.book_title || 'Untitled';
  const author = result.metadata.book_author || 'Unknown';
  const tier = result.metadata.tier || 'C';
  const page =
    typeof result.metadata.page_number === 'number' ? `p.${result.metadata.page_number}` : 'p.?';
  const scorePct = Number.isFinite(result.similarity_score)
    ? `${Math.round(result.similarity_score * 100)}%`
    : '?';

  const file = result.metadata.file_path ? `\nFile: ${result.metadata.file_path}` : '';

  return `Source: ${title} — ${author} (${tier}, ${page}, ${scorePct})${file}\nExcerpt: ${result.text}`;
}

function buildSourcesBlock(results: KnowledgeSearchResult[]): string {
  const lines: string[] = [];
  results.forEach((r, idx) => {
    lines.push(`\n[${idx + 1}]\n${formatCitation(r)}\n`);
  });
  return lines.join('\n');
}

export function SearchDocsModal({
  open,
  onClose,
  onInsert,
  initialQuery = '',
}: {
  open: boolean;
  onClose: () => void;
  onInsert: (text: string) => void;
  initialQuery?: string;
}) {
  const [query, setQuery] = useState(initialQuery);
  const [level, setLevel] = useState<number>(() => (api.isAdmin() ? 3 : 1));
  const [limit, setLimit] = useState<number>(8);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [totalFound, setTotalFound] = useState<number>(0);
  const [executionTimeMs, setExecutionTimeMs] = useState<number | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQuery(initialQuery);
    setError(null);
    setResults([]);
    setTotalFound(0);
    setExecutionTimeMs(null);
    setExpandedIds(new Set());
    setSelectedIds(new Set());
    setStatusMessage(null);
    const t = setTimeout(() => inputRef.current?.focus(), 0);
    return () => clearTimeout(t);
  }, [open, initialQuery]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [open]);

  const toggleExpanded = useCallback((idx: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const toggleSelected = useCallback((idx: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const selectedResults = useMemo(
    () => Array.from(selectedIds).sort((a, b) => a - b).map((i) => results[i]).filter(Boolean),
    [results, selectedIds]
  );

  const runSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;

    if (!api.isAuthenticated()) {
      setError('Authentication required');
      setStatusMessage('Authentication required. Please login to search the archive.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setStatusMessage(null);
    try {
      const resp = await api.searchDocs({ query: q, level, limit });
      setResults(resp.results || []);
      setTotalFound(resp.total_found || 0);
      setExecutionTimeMs(typeof resp.execution_time_ms === 'number' ? resp.execution_time_ms : null);
      setExpandedIds(new Set());
      setSelectedIds(new Set());
      if (!resp.results?.length) {
        setStatusMessage('No results found for this query.');
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Search failed';
      setError(message);
      setResults([]);
      setTotalFound(0);
      setExecutionTimeMs(null);
      if (/401|Authentication required/i.test(message)) {
        setStatusMessage('Authentication required. Please login to search the archive.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [query, level, limit]);

  const handleCopy = useCallback(async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 1200);
    } catch {
      // ignore
    }
  }, []);

  const handleInsertSelected = useCallback(() => {
    if (selectedResults.length === 0) return;
    const max = 5;
    const slice = selectedResults.slice(0, max);
    const sources = buildSourcesBlock(slice);
    onInsert(`\n\nUse these sources:\n${sources}\n`);
    onClose();
  }, [selectedResults, onInsert, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100]">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-[2px]" onClick={onClose} />

      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search docs"
        className="absolute left-1/2 top-1/2 w-[min(980px,calc(100vw-2rem))] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-white/10 bg-black/70 backdrop-blur-xl shadow-2xl overflow-hidden"
      >
        <div className="px-4 py-3 border-b border-white/10 flex items-center gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <Search className="w-4 h-4 text-white/70" />
            <h2 className="text-sm font-semibold text-white truncate">Search docs</h2>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="p-4 border-b border-white/10">
          <div className="flex flex-col md:flex-row gap-2">
            <div className="flex-1">
              <Input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search the knowledge base…"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') runSearch();
                }}
              />
            </div>

            <div className="flex gap-2 items-center">
              <label className="text-xs text-white/60 hidden sm:block">Level</label>
              <select
                value={level}
                onChange={(e) => setLevel(Number(e.target.value))}
                className="h-10 rounded-md border border-white/10 bg-black/30 px-2 text-sm text-white/80"
                aria-label="Access level"
              >
                <option value={0}>0</option>
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
              </select>

              <label className="text-xs text-white/60 hidden sm:block">Limit</label>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="h-10 rounded-md border border-white/10 bg-black/30 px-2 text-sm text-white/80"
                aria-label="Result limit"
              >
                <option value={5}>5</option>
                <option value={8}>8</option>
                <option value={10}>10</option>
                <option value={20}>20</option>
              </select>

              <Button onClick={runSearch} disabled={!query.trim() || isLoading}>
                {isLoading ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Searching…
                  </span>
                ) : (
                  'Search'
                )}
              </Button>
            </div>
          </div>

          <div className="mt-2 text-xs text-white/50 flex items-center gap-2">
            {executionTimeMs !== null && (
              <span>
                {totalFound} found • {executionTimeMs.toFixed(0)}ms
              </span>
            )}
            {selectedResults.length > 0 && (
              <span className="ml-auto">{selectedResults.length} selected</span>
            )}
          </div>
        </div>

        <div className="max-h-[60vh] overflow-y-auto">
          {error && (
            <div className="p-4">
              <div className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-200">
                <div className="flex items-start gap-2">
                  <span>{error}</span>
                  {statusMessage?.toLowerCase().includes('authentication') && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-auto text-red-200 hover:text-white"
                      onClick={() => {
                        window.location.href = '/login';
                      }}
                    >
                      Login
                    </Button>
                  )}
                </div>
              </div>
            </div>
          )}

          {isLoading && (
            <div className="p-6 text-center text-sm text-white/70 flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Searching…
            </div>
          )}

          {!error && !isLoading && results.length === 0 && (
            <div className="p-6 text-center text-sm text-white/60">
              {statusMessage || 'Search across the archive and pull verified excerpts into chat.'}
            </div>
          )}

          {results.length > 0 && (
            <div className="p-3 space-y-2">
              {results.map((r, idx) => {
                const isExpanded = expandedIds.has(idx);
                const isSelected = selectedIds.has(idx);
                const citation = formatCitation(r);
                const copyKey = `citation:${idx}`;
                const topics = r.metadata.topics ?? [];
                const fileUrl =
                  r.metadata.file_path?.startsWith('http://') ||
                  r.metadata.file_path?.startsWith('https://')
                    ? r.metadata.file_path
                    : null;

                return (
                  <div
                    key={`${r.metadata.file_path}-${r.metadata.chunk_index}-${idx}`}
                    className="rounded-xl border border-white/10 bg-black/40 hover:bg-black/50 transition-colors"
                  >
                    <div className="p-3 flex gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelected(idx)}
                        className="mt-1 accent-[var(--accent)]"
                        aria-label={`Select result ${idx + 1}`}
                      />

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start gap-2">
                          <div className="min-w-0 flex-1">
                            <div className="text-sm text-white font-medium truncate">
                              {r.metadata.book_title || 'Untitled'}
                            </div>
                            <div className="text-xs text-white/60 truncate">
                              {r.metadata.book_author || 'Unknown'}
                              {typeof r.metadata.page_number === 'number'
                                ? ` • p.${r.metadata.page_number}`
                                : ''}
                              {Number.isFinite(r.similarity_score)
                                ? ` • ${Math.round(r.similarity_score * 100)}%`
                                : ''}
                              {r.metadata.tier ? ` • Tier ${r.metadata.tier}` : ''}
                            </div>
                          </div>

                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 px-2"
                              onClick={() => {
                                onInsert(`\n\n${citation}\n`);
                                onClose();
                              }}
                            >
                              Insert
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => handleCopy(copyKey, citation)}
                              aria-label="Copy citation"
                            >
                              {copiedKey === copyKey ? (
                                <Check className="w-4 h-4" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8"
                              onClick={() => {
                                if (fileUrl) window.open(fileUrl, '_blank', 'noopener,noreferrer');
                                else toggleExpanded(idx);
                              }}
                              aria-label={fileUrl ? 'Open source' : 'Toggle details'}
                            >
                              {fileUrl ? <ExternalLink className="w-4 h-4" /> : <span className="text-xs text-white/70">⋯</span>}
                            </Button>
                          </div>
                        </div>

                        <div className="mt-2 text-sm text-white/80">
                          {isExpanded ? r.text : `${r.text.slice(0, 220)}${r.text.length > 220 ? '…' : ''}`}
                        </div>

                        {topics.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {topics.slice(0, 6).map((t) => (
                              <span
                                key={t}
                                className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-white/60"
                              >
                                {t}
                              </span>
                            ))}
                          </div>
                        )}

                        {!fileUrl && r.metadata.file_path && (
                          <button
                            type="button"
                            onClick={() => handleCopy(`file:${idx}`, r.metadata.file_path)}
                            className="mt-2 inline-flex items-center gap-1 text-xs text-white/50 hover:text-white/70"
                          >
                            <ExternalLink className="w-3 h-3" />
                            Copy file path
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="px-3 pb-3">
                      <button
                        type="button"
                        onClick={() => toggleExpanded(idx)}
                        className="text-xs text-white/50 hover:text-white/70"
                      >
                        {isExpanded ? 'Hide details' : 'Show details'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="px-4 py-3 border-t border-white/10 flex items-center gap-2">
          <div className="text-xs text-white/50">
            Tip: select multiple sources, then “Insert selected”.
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => {
                if (!query.trim()) return;
                onInsert(query.trim());
                onClose();
              }}
              disabled={!query.trim()}
            >
              Insert query
            </Button>
            <Button
              onClick={handleInsertSelected}
              disabled={selectedResults.length === 0 || isLoading || !!error}
            >
              Insert selected
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
