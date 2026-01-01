'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Clock,
  DollarSign,
  FileCheck,
  Star,
  TrendingUp,
  Shield,
  ChevronRight,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Timer,
  Wallet,
  Download,
  Share2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { VisaType, VisaTypeListResponse } from '@/lib/api/knowledge/visa.types';

// =============================================================================
// Helper Functions
// =============================================================================

function getDifficultyColor(difficulty: string | undefined): string {
  switch (difficulty) {
    case 'very_low':
      return 'text-emerald-400 bg-emerald-400/10';
    case 'low':
      return 'text-green-400 bg-green-400/10';
    case 'medium':
      return 'text-yellow-400 bg-yellow-400/10';
    case 'high':
      return 'text-orange-400 bg-orange-400/10';
    case 'very_high':
      return 'text-red-400 bg-red-400/10';
    default:
      return 'text-gray-400 bg-gray-400/10';
  }
}

function getDifficultyLabel(difficulty: string | undefined): string {
  switch (difficulty) {
    case 'very_low':
      return 'Very Easy';
    case 'low':
      return 'Easy';
    case 'medium':
      return 'Medium';
    case 'high':
      return 'Difficult';
    case 'very_high':
      return 'Very Difficult';
    default:
      return 'Unknown';
  }
}

function getCategoryColor(category: string): string {
  // KITAS/KITAP = Intense Orange, Visa types = Intense Blue
  switch (category) {
    case 'KITAS':
      return 'from-orange-400/50 to-amber-400/50 border-orange-500/60';
    case 'KITAP':
      return 'from-orange-500/50 to-amber-500/50 border-orange-600/60';
    case 'Visa Free':
      return 'from-sky-400/50 to-blue-400/50 border-sky-500/60';
    case 'VOA':
      return 'from-sky-400/50 to-cyan-400/50 border-sky-500/60';
    case 'Visit':
      return 'from-blue-400/50 to-sky-400/50 border-blue-500/60';
    default:
      return 'from-sky-400/50 to-blue-400/50 border-sky-500/60';
  }
}

function getCategoryBadgeColor(category: string): string {
  // KITAS/KITAP = Intense Orange badges, Visa types = Intense Blue badges
  switch (category) {
    case 'KITAS':
      return 'bg-orange-500/30 text-orange-600 dark:text-orange-300 border-orange-500/50';
    case 'KITAP':
      return 'bg-amber-500/30 text-amber-600 dark:text-amber-300 border-amber-500/50';
    case 'Visa Free':
      return 'bg-sky-500/30 text-sky-600 dark:text-sky-300 border-sky-500/50';
    case 'VOA':
      return 'bg-cyan-500/30 text-cyan-600 dark:text-cyan-300 border-cyan-500/50';
    case 'Visit':
      return 'bg-blue-500/30 text-blue-600 dark:text-blue-300 border-blue-500/50';
    default:
      return 'bg-sky-500/30 text-sky-600 dark:text-sky-300 border-sky-500/50';
  }
}

// Get series letter from visa code (e.g., "E33G" -> "E", "A1" -> "A")
function getSeriesFromCode(code: string): string {
  const match = code.match(/^([A-Z]+)/);
  return match ? match[1] : 'Z';
}

// Sort order for series
const SERIES_ORDER: Record<string, number> = {
  'A': 1,
  'B': 2,
  'C': 3,
  'D': 4,
  'E': 5,
  'KITAP': 6,
};

function getSeriesOrder(code: string): number {
  if (code === 'KITAP') return 6;
  const series = getSeriesFromCode(code);
  return SERIES_ORDER[series] || 99;
}

// Get series display name
function getSeriesDisplayName(series: string): string {
  switch (series) {
    case 'A': return 'Series A - Visa Free';
    case 'B': return 'Series B - Visa on Arrival';
    case 'C': return 'Series C - Single Entry Visit';
    case 'D': return 'Series D - Multiple Entry Visit';
    case 'E': return 'Series E - KITAS (Temporary Stay)';
    case 'KITAP': return 'KITAP - Permanent Stay';
    default: return `Series ${series}`;
  }
}

// =============================================================================
// Visa Card Component
// =============================================================================

interface VisaCardProps {
  visa: VisaType;
  onClick: () => void;
  onDownloadPdf?: () => void;
}

function VisaCard({ visa, onClick, onDownloadPdf }: VisaCardProps) {
  const isRecommended = visa.metadata?.bali_zero_recommended;
  const isNew = visa.metadata?.new_visa;
  const difficulty = visa.metadata?.difficulty;
  const pdfUrl = visa.metadata?.pdf_url;

  const handlePdfDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (pdfUrl) {
      window.open(pdfUrl, '_blank');
    } else if (onDownloadPdf) {
      onDownloadPdf();
    }
  };

  return (
    <div
      onClick={onClick}
      className={`
        group relative overflow-hidden rounded-2xl border cursor-pointer
        bg-gradient-to-br ${getCategoryColor(visa.category)}
        hover:scale-[1.02] hover:shadow-xl hover:shadow-[var(--accent)]/10
        transition-all duration-300 ease-out
      `}
    >
      {/* Recommended Badge */}
      {isRecommended && (
        <div className="absolute top-4 right-4 z-10">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-semibold shadow-lg">
            <Star className="w-3.5 h-3.5 fill-current" />
            Recommended
          </div>
        </div>
      )}

      {/* New Badge */}
      {isNew && !isRecommended && (
        <div className="absolute top-4 right-4 z-10">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-semibold shadow-lg">
            <Sparkles className="w-3.5 h-3.5" />
            New
          </div>
        </div>
      )}

      {/* Card Content */}
      <div className="p-6">
        {/* BIG VISA CODE - Prominent Display */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-3xl font-black text-[var(--foreground)] tracking-tight">
            {visa.code}
          </span>
          <span className={`px-2.5 py-1 text-xs font-medium rounded-full border ${getCategoryBadgeColor(visa.category)}`}>
            {visa.category}
          </span>
        </div>

        {/* Title */}
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-1 group-hover:text-[var(--accent)] transition-colors leading-tight">
            {visa.name}
          </h3>
          {difficulty && (
            <span className={`inline-block mt-1 px-2 py-0.5 text-xs font-medium rounded-full ${getDifficultyColor(difficulty)}`}>
              {getDifficultyLabel(difficulty)}
            </span>
          )}
        </div>

        {/* Key Info Grid */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          {/* Duration */}
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[var(--background)]/50">
            <div className="w-9 h-9 rounded-lg bg-[var(--accent)]/10 flex items-center justify-center">
              <Clock className="w-4.5 h-4.5 text-[var(--accent)]" />
            </div>
            <div>
              <p className="text-xs text-[var(--foreground-muted)]">Duration</p>
              <p className="text-sm font-semibold text-[var(--foreground)]">{visa.duration || 'Varies'}</p>
            </div>
          </div>

          {/* Cost */}
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[var(--background)]/50">
            <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Wallet className="w-4.5 h-4.5 text-emerald-400" />
            </div>
            <div>
              <p className="text-xs text-[var(--foreground-muted)]">From</p>
              <p className="text-sm font-semibold text-[var(--foreground)]">{visa.cost_visa || 'Contact us'}</p>
            </div>
          </div>

          {/* Processing Time */}
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[var(--background)]/50">
            <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Timer className="w-4.5 h-4.5 text-blue-400" />
            </div>
            <div>
              <p className="text-xs text-[var(--foreground-muted)]">Processing</p>
              <p className="text-sm font-semibold text-[var(--foreground)]">{visa.processing_time_normal || 'Varies'}</p>
            </div>
          </div>

          {/* Total Stay */}
          <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[var(--background)]/50">
            <div className="w-9 h-9 rounded-lg bg-purple-500/10 flex items-center justify-center">
              <Shield className="w-4.5 h-4.5 text-purple-400" />
            </div>
            <div>
              <p className="text-xs text-[var(--foreground-muted)]">Max Stay</p>
              <p className="text-sm font-semibold text-[var(--foreground)]">{visa.total_stay || 'Varies'}</p>
            </div>
          </div>
        </div>

        {/* Quick Benefits */}
        <div className="space-y-2 mb-5">
          {visa.benefits.slice(0, 3).map((benefit, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
              <span className="text-sm text-[var(--foreground-secondary)] line-clamp-1">{benefit}</span>
            </div>
          ))}
        </div>

        {/* CTA with PDF Download */}
        <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-sm text-[var(--foreground-muted)]">
              <FileCheck className="w-4 h-4" />
              <span>{visa.requirements.length} req</span>
            </div>
            {/* PDF Download Button */}
            <button
              onClick={handlePdfDownload}
              className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[var(--background)]/60 hover:bg-[var(--accent)]/20 text-[var(--foreground-muted)] hover:text-[var(--accent)] transition-colors text-xs"
              title="Download PDF Info Sheet"
            >
              <Download className="w-3.5 h-3.5" />
              <span>PDF</span>
            </button>
          </div>
          <div className="flex items-center gap-1 text-[var(--accent)] font-medium text-sm group-hover:gap-2 transition-all">
            <span>Details</span>
            <ChevronRight className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Hover Gradient Effect */}
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--accent)]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
    </div>
  );
}

// =============================================================================
// Category Filter Component
// =============================================================================

interface CategoryFilterProps {
  categories: string[];
  selected: string | null;
  onSelect: (category: string | null) => void;
  counts: Record<string, number>;
}

function CategoryFilter({ categories, selected, onSelect, counts }: CategoryFilterProps) {
  // Order: Visa types first (blue), then KITAS/KITAP (orange)
  const orderedCategories = ['Visa Free', 'VOA', 'Visit', 'KITAS', 'KITAP'];
  const sortedCategories = orderedCategories.filter(c => categories.includes(c));

  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onSelect(null)}
        className={`
          px-4 py-2 rounded-full text-sm font-medium transition-all
          ${selected === null
            ? 'bg-[var(--accent)] text-white'
            : 'bg-[var(--background-secondary)] text-[var(--foreground-secondary)] hover:bg-[var(--background-elevated)]'
          }
        `}
      >
        All ({Object.values(counts).reduce((a, b) => a + b, 0)})
      </button>
      {sortedCategories.map((category) => (
        <button
          key={category}
          onClick={() => onSelect(category)}
          className={`
            px-4 py-2 rounded-full text-sm font-medium transition-all
            ${selected === category
              ? 'bg-[var(--accent)] text-white'
              : 'bg-[var(--background-secondary)] text-[var(--foreground-secondary)] hover:bg-[var(--background-elevated)]'
            }
          `}
        >
          {category} ({counts[category] || 0})
        </button>
      ))}
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function KitasVisaPage() {
  const router = useRouter();
  const [visas, setVisas] = useState<VisaType[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadVisas();
  }, []);

  const loadVisas = async () => {
    try {
      setIsLoading(true);
      const response = await api.get<VisaTypeListResponse>('/api/knowledge/visa/');
      setVisas(response.items);
      setCategories(response.categories);
      setError(null);
    } catch (err) {
      console.error('Failed to load visas:', err);
      setError('Failed to load visa information. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Filter by category if selected
  const filteredVisas = selectedCategory
    ? visas.filter((v) => v.category === selectedCategory)
    : visas;

  // Sort visas by series (A → B → C → D → E → KITAP)
  const sortedVisas = [...filteredVisas].sort((a, b) => {
    const orderA = getSeriesOrder(a.code);
    const orderB = getSeriesOrder(b.code);
    if (orderA !== orderB) return orderA - orderB;
    // Within same series, sort by code
    return a.code.localeCompare(b.code);
  });

  // Group visas by series for section headers
  const visasBySeries = sortedVisas.reduce((acc, visa) => {
    const series = visa.code === 'KITAP' ? 'KITAP' : getSeriesFromCode(visa.code);
    if (!acc[series]) acc[series] = [];
    acc[series].push(visa);
    return acc;
  }, {} as Record<string, VisaType[]>);

  // Get ordered series keys
  const orderedSeries = Object.keys(visasBySeries).sort((a, b) => {
    return (SERIES_ORDER[a] || 99) - (SERIES_ORDER[b] || 99);
  });

  const categoryCounts = visas.reduce((acc, visa) => {
    acc[visa.category] = (acc[visa.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const handleVisaClick = (visa: VisaType) => {
    router.push(`/knowledge/kitas/${visa.id}`);
  };

  const handleDownloadPdf = (visa: VisaType) => {
    // Generate PDF or show info - for now, navigate to detail page
    router.push(`/knowledge/kitas/${visa.id}?download=pdf`);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.push('/knowledge')}
            className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] mb-4 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Knowledge Base
          </button>
          <h1 className="text-3xl font-bold text-[var(--foreground)]">KITAS & Visa Guide</h1>
          <p className="text-[var(--foreground-muted)] mt-2 max-w-2xl">
            Complete guide to Indonesian visas and permits. Professional service by Bali Zero -
            your trusted immigration partner since 2015.
          </p>
        </div>

        {/* Bali Zero Branding */}
        <div className="hidden lg:flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
          <div className="w-10 h-10 rounded-lg bg-[var(--accent)] flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">Bali Zero</p>
            <p className="text-xs text-[var(--foreground-muted)]">Trusted Immigration Partner</p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <FileCheck className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">{visas.length}</p>
              <p className="text-xs text-[var(--foreground-muted)]">Visa Types</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">98%</p>
              <p className="text-xs text-[var(--foreground-muted)]">Success Rate</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <Star className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">10+</p>
              <p className="text-xs text-[var(--foreground-muted)]">Years Experience</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <Clock className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">24/7</p>
              <p className="text-xs text-[var(--foreground-muted)]">Support</p>
            </div>
          </div>
        </div>
      </div>

      {/* Category Filter */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <CategoryFilter
          categories={categories}
          selected={selectedCategory}
          onSelect={setSelectedCategory}
          counts={categoryCounts}
        />
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-80 rounded-2xl bg-[var(--background-secondary)] animate-pulse" />
          ))}
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="p-6 rounded-xl bg-red-500/10 border border-red-500/30 text-center">
          <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-red-400 font-medium">{error}</p>
          <Button onClick={loadVisas} className="mt-4">
            Try Again
          </Button>
        </div>
      )}

      {/* Visa Cards Grouped by Series */}
      {!isLoading && !error && orderedSeries.length > 0 && (
        <div className="space-y-10">
          {orderedSeries.map((series) => (
            <div key={series} className="space-y-4">
              {/* Series Header */}
              <div className="flex items-center gap-3">
                <div className={`
                  w-12 h-12 rounded-xl flex items-center justify-center font-black text-xl
                  ${series === 'E' || series === 'KITAP'
                    ? 'bg-orange-500/40 text-orange-500 dark:text-orange-400 border border-orange-500/50'
                    : 'bg-sky-500/40 text-sky-500 dark:text-sky-400 border border-sky-500/50'}
                `}>
                  {series}
                </div>
                <div>
                  <h2 className="text-xl font-bold text-[var(--foreground)]">
                    {getSeriesDisplayName(series)}
                  </h2>
                  <p className="text-sm text-[var(--foreground-muted)]">
                    {visasBySeries[series].length} visa type{visasBySeries[series].length > 1 ? 's' : ''}
                  </p>
                </div>
              </div>

              {/* Series Grid */}
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                {visasBySeries[series].map((visa) => (
                  <VisaCard
                    key={visa.id}
                    visa={visa}
                    onClick={() => handleVisaClick(visa)}
                    onDownloadPdf={() => handleDownloadPdf(visa)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && filteredVisas.length === 0 && (
        <div className="p-12 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)] text-center">
          <FileCheck className="w-16 h-16 text-[var(--foreground-muted)] mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">No visas found</h3>
          <p className="text-sm text-[var(--foreground-muted)]">
            {selectedCategory
              ? `No visa types in the ${selectedCategory} category.`
              : 'No visa types available. Check back later.'}
          </p>
        </div>
      )}

      {/* Contact CTA */}
      <div className="p-8 rounded-2xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)] mb-2">
              Need Help Choosing the Right Visa?
            </h3>
            <p className="text-[var(--foreground-secondary)]">
              Our immigration experts are here to guide you through the process.
              Free consultation available.
            </p>
          </div>
          <Button
            onClick={() => router.push('/chat')}
            className="gap-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white whitespace-nowrap"
          >
            <Sparkles className="w-4 h-4" />
            Ask Zantara AI
          </Button>
        </div>
      </div>
    </div>
  );
}
