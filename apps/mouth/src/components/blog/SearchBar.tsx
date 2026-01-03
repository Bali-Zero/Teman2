'use client';

import * as React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, X, SlidersHorizontal, Calendar, Clock, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CategoryNav } from './CategoryNav';
import type { SearchBarProps, ArticleCategory } from '@/lib/blog/types';

export function SearchBar({
  placeholder = 'Search articles...',
  defaultValue = '',
  onSearch,
  showFilters = false,
  className,
}: SearchBarProps) {
  const [query, setQuery] = React.useState(defaultValue);
  const [isFiltersOpen, setIsFiltersOpen] = React.useState(false);
  const [selectedCategory, setSelectedCategory] = React.useState<ArticleCategory | undefined>();
  const [sortBy, setSortBy] = React.useState<'relevance' | 'date' | 'views'>('relevance');
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Debounced search
  React.useEffect(() => {
    const timer = setTimeout(() => {
      onSearch?.(query);
    }, 300);

    return () => clearTimeout(timer);
  }, [query, onSearch]);

  // Keyboard shortcut to focus search
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
      if (e.key === 'Escape') {
        inputRef.current?.blur();
        setIsFiltersOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch?.(query);
  };

  const clearSearch = () => {
    setQuery('');
    onSearch?.('');
    inputRef.current?.focus();
  };

  return (
    <div className={cn('relative', className)}>
      {/* Search form */}
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative flex items-center">
          {/* Search icon */}
          <Search className="absolute left-4 w-5 h-5 text-white/40 pointer-events-none" />

          {/* Input */}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className={cn(
              'w-full h-12 pl-12 pr-24 rounded-xl',
              'bg-white/5 border border-white/10',
              'text-white placeholder-white/40',
              'focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50',
              'transition-all duration-200'
            )}
          />

          {/* Right side buttons */}
          <div className="absolute right-2 flex items-center gap-1">
            {/* Clear button */}
            {query && (
              <button
                type="button"
                onClick={clearSearch}
                className="p-2 rounded-lg text-white/40 hover:text-white hover:bg-white/10 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            {/* Filters button */}
            {showFilters && (
              <button
                type="button"
                onClick={() => setIsFiltersOpen(!isFiltersOpen)}
                className={cn(
                  'p-2 rounded-lg transition-colors',
                  isFiltersOpen
                    ? 'bg-violet-500/20 text-violet-400'
                    : 'text-white/40 hover:text-white hover:bg-white/10'
                )}
              >
                <SlidersHorizontal className="w-4 h-4" />
              </button>
            )}

            {/* Keyboard shortcut hint */}
            <div className="hidden md:flex items-center gap-1 px-2 py-1 rounded-md bg-white/5 text-white/30 text-xs">
              <kbd className="font-mono">⌘</kbd>
              <kbd className="font-mono">K</kbd>
            </div>
          </div>
        </div>
      </form>

      {/* Filters panel */}
      <AnimatePresence>
        {showFilters && isFiltersOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -10, height: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-4 p-4 rounded-xl bg-white/5 border border-white/10 overflow-hidden"
          >
            {/* Category filter */}
            <div className="mb-4">
              <label className="block text-xs font-medium text-white/60 uppercase tracking-wider mb-2">
                Category
              </label>
              <CategoryNav
                activeCategory={selectedCategory}
                onCategoryChange={setSelectedCategory}
              />
            </div>

            {/* Sort options */}
            <div>
              <label className="block text-xs font-medium text-white/60 uppercase tracking-wider mb-2">
                Sort by
              </label>
              <div className="flex gap-2">
                <SortButton
                  active={sortBy === 'relevance'}
                  onClick={() => setSortBy('relevance')}
                  icon={Search}
                  label="Relevance"
                />
                <SortButton
                  active={sortBy === 'date'}
                  onClick={() => setSortBy('date')}
                  icon={Calendar}
                  label="Latest"
                />
                <SortButton
                  active={sortBy === 'views'}
                  onClick={() => setSortBy('views')}
                  icon={TrendingUp}
                  label="Popular"
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Sort button component
function SortButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ElementType;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
        active
          ? 'bg-violet-500/20 text-violet-400'
          : 'text-white/50 hover:text-white hover:bg-white/10'
      )}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}

// Compact search for header
export function SearchTrigger({
  onClick,
  className,
}: {
  onClick?: () => void;
  className?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-2 px-3 py-2 rounded-lg',
        'bg-white/5 border border-white/10',
        'text-white/50 hover:text-white hover:bg-white/10',
        'transition-colors',
        className
      )}
    >
      <Search className="w-4 h-4" />
      <span className="hidden md:inline text-sm">Search...</span>
      <div className="hidden md:flex items-center gap-1 ml-2 px-1.5 py-0.5 rounded bg-white/5 text-xs">
        <kbd className="font-mono">⌘</kbd>
        <kbd className="font-mono">K</kbd>
      </div>
    </button>
  );
}

// Article result type for search
interface SearchResult {
  id: string;
  slug: string;
  title: string;
  excerpt: string;
  coverImage: string;
  category: string;
  readingTime: number;
  publishedAt: string;
}

// Full search modal
export function SearchModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = React.useState('');
  const [results, setResults] = React.useState<SearchResult[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  // Focus input when modal opens
  React.useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Debounced search
  React.useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`/api/blog/articles?q=${encodeURIComponent(query)}&limit=10`);
        const data = await res.json();
        setResults(data.articles || []);
        setSelectedIndex(0);
      } catch (err) {
        console.error('Search failed:', err);
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  // Keyboard navigation
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && results[selectedIndex]) {
        e.preventDefault();
        const article = results[selectedIndex];
        window.location.href = `/${article.category}/${article.slug}`;
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose, results, selectedIndex]);

  // Category click handler
  const handleCategoryClick = (category: string) => {
    setQuery(category);
  };

  // Recent search click handler
  const handleRecentClick = (term: string) => {
    setQuery(term);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative max-w-2xl mx-auto mt-20 md:mt-32 animate-in fade-in slide-in-from-top-4 duration-300">
        <div className="mx-4 bg-zinc-900 border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
          {/* Search input */}
          <div className="relative flex items-center border-b border-white/10">
            <Search className="absolute left-4 w-5 h-5 text-white/40" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search articles, topics, authors..."
              className="w-full h-14 pl-12 pr-20 bg-transparent text-white placeholder-white/40 focus:outline-none"
            />
            <button
              onClick={onClose}
              className="absolute right-4 px-2 py-1 rounded bg-white/10 text-white/60 text-xs hover:bg-white/20 transition-colors"
            >
              ESC
            </button>
          </div>

          {/* Quick filters */}
          <div className="p-4 border-b border-white/10">
            <div className="flex gap-2 overflow-x-auto scrollbar-hide">
              <QuickFilter label="Immigration" onClick={() => handleCategoryClick('immigration')} />
              <QuickFilter label="Business" onClick={() => handleCategoryClick('business')} />
              <QuickFilter label="Tax" onClick={() => handleCategoryClick('tax')} />
              <QuickFilter label="Property" onClick={() => handleCategoryClick('property')} />
              <QuickFilter label="Lifestyle" onClick={() => handleCategoryClick('lifestyle')} />
            </div>
          </div>

          {/* Results */}
          <div className="max-h-[400px] overflow-y-auto">
            {isLoading ? (
              <div className="p-8 text-center">
                <div className="inline-block w-6 h-6 border-2 border-white/20 border-t-white/60 rounded-full animate-spin" />
                <p className="text-white/40 mt-2">Searching...</p>
              </div>
            ) : results.length > 0 ? (
              <div className="py-2">
                {results.map((article, index) => (
                  <a
                    key={article.id}
                    href={`/${article.category}/${article.slug}`}
                    onClick={onClose}
                    className={cn(
                      'flex items-start gap-4 px-4 py-3 hover:bg-white/5 transition-colors',
                      index === selectedIndex && 'bg-white/10'
                    )}
                  >
                    {/* Thumbnail */}
                    <div className="w-16 h-12 rounded-lg bg-white/10 overflow-hidden flex-shrink-0">
                      {article.coverImage && (
                        <img
                          src={article.coverImage}
                          alt=""
                          className="w-full h-full object-cover"
                        />
                      )}
                    </div>
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <p className="text-white font-medium truncate">{article.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-violet-500/20 text-violet-400 capitalize">
                          {article.category}
                        </span>
                        <span className="text-xs text-white/40">{article.readingTime} min read</span>
                      </div>
                    </div>
                    {/* Arrow indicator for selected */}
                    {index === selectedIndex && (
                      <div className="text-white/40 self-center">
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    )}
                  </a>
                ))}
              </div>
            ) : query ? (
              <div className="p-8 text-center">
                <p className="text-white/40">No results found for &ldquo;{query}&rdquo;</p>
                <p className="text-white/30 text-sm mt-1">Try different keywords</p>
              </div>
            ) : (
              <div className="p-6 text-center">
                <p className="text-white/40 text-sm mb-4">Popular searches</p>
                <div className="flex flex-wrap justify-center gap-2">
                  <RecentSearch label="KITAS application" onClick={() => handleRecentClick('KITAS')} />
                  <RecentSearch label="PT PMA setup" onClick={() => handleRecentClick('PT PMA')} />
                  <RecentSearch label="Tax obligations" onClick={() => handleRecentClick('tax')} />
                  <RecentSearch label="Golden Visa" onClick={() => handleRecentClick('golden visa')} />
                </div>
              </div>
            )}
          </div>

          {/* Footer hint */}
          <div className="px-4 py-3 border-t border-white/10 flex items-center justify-between text-xs text-white/30">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">↑</kbd>
                <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">↓</kbd>
                to navigate
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">↵</kbd>
                to select
              </span>
            </div>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 rounded bg-white/10 font-mono">esc</kbd>
              to close
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Quick filter chip
function QuickFilter({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="px-3 py-1.5 rounded-full bg-white/5 text-white/60 text-sm whitespace-nowrap hover:bg-white/10 hover:text-white transition-colors"
    >
      {label}
    </button>
  );
}

// Recent search item
function RecentSearch({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 text-white/60 text-sm hover:bg-white/10 hover:text-white transition-colors"
    >
      <Clock className="w-3 h-3" />
      {label}
    </button>
  );
}

export { SortButton, QuickFilter, RecentSearch };
