'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { BookOpen, Search, Filter, Plus, FileText, FolderOpen, Tag } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { useEnhancedAnalytics } from '@/lib/enhanced-analytics';
import type { KnowledgeSearchResult } from '@/lib/api/knowledge/knowledge.types';

export default function KnowledgePage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const pageLoadStartTime = useRef<number>(performance.now());
  const { trackPageView, trackUserInteraction, trackPerformance, trackEvent } = useEnhancedAnalytics();

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      setHasSearched(false);
      logger.debug('Search cleared', { component: 'KnowledgePage', action: 'clearSearch' });
      return;
    }

    const searchStartTime = performance.now();
    setIsSearching(true);
    setHasSearched(true);
    
    logger.info('Knowledge search initiated', {
      component: 'KnowledgePage',
      action: 'search',
      metadata: { query: searchQuery, queryLength: searchQuery.length },
    });
    
    trackUserInteraction('search', 'knowledge_search', searchQuery);
    trackEvent('knowledge_search', 'knowledge', searchQuery);

    try {
      const response = await api.knowledge.searchDocs({
        query: searchQuery,
        limit: 20,
      });
      
      const searchDuration = performance.now() - searchStartTime;
      const resultCount = response.results?.length || 0;
      
      setSearchResults(response.results || []);
      
      logger.info('Knowledge search completed', {
        component: 'KnowledgePage',
        action: 'search_success',
        metadata: {
          query: searchQuery,
          resultCount,
          executionTime: response.execution_time_ms,
          searchDuration: Math.round(searchDuration),
        },
      });
      
      trackPerformance({ apiCallTime: searchDuration });
      trackEvent('knowledge_search_success', 'knowledge', searchQuery, resultCount);
    } catch (error) {
      const searchDuration = performance.now() - searchStartTime;
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      logger.error('Knowledge search failed', {
        component: 'KnowledgePage',
        action: 'search_error',
        metadata: { query: searchQuery, error: errorMessage },
      }, error instanceof Error ? error : new Error(errorMessage));
      
      trackEvent('knowledge_search_error', 'knowledge', searchQuery);
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      if (searchQuery.trim()) {
        handleSearch();
      } else {
        setSearchResults([]);
        setHasSearched(false);
      }
    }, 500);

    return () => clearTimeout(debounceTimer);
  }, [searchQuery]);

  // Track page load and performance
  useEffect(() => {
    const loadTime = performance.now() - pageLoadStartTime.current;
    
    logger.componentMount('KnowledgePage', {
      component: 'KnowledgePage',
      action: 'mount',
      metadata: { loadTime: Math.round(loadTime) },
    });
    
    trackPageView('/knowledge', 'Knowledge Base');
    trackPerformance({ loadTime });
    trackEvent('knowledge_page_view', 'navigation', 'knowledge_base');

    return () => {
      logger.componentUnmount('KnowledgePage', {
        component: 'KnowledgePage',
        action: 'unmount',
      });
    };
  }, []);

  const handleNewDocument = () => {
    logger.userAction('new_document_click', undefined, undefined, {
      component: 'KnowledgePage',
      action: 'new_document',
    });
    trackUserInteraction('click', 'new_document_button', 'knowledge_page');
    trackEvent('knowledge_new_document_click', 'knowledge', 'new_document');
    router.push('/knowledge/upload');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Knowledge Base</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Documents, procedures and company information
          </p>
        </div>
        <Button className="gap-2" onClick={handleNewDocument}>
          <Plus className="w-4 h-4" />
          New Document
        </Button>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--foreground-muted)]" />
        <input
          type="text"
          placeholder="Search knowledge base..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              handleSearch();
            }
          }}
          className="w-full pl-12 pr-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 text-lg"
        />
      </div>

      {/* Categories - 30% smaller */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { name: 'KITAS & Visa', icon: FileText, key: 'kitas', href: '/knowledge/kitas', hasPage: true },
          { name: 'Company & Licenses', icon: FolderOpen, key: 'pma', href: '/knowledge/company-licenses', hasPage: true },
          { name: 'Tax & NPWP', icon: FileText, key: 'tax', href: '/knowledge/tax', hasPage: true },
          { name: 'Our Journey', icon: Tag, key: 'journey', href: '/knowledge/our-journey', hasPage: true },
        ].map((category) => {
          const count = searchResults.filter((r) => {
            const collection = r.metadata?.collection?.toLowerCase() || '';
            if (category.key === 'kitas') return collection.includes('kitas') || collection.includes('visa');
            if (category.key === 'pma') return collection.includes('pma') || collection.includes('company');
            if (category.key === 'tax') return collection.includes('tax') || collection.includes('npwp');
            if (category.key === 'journey') return false; // Our Journey is empty for now
            return false;
          }).length;

          return (
            <div
              key={category.name}
              onClick={() => {
                logger.userAction('category_click', undefined, undefined, {
                  component: 'KnowledgePage',
                  action: 'category_click',
                  metadata: { category: category.key, categoryName: category.name },
                });
                trackUserInteraction('click', `category_${category.key}`, category.name);
                trackEvent('knowledge_category_click', 'knowledge', category.key);
                
                if (category.hasPage && category.href) {
                  router.push(category.href);
                } else {
                  const searchTerm = category.key === 'kitas' ? 'KITAS visa' : category.key === 'pma' ? 'PT PMA company' : category.key === 'tax' ? 'tax NPWP' : 'procedure process';
                  setSearchQuery(searchTerm);
                  handleSearch();
                }
              }}
              className={`p-3 rounded-lg border cursor-pointer transition-all ${
                category.hasPage
                  ? 'border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/5 to-purple-500/5 hover:border-[var(--accent)]/50 hover:shadow-lg hover:shadow-[var(--accent)]/10'
                  : 'border-[var(--border)] bg-[var(--background-secondary)] hover:bg-[var(--background-elevated)]/50'
              }`}
            >
              <category.icon className={`w-6 h-6 mb-2 ${category.hasPage ? 'text-[var(--accent)]' : 'text-[var(--foreground-muted)]'}`} />
              <h3 className="text-sm font-medium text-[var(--foreground)]">{category.name}</h3>
              <p className="text-[10px] text-[var(--foreground-muted)]">
                {category.hasPage
                  ? (category.key === 'kitas' ? 'View visa guides' : category.key === 'pma' ? 'Company & Licenses' : category.key === 'tax' ? 'NPWP, SPT, BPJS, LKPM' : category.key === 'journey' ? 'Coming soon' : '')
                  : ((category as any).subtitle || `${count} documents`)}
              </p>
            </div>
          );
        })}
      </div>

      {/* Search Results */}
      {hasSearched && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
          <div className="p-4 border-b border-[var(--border)]">
            <h2 className="font-semibold text-[var(--foreground)]">
              {isSearching ? 'Searching...' : `Search Results (${searchResults.length})`}
            </h2>
          </div>
          {isSearching ? (
            <div className="p-8 text-center">
              <div className="animate-pulse text-sm text-[var(--foreground-muted)]">Searching...</div>
            </div>
          ) : searchResults.length > 0 ? (
            <div className="divide-y divide-[var(--border)]">
              {searchResults.map((result, idx) => (
                <div
                  key={idx}
                  className="p-4 hover:bg-[var(--background-elevated)]/50 transition-colors cursor-pointer"
                  onClick={() => {
                    const docId = result.metadata?.document_id;
                    if (docId) {
                      logger.userAction('document_click', undefined, docId, {
                        component: 'KnowledgePage',
                        action: 'document_click',
                        metadata: {
                          documentId: docId,
                          title: result.metadata?.title,
                          collection: (result.metadata as any)?.collection,
                        },
                      });
                      trackUserInteraction('click', 'search_result', docId);
                      trackEvent('knowledge_document_view', 'knowledge', docId);
                      router.push(`/knowledge/${docId}`);
                    }
                  }}
                >
                  <h3 className="font-medium text-[var(--foreground)] mb-1">
                    {result.metadata?.title || result.metadata?.document_id || 'Untitled Document'}
                  </h3>
                  <p className="text-sm text-[var(--foreground-muted)] line-clamp-2">
                    {result.text || (result.metadata as any)?.summary || 'No preview available'}
                  </p>
                  {(result.metadata as any)?.collection && (
                    <span className="inline-block mt-2 text-xs text-[var(--accent)] bg-[var(--accent)]/10 px-2 py-1 rounded">
                      {(result.metadata as any)?.collection}
                    </span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center">
              <BookOpen className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">
                No documents found
              </p>
            </div>
          )}
        </div>
      )}

      {/* Recent Documents Placeholder */}
      {!hasSearched && (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
          <div className="p-4 border-b border-[var(--border)]">
            <h2 className="font-semibold text-[var(--foreground)]">Recent Documents</h2>
          </div>
          <div className="p-8 text-center">
            <BookOpen className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
            <p className="text-sm text-[var(--foreground-muted)]">
              No recent documents
            </p>
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          The Knowledge Base contains all company documents, operational procedures,
          templates and legal/tax information for Indonesia.
          Integrated with Zantara AI for semantic search.
        </p>
      </div>
    </div>
  );
}
