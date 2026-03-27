'use client';

import { useEffect, useState, useMemo } from 'react';
import { intelligenceApi, StagingItem } from '@/lib/api/intelligence.api';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';
import { toast as sonnerToast } from 'sonner';
import { logger } from '@/lib/logger';
import {
  Loader2,
  Check,
  X,
  ExternalLink,
  Sparkles,
  AlertTriangle,
  RefreshCw,
  Eye,
  Filter,
  ArrowUpDown,
  Search,
  CheckSquare,
  Square,
} from 'lucide-react';

type FilterType = 'all' | 'NEW' | 'UPDATED';
type SortType = 'date-desc' | 'date-asc' | 'title-asc' | 'title-desc';

export default function VisaOraclePage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState<string | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewContent, setPreviewContent] = useState<string>('');
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [filterType, setFilterType] = useState<FilterType>('all');
  const [sortType, setSortType] = useState<SortType>('date-desc');
  const [searchQuery, setSearchQuery] = useState('');
  const toast = useToast();

  // Filtered and sorted items
  const filteredAndSortedItems = useMemo(() => {
    let filtered = items;

    // Apply search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (item) =>
          item.title.toLowerCase().includes(query) ||
          item.id.toLowerCase().includes(query) ||
          item.source.toLowerCase().includes(query)
      );
    }

    // Apply type filter
    if (filterType !== 'all') {
      filtered = filtered.filter((item) => item.detection_type === filterType);
    }

    // Apply sorting
    const sorted = [...filtered].sort((a, b) => {
      switch (sortType) {
        case 'date-desc':
          return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
        case 'date-asc':
          return new Date(a.detected_at).getTime() - new Date(b.detected_at).getTime();
        case 'title-asc':
          return a.title.localeCompare(b.title);
        case 'title-desc':
          return b.title.localeCompare(a.title);
        default:
          return 0;
      }
    });

    return sorted;
  }, [items, filterType, sortType, searchQuery]);

  useEffect(() => {
    logger.componentMount('VisaOraclePage');
    loadItems();

    return () => {
      logger.componentUnmount('VisaOraclePage');
    };
  }, []);

  const loadItems = async () => {
    logger.info('Loading visa items', {
      component: 'VisaOraclePage',
      action: 'load_items',
    });
    setLoading(true);
    try {
      const res = await intelligenceApi.getPendingItems('visa');
      setItems(res.items);
      logger.info(`Loaded ${res.count} visa items`, {
        component: 'VisaOraclePage',
        action: 'load_items_success',
        metadata: { count: res.count },
      });
    } catch (error) {
      logger.error(
        'Failed to load visa items',
        { component: 'VisaOraclePage', action: 'load_items_error' },
        error as Error
      );
      toast.error('Failed to load items', 'Could not fetch pending visa updates.');
    } finally {
      setLoading(false);
    }
  };

  const handlePreview = async (id: string, type: 'visa' | 'news') => {
    if (previewId === id) {
      logger.userAction('close_preview', type, id, {
        component: 'VisaOraclePage',
      });
      setPreviewId(null);
      setPreviewContent('');
      return;
    }

    logger.userAction('open_preview', type, id, {
      component: 'VisaOraclePage',
    });

    try {
      const item = await intelligenceApi.getPreview(type, id);
      setPreviewId(id);
      setPreviewContent(item.content || 'No content available');
      logger.info(`Preview loaded for ${id}`, {
        component: 'VisaOraclePage',
        action: 'preview_success',
        itemType: type,
        itemId: id,
      });
    } catch (error) {
      logger.error(
        `Preview failed for ${id}`,
        {
          component: 'VisaOraclePage',
          action: 'preview_error',
          itemType: type,
          itemId: id,
        },
        error as Error
      );
      toast.error('Preview failed', 'Could not load content');
    }
  };

  const handleApprove = async (id: string) => {
    logger.userAction('approve_confirm_prompt', 'visa', id, {
      component: 'VisaOraclePage',
    });

    sonnerToast('Ingest into Knowledge Base?', {
      action: {
        label: 'Approve',
        onClick: () => void doApprove(id),
      },
      cancel: {
        label: 'Cancel',
        onClick: () =>
          logger.info('Approval cancelled by user', {
            component: 'VisaOraclePage',
            action: 'approve_cancelled',
            itemType: 'visa',
            itemId: id,
          }),
      },
    });
    return;
  };

  const doApprove = async (id: string) => {
    logger.info('Starting approval process', {
      component: 'VisaOraclePage',
      action: 'approve_start',
      itemType: 'visa',
      itemId: id,
    });

    setProcessing(id);
    try {
      await intelligenceApi.approveItem('visa', id);
      toast.success(
        'Visa approved',
        'Item has been ingested into visa_oracle collection successfully.'
      );
      setItems((prev) => prev.filter((i) => i.id !== id));
      if (previewId === id) {
        setPreviewId(null);
        setPreviewContent('');
      }
      logger.info('Approval completed successfully', {
        component: 'VisaOraclePage',
        action: 'approve_success',
        itemType: 'visa',
        itemId: id,
      });
    } catch (error) {
      logger.error(
        'Approval failed',
        {
          component: 'VisaOraclePage',
          action: 'approve_error',
          itemType: 'visa',
          itemId: id,
        },
        error as Error
      );
      toast.error('Approval failed', 'Could not ingest item. Check backend logs.');
    } finally {
      setProcessing(null);
    }
  };

  const toggleSelectItem = (id: string) => {
    setSelectedItems((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === filteredAndSortedItems.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(filteredAndSortedItems.map((item) => item.id)));
    }
  };

  const handleBulkApprove = () => {
    if (selectedItems.size === 0) {
      toast.error('No items selected', 'Please select items to approve.');
      return;
    }
    sonnerToast(
      `Approve ${selectedItems.size} item(s)? This will ingest them into the Knowledge Base.`,
      {
        action: { label: 'Approve', onClick: () => void doBulkApprove() },
        cancel: { label: 'Cancel', onClick: () => sonnerToast.dismiss() },
      }
    );
  };

  const doBulkApprove = async () => {
    logger.info('Starting bulk approval', {
      component: 'VisaOraclePage',
      action: 'bulk_approve_start',
      metadata: { count: selectedItems.size },
    });

    const ids = Array.from(selectedItems);
    const results = { success: 0, failed: 0 };

    for (const id of ids) {
      setProcessing(id);
      try {
        await intelligenceApi.approveItem('visa', id);
        results.success++;
        setItems((prev) => prev.filter((i) => i.id !== id));
      } catch (error) {
        results.failed++;
        logger.error(
          'Bulk approval failed for item',
          {
            component: 'VisaOraclePage',
            action: 'bulk_approve_error',
            itemId: id,
          },
          error as Error
        );
      } finally {
        setProcessing(null);
      }
    }

    setSelectedItems(new Set());
    toast.success(
      'Bulk approval completed',
      `${results.success} approved, ${results.failed} failed.`
    );

    logger.info('Bulk approval completed', {
      component: 'VisaOraclePage',
      action: 'bulk_approve_complete',
      metadata: results,
    });
  };

  const handleBulkReject = () => {
    if (selectedItems.size === 0) {
      toast.error('No items selected', 'Please select items to reject.');
      return;
    }
    sonnerToast(`Reject ${selectedItems.size} item(s)? They will be archived.`, {
      action: { label: 'Reject', onClick: () => void doBulkReject() },
      cancel: { label: 'Cancel', onClick: () => sonnerToast.dismiss() },
    });
  };

  const doBulkReject = async () => {
    logger.info('Starting bulk rejection', {
      component: 'VisaOraclePage',
      action: 'bulk_reject_start',
      metadata: { count: selectedItems.size },
    });

    const ids = Array.from(selectedItems);
    const results = { success: 0, failed: 0 };

    for (const id of ids) {
      setProcessing(id);
      try {
        await intelligenceApi.rejectItem('visa', id);
        results.success++;
        setItems((prev) => prev.filter((i) => i.id !== id));
      } catch (error) {
        results.failed++;
        logger.error(
          'Bulk rejection failed for item',
          {
            component: 'VisaOraclePage',
            action: 'bulk_reject_error',
            itemId: id,
          },
          error as Error
        );
      } finally {
        setProcessing(null);
      }
    }

    setSelectedItems(new Set());
    toast.success(
      'Bulk rejection completed',
      `${results.success} rejected, ${results.failed} failed.`
    );

    logger.info('Bulk rejection completed', {
      component: 'VisaOraclePage',
      action: 'bulk_reject_complete',
      metadata: results,
    });
  };

  const handleReject = async (id: string) => {
    logger.userAction('reject_confirm_prompt', 'visa', id, {
      component: 'VisaOraclePage',
    });

    sonnerToast('Reject this update? It will be archived.', {
      action: {
        label: 'Reject',
        onClick: () => void doReject(id),
      },
      cancel: {
        label: 'Cancel',
        onClick: () =>
          logger.info('Rejection cancelled by user', {
            component: 'VisaOraclePage',
            action: 'reject_cancelled',
            itemType: 'visa',
            itemId: id,
          }),
      },
    });
    return;
  };

  const doReject = async (id: string) => {
    logger.info('Starting rejection process', {
      component: 'VisaOraclePage',
      action: 'reject_start',
      itemType: 'visa',
      itemId: id,
    });

    setProcessing(id);
    try {
      await intelligenceApi.rejectItem('visa', id);
      toast.success('Update rejected', 'Item has been archived as rejected.');
      setItems((prev) => prev.filter((i) => i.id !== id));
      if (previewId === id) {
        setPreviewId(null);
        setPreviewContent('');
      }
      logger.info('Rejection completed successfully', {
        component: 'VisaOraclePage',
        action: 'reject_success',
        itemType: 'visa',
        itemId: id,
      });
    } catch (error) {
      logger.error(
        'Rejection failed',
        {
          component: 'VisaOraclePage',
          action: 'reject_error',
          itemType: 'visa',
          itemId: id,
        },
        error as Error
      );
      toast.error('Rejection failed', 'Could not archive item. Check backend logs.');
    } finally {
      setProcessing(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--bz-accent)' }} />
        <p className="text-[12px] animate-pulse" style={{ color: 'var(--bz-text-2)' }}>
          Scanning Intelligence Feed...
        </p>
      </div>
    );
  }

  if (items.length === 0 || filteredAndSortedItems.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center py-24 rounded-2xl border-2 border-dashed"
        style={{
          borderColor: 'rgba(255,255,255,0.07)',
          background: 'rgba(255,255,255,0.01)',
        }}
      >
        <div
          className="w-16 h-16 rounded-2xl flex items-center justify-center mb-5"
          style={{
            background: 'rgba(212,132,90,0.08)',
            border: '1px solid rgba(212,132,90,0.15)',
          }}
        >
          <Sparkles className="w-8 h-8" style={{ color: 'var(--bz-accent)' }} />
        </div>
        <h3 className="text-[15px] font-semibold mb-1" style={{ color: 'var(--bz-text-1)' }}>
          All Caught Up!
        </h3>
        <p className="text-[12px] text-center max-w-sm mb-6" style={{ color: 'var(--bz-text-2)' }}>
          {items.length === 0
            ? 'No pending visa updates. The agent is continuously monitoring imigrasi.go.id.'
            : 'No items match your current filters.'}
        </p>
        <button
          onClick={loadItems}
          className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[12px] font-medium transition-all hover:bg-white/[0.04]"
          style={{
            color: 'var(--bz-text-2)',
            border: '1px solid rgba(255,255,255,0.07)',
          }}
        >
          <RefreshCw className="w-3.5 h-3.5" /> Check Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Stats Bar */}
      <div
        className="flex items-center justify-between px-4 py-3 rounded-2xl border mb-2"
        style={{
          background: 'rgba(255,255,255,0.03)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderColor: 'rgba(255,255,255,0.07)',
        }}
      >
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" style={{ color: 'var(--bz-accent)' }} />
            <span className="text-[12px] font-medium" style={{ color: 'var(--bz-text-1)' }}>
              {filteredAndSortedItems.length} of {items.length} pending
            </span>
          </div>
          <div className="h-3 w-px" style={{ background: 'var(--bz-border)' }} />
          <span className="text-[11px]" style={{ color: 'var(--bz-text-2)' }}>
            {items.filter((i) => i.detection_type === 'NEW').length} new ·{' '}
            {items.filter((i) => i.detection_type === 'UPDATED').length} updated
          </span>
          {selectedItems.size > 0 && (
            <>
              <div className="h-3 w-px" style={{ background: 'var(--bz-border)' }} />
              <span className="text-[11px] font-semibold" style={{ color: 'var(--bz-accent)' }}>
                {selectedItems.size} selected
              </span>
            </>
          )}
        </div>
        <button
          onClick={loadItems}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all hover:bg-white/[0.04]"
          style={{
            color: 'var(--bz-text-2)',
            border: '1px solid rgba(255,255,255,0.07)',
          }}
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Filter Bar */}
      <div
        className="flex flex-col sm:flex-row gap-3 px-4 py-3 rounded-2xl border mb-6"
        style={{
          background: 'rgba(255,255,255,0.03)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          borderColor: 'rgba(255,255,255,0.07)',
        }}
      >
        {/* Search input */}
        <div className="flex-1 relative">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
            style={{ color: 'var(--bz-text-3)' }}
          />
          <input
            placeholder="Search by title, ID, or source..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded-xl text-[12px] outline-none transition-all"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.07)',
              color: 'var(--bz-text-1)',
            }}
          />
        </div>

        {/* Type filter */}
        <Select value={filterType} onValueChange={(v) => setFilterType(v as FilterType)}>
          <SelectTrigger
            className="w-[130px] h-8 text-[11px] rounded-xl"
            style={{
              background: 'rgba(255,255,255,0.04)',
              borderColor: 'rgba(255,255,255,0.07)',
              color: 'var(--bz-text-2)',
            }}
          >
            <Filter className="w-3 h-3 mr-1.5" style={{ color: 'var(--bz-text-3)' }} />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Types</SelectItem>
            <SelectItem value="NEW">New Only</SelectItem>
            <SelectItem value="UPDATED">Updated Only</SelectItem>
          </SelectContent>
        </Select>

        {/* Sort select */}
        <Select value={sortType} onValueChange={(v) => setSortType(v as SortType)}>
          <SelectTrigger
            className="w-[140px] h-8 text-[11px] rounded-xl"
            style={{
              background: 'rgba(255,255,255,0.04)',
              borderColor: 'rgba(255,255,255,0.07)',
              color: 'var(--bz-text-2)',
            }}
          >
            <ArrowUpDown className="w-3 h-3 mr-1.5" style={{ color: 'var(--bz-text-3)' }} />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="date-desc">Newest First</SelectItem>
            <SelectItem value="date-asc">Oldest First</SelectItem>
            <SelectItem value="title-asc">Title A-Z</SelectItem>
            <SelectItem value="title-desc">Title Z-A</SelectItem>
          </SelectContent>
        </Select>

        {/* Bulk actions inline */}
        {selectedItems.size > 0 && (
          <div className="flex gap-2 ml-auto">
            <button
              onClick={toggleSelectAll}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-medium transition-all hover:bg-white/[0.04]"
              style={{
                color: 'var(--bz-text-2)',
                border: '1px solid rgba(255,255,255,0.07)',
              }}
            >
              {selectedItems.size === filteredAndSortedItems.length ? (
                <>
                  <CheckSquare className="w-3.5 h-3.5" /> Deselect All
                </>
              ) : (
                <>
                  <Square className="w-3.5 h-3.5" /> Select All
                </>
              )}
            </button>
            <button
              onClick={handleBulkApprove}
              disabled={!!processing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold transition-all"
              style={{
                background: 'rgba(77,184,122,0.12)',
                color: 'var(--bz-green)',
                border: '1px solid rgba(77,184,122,0.2)',
              }}
            >
              <Check className="w-3.5 h-3.5" /> Approve ({selectedItems.size})
            </button>
            <button
              onClick={handleBulkReject}
              disabled={!!processing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[11px] font-semibold transition-all"
              style={{
                background: 'rgba(239,68,68,0.08)',
                color: 'rgba(239,68,68,0.8)',
                border: '1px solid rgba(239,68,68,0.2)',
              }}
            >
              <X className="w-3.5 h-3.5" /> Reject ({selectedItems.size})
            </button>
          </div>
        )}
      </div>

      {/* Items Grid */}
      <div className="grid gap-4">
        {filteredAndSortedItems.map((item) => (
          <div
            key={item.id}
            className="rounded-2xl border overflow-hidden transition-all duration-200 hover:shadow-lg"
            style={{
              background: 'rgba(255,255,255,0.03)',
              backdropFilter: 'blur(12px)',
              WebkitBackdropFilter: 'blur(12px)',
              borderColor: 'rgba(255,255,255,0.07)',
              borderLeft: `3px solid ${item.detection_type === 'NEW' ? 'rgba(212,132,90,0.8)' : 'rgba(251,191,36,0.7)'}`,
            }}
          >
            {/* Card header */}
            <div className="px-4 py-4" style={{ background: 'rgba(255,255,255,0.02)' }}>
              <div className="flex items-start gap-3">
                <button
                  onClick={() => toggleSelectItem(item.id)}
                  className="mt-0.5 p-1 rounded-lg transition-colors hover:bg-white/[0.04]"
                  aria-label={`Select ${item.title}`}
                >
                  {selectedItems.has(item.id) ? (
                    <CheckSquare className="w-4 h-4" style={{ color: 'var(--bz-accent)' }} />
                  ) : (
                    <Square className="w-4 h-4" style={{ color: 'var(--bz-text-3)' }} />
                  )}
                </button>
                <div className="flex-1 space-y-1.5">
                  <span
                    className="inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold"
                    style={
                      item.detection_type === 'NEW'
                        ? {
                            background: 'rgba(212,132,90,0.12)',
                            color: 'var(--bz-accent)',
                            border: '1px solid rgba(212,132,90,0.2)',
                          }
                        : {
                            background: 'rgba(251,191,36,0.12)',
                            color: 'rgba(251,191,36,0.9)',
                            border: '1px solid rgba(251,191,36,0.2)',
                          }
                    }
                  >
                    {item.detection_type === 'NEW'
                      ? '\u2726 NEW REGULATION'
                      : '\u21BA UPDATED POLICY'}
                  </span>
                  <h3
                    className="text-[13.5px] font-semibold leading-snug"
                    style={{ color: 'var(--bz-text-1)' }}
                  >
                    {item.title}
                  </h3>
                  <div
                    className="flex items-center gap-3 text-[10.5px]"
                    style={{ color: 'var(--bz-text-2)' }}
                  >
                    <span className="font-mono">#{item.id.slice(0, 8)}</span>
                    <div className="w-px h-3" style={{ background: 'var(--bz-border)' }} />
                    <span>
                      {new Date(item.detected_at).toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                    </span>
                  </div>
                </div>
                <a
                  href={item.source}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10.5px] font-medium transition-all hover:bg-white/[0.04]"
                  style={{
                    color: 'var(--bz-text-2)',
                    border: '1px solid rgba(255,255,255,0.07)',
                  }}
                >
                  Source <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>

            {/* Preview section (when open) */}
            {previewId === item.id && (
              <div className="px-4 pb-3">
                <div
                  className="rounded-xl p-3"
                  style={{
                    background: 'rgba(255,255,255,0.02)',
                    border: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className="text-[11px] font-semibold"
                      style={{ color: 'var(--bz-text-2)' }}
                    >
                      Content Preview
                    </span>
                    <button
                      onClick={() => {
                        setPreviewId(null);
                        setPreviewContent('');
                      }}
                    >
                      <X className="w-3.5 h-3.5" style={{ color: 'var(--bz-text-3)' }} />
                    </button>
                  </div>
                  <pre
                    className="text-[10.5px] whitespace-pre-wrap font-mono max-h-48 overflow-auto"
                    style={{ color: 'var(--bz-text-2)' }}
                  >
                    {previewContent}
                  </pre>
                </div>
              </div>
            )}

            {/* Card footer */}
            <div
              className="flex items-center gap-2 px-4 py-3"
              style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
            >
              <button
                onClick={() => handlePreview(item.id, item.type)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] transition-all hover:bg-white/[0.04]"
                style={{ color: 'var(--bz-text-2)' }}
              >
                <Eye className="w-3.5 h-3.5" />
                {previewId === item.id ? 'Hide' : 'Preview'}
              </button>
              <div className="flex-1" />
              <button
                onClick={() => handleReject(item.id)}
                disabled={!!processing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all"
                style={{
                  color: 'rgba(239,68,68,0.8)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  background: 'rgba(239,68,68,0.05)',
                }}
              >
                <X className="w-3.5 h-3.5" /> Reject
              </button>
              <button
                onClick={() => handleApprove(item.id)}
                disabled={!!processing}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all"
                style={{
                  background: 'rgba(77,184,122,0.15)',
                  color: 'var(--bz-green)',
                  border: '1px solid rgba(77,184,122,0.25)',
                }}
              >
                {processing === item.id ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Ingesting...
                  </>
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" /> Approve & Ingest
                  </>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
