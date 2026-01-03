'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  FileText,
  Shield,
  TrendingUp,
  Star,
  Search,
  UtensilsCrossed,
  Wine,
  BadgeCheck,
  Cookie,
  Clock,
  DollarSign,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ChevronRight,
  Building2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// =============================================================================
// License Data
// =============================================================================

interface License {
  id: string;
  code: string;
  title: string;
  title_id: string;
  category: 'Food & Beverage' | 'Certification';
  price: string;
  price_note?: string;
  processing_time: string;
  validity: string;
  mandatory_for: string[];
  issuer: string;
  icon: 'utensils' | 'wine' | 'badge' | 'cookie';
  description: string;
  key_points: string[];
  warning?: string;
}

const LICENSES: License[] = [
  {
    id: 'slhs',
    code: 'SLHS',
    title: 'Hygiene Sanitation Certificate',
    title_id: 'Sertifikat Laik Higiene Sanitasi',
    category: 'Food & Beverage',
    price: 'IDR 9.000.000',
    processing_time: '3-4 weeks',
    validity: '3 years',
    mandatory_for: ['Restaurants', 'Cafes', 'Hotels with F&B', 'Catering', 'Food Production'],
    issuer: 'Dinas Kesehatan (Dinkes)',
    icon: 'utensils',
    description: 'Mandatory hygiene certificate for all food and beverage businesses in Indonesia. Required before opening.',
    key_points: [
      'Required for all F&B businesses',
      'Health inspection included',
      'Kitchen standards verification',
      'Renewable every 3 years',
    ],
    warning: 'Cannot operate legally without SLHS - risk of closure and fines!',
  },
  {
    id: 'npbbkc',
    code: 'NPBBKC',
    title: 'Alcohol License (A+B+C)',
    title_id: 'Nomor Pokok Pengusaha Barang Kena Cukai',
    category: 'Food & Beverage',
    price: 'IDR 15.000.000',
    processing_time: '45-60 days MINIMUM',
    validity: '5 years',
    mandatory_for: ['Bars', 'Beach Clubs', 'Restaurants serving alcohol', 'Hotels with bars'],
    issuer: 'Bea Cukai (Customs)',
    icon: 'wine',
    description: 'License to sell alcoholic beverages. Covers all categories: A (<5%), B (5-20%), C (>20% alcohol).',
    key_points: [
      'Golongan A: Beer, wine coolers',
      'Golongan B: Wine, sake',
      'Golongan C: Spirits, liquor',
      'Full coverage included',
    ],
    warning: 'Takes 45-60 days MINIMUM - major bottleneck! Start EARLY!',
  },
  {
    id: 'halal',
    code: 'HALAL',
    title: 'Halal Certificate',
    title_id: 'Sertifikat Halal',
    category: 'Certification',
    price: 'IDR 5.000.000 - 8.000.000',
    processing_time: '4-8 weeks',
    validity: '4 years',
    mandatory_for: ['F&B targeting Muslim market', 'Export to Muslim countries', 'Supermarket products'],
    issuer: 'BPJPH (Badan Penyelenggara Jaminan Produk Halal)',
    icon: 'badge',
    description: 'Official halal certification for food products. Optional but recommended for wider market reach.',
    key_points: [
      'Expands market reach',
      'Required for some exports',
      'Ingredient audit included',
      'Renewable every 4 years',
    ],
  },
  {
    id: 'pirt',
    code: 'PIRT',
    title: 'Home Industry Food License',
    title_id: 'Pangan Industri Rumah Tangga',
    category: 'Food & Beverage',
    price: 'IDR 500.000 - 1.000.000',
    processing_time: '2-3 weeks',
    validity: '5 years',
    mandatory_for: ['Small-scale food production', 'Home bakeries', 'Homemade snacks', 'Cottage food'],
    issuer: 'Dinas Kesehatan (Dinkes)',
    icon: 'cookie',
    description: 'License for small-scale home food production. More affordable option for cottage industries.',
    key_points: [
      'Low cost option',
      'For home-based production',
      'Simpler requirements',
      'Good for starting small',
    ],
  },
];

// =============================================================================
// Helper Functions
// =============================================================================

function getCategoryColor(category: string): string {
  switch (category) {
    case 'Food & Beverage':
      return 'from-orange-500/20 to-amber-500/20 border-orange-500/30';
    case 'Certification':
      return 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30';
    default:
      return 'from-gray-500/20 to-slate-500/20 border-gray-500/30';
  }
}

function getCategoryBadgeColor(category: string): string {
  switch (category) {
    case 'Food & Beverage':
      return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    case 'Certification':
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

function getIcon(icon: string) {
  switch (icon) {
    case 'utensils':
      return UtensilsCrossed;
    case 'wine':
      return Wine;
    case 'badge':
      return BadgeCheck;
    case 'cookie':
      return Cookie;
    default:
      return FileText;
  }
}

// =============================================================================
// License Card Component
// =============================================================================

interface LicenseCardProps {
  license: License;
  onClick: () => void;
}

function LicenseCard({ license, onClick }: LicenseCardProps) {
  const IconComponent = getIcon(license.icon);
  const isCritical = license.code === 'SLHS' || license.code === 'NPBBKC';

  return (
    <div
      onClick={onClick}
      className={`
        group relative overflow-hidden rounded-2xl border cursor-pointer
        bg-gradient-to-br ${getCategoryColor(license.category)}
        hover:scale-[1.02] hover:shadow-xl hover:shadow-[var(--accent)]/10
        transition-all duration-300 ease-out
      `}
    >
      {/* Critical Badge */}
      {isCritical && (
        <div className="absolute top-4 right-4 z-10">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-red-500 to-orange-500 text-white text-xs font-semibold shadow-lg">
            <AlertTriangle className="w-3.5 h-3.5" />
            Critical
          </div>
        </div>
      )}

      {/* Card Content */}
      <div className="p-6">
        {/* Code and Icon */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--background)]/60 flex items-center justify-center">
            <IconComponent className="w-6 h-6 text-[var(--accent)]" />
          </div>
          <div>
            <span className="text-2xl font-black text-[var(--foreground)] tracking-tight">
              {license.code}
            </span>
            <div className="flex items-center gap-2 mt-1">
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${getCategoryBadgeColor(license.category)}`}>
                {license.category}
              </span>
            </div>
          </div>
        </div>

        {/* Title */}
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-1 group-hover:text-[var(--accent)] transition-colors">
            {license.title}
          </h3>
          <p className="text-sm text-[var(--foreground-muted)]">{license.title_id}</p>
        </div>

        {/* Price and Time */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <div>
              <p className="text-xs text-[var(--foreground-muted)]">Price</p>
              <p className="text-sm font-semibold text-[var(--foreground)]">{license.price}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
            <Clock className="w-4 h-4 text-blue-400" />
            <div>
              <p className="text-xs text-[var(--foreground-muted)]">Processing</p>
              <p className="text-sm font-semibold text-[var(--foreground)]">{license.processing_time}</p>
            </div>
          </div>
        </div>

        {/* Key Points */}
        <div className="space-y-1.5 mb-4">
          {license.key_points.slice(0, 3).map((point, idx) => (
            <div key={idx} className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 flex-shrink-0" />
              <span className="text-sm text-[var(--foreground-secondary)] line-clamp-1">{point}</span>
            </div>
          ))}
        </div>

        {/* Warning if exists */}
        {license.warning && (
          <div className="p-2 rounded-lg bg-red-500/10 border border-red-500/20 mb-4">
            <p className="text-xs text-red-400 flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
              {license.warning}
            </p>
          </div>
        )}

        {/* CTA */}
        <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
          <span className="text-xs text-[var(--foreground-muted)]">Valid: {license.validity}</span>
          <div className="flex items-center gap-1 text-[var(--accent)] font-medium text-sm group-hover:gap-2 transition-all">
            <span>Learn More</span>
            <ChevronRight className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Hover Effect */}
      <div className="absolute inset-0 bg-gradient-to-t from-[var(--accent)]/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function LicensesPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const categories = ['Food & Beverage', 'Certification'];

  const filteredLicenses = LICENSES.filter((lic) => {
    const matchesSearch =
      !searchQuery ||
      lic.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lic.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lic.title_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !selectedCategory || lic.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categoryCounts = LICENSES.reduce((acc, lic) => {
    acc[lic.category] = (acc[lic.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const handleCardClick = (license: License) => {
    // Navigate to chat with context
    router.push(`/chat?q=${encodeURIComponent(`Tell me about ${license.title} (${license.code}) license in Indonesia`)}`);
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
          <h1 className="text-3xl font-bold text-[var(--foreground)]">Business Licenses Guide</h1>
          <p className="text-[var(--foreground-muted)] mt-2 max-w-2xl">
            Essential licenses for F&B and food businesses in Indonesia. SLHS, NPBBKC (alcohol),
            Halal certification, and more - with Bali Zero 2026 prices.
          </p>
        </div>

        {/* Bali Zero Branding */}
        <div className="hidden lg:flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
          <div className="w-10 h-10 rounded-lg bg-[var(--accent)] flex items-center justify-center">
            <UtensilsCrossed className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">Bali Zero</p>
            <p className="text-xs text-[var(--foreground-muted)]">Licensing Experts</p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
              <FileText className="w-5 h-5 text-indigo-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">{LICENSES.length}</p>
              <p className="text-xs text-[var(--foreground-muted)]">License Types</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Shield className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">100%</p>
              <p className="text-xs text-[var(--foreground-muted)]">Legal Compliance</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <Star className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">2026</p>
              <p className="text-xs text-[var(--foreground-muted)]">Updated Prices</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">Full</p>
              <p className="text-xs text-[var(--foreground-muted)]">Support</p>
            </div>
          </div>
        </div>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--foreground-muted)]" />
          <input
            type="text"
            placeholder="Search by license name or code..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-12 pr-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
          />
        </div>

        {/* Category Filter */}
        <div className="flex gap-2 flex-wrap">
          <button
            onClick={() => setSelectedCategory(null)}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
              selectedCategory === null
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--background-secondary)] text-[var(--foreground-secondary)] hover:bg-[var(--background-elevated)]'
            }`}
          >
            All ({LICENSES.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                selectedCategory === cat
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--background-secondary)] text-[var(--foreground-secondary)] hover:bg-[var(--background-elevated)]'
              }`}
            >
              {cat} ({categoryCounts[cat] || 0})
            </button>
          ))}
        </div>
      </div>

      {/* License Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-2 gap-6">
        {filteredLicenses.map((license) => (
          <LicenseCard key={license.id} license={license} onClick={() => handleCardClick(license)} />
        ))}
      </div>

      {/* Empty State */}
      {filteredLicenses.length === 0 && (
        <div className="p-12 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)] text-center">
          <FileText className="w-16 h-16 text-[var(--foreground-muted)] mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">No licenses found</h3>
          <p className="text-sm text-[var(--foreground-muted)]">
            Try adjusting your search or filter criteria.
          </p>
        </div>
      )}

      {/* Restaurant Checklist */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-orange-500/10 to-amber-500/10 border border-orange-500/20">
        <h3 className="text-lg font-bold text-[var(--foreground)] mb-4 flex items-center gap-2">
          <UtensilsCrossed className="w-5 h-5 text-orange-400" />
          Restaurant Opening Checklist
        </h3>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-[var(--foreground)]">PT PMA / Company Setup</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-[var(--foreground)]">NIB (Business ID)</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-[var(--foreground)]">SLHS (Hygiene Certificate)</span>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-[var(--foreground)]">NPBBKC (if serving alcohol)</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-[var(--foreground)]">NPWP & Tax Registration</span>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--background)]/50">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-[var(--foreground)]">Halal Certificate (optional)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Contact CTA */}
      <div className="p-8 rounded-2xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)] mb-2">
              Need Help with Business Licenses?
            </h3>
            <p className="text-[var(--foreground-secondary)]">
              Our licensing experts handle the entire process from application to approval.
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
