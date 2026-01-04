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
  Calculator,
  Receipt,
  Building2,
  Users,
  Calendar,
  Clock,
  DollarSign,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// =============================================================================
// Tax Service Data
// =============================================================================

interface TaxService {
  id: string;
  code: string;
  title: string;
  title_id: string;
  category: 'Registration' | 'Filing' | 'Insurance' | 'Reporting';
  price: string;
  price_note?: string;
  processing_time: string;
  frequency: string;
  mandatory: boolean;
  icon: 'calculator' | 'receipt' | 'users' | 'calendar' | 'building';
  description: string;
  key_points: string[];
  warning?: string;
}

const TAX_SERVICES: TaxService[] = [
  {
    id: 'npwp-personal',
    code: 'NPWP',
    title: 'NPWP Personal + Coretax',
    title_id: 'Nomor Pokok Wajib Pajak Pribadi',
    category: 'Registration',
    price: 'IDR 1.000.000',
    processing_time: '2-3 days',
    frequency: 'One-time',
    mandatory: true,
    icon: 'calculator',
    description: 'Personal Tax ID registration with Coretax system integration. Required for all working individuals in Indonesia.',
    key_points: [
      'Required for KITAS holders',
      'Needed for bank accounts',
      'Permanent validity',
      'Includes Coretax migration',
    ],
  },
  {
    id: 'npwpd-corporate',
    code: 'NPWPD',
    title: 'NPWPD Corporate',
    title_id: 'NPWP Daerah / Badan',
    category: 'Registration',
    price: 'IDR 2.500.000',
    processing_time: '3-5 days',
    frequency: 'One-time',
    mandatory: true,
    icon: 'building',
    description: 'Corporate/Regional Tax ID for companies. Required for all PT PMA and local businesses.',
    key_points: [
      'Required after company setup',
      'Enables invoice issuance',
      'VAT credit eligibility',
      'Local tax compliance',
    ],
  },
  {
    id: 'spt-personal',
    code: 'SPT',
    title: 'SPT Annual Personal',
    title_id: 'Surat Pemberitahuan Tahunan Pribadi',
    category: 'Filing',
    price: 'IDR 2.000.000',
    processing_time: '1-2 weeks',
    frequency: 'Annually (by March 31)',
    mandatory: true,
    icon: 'receipt',
    description: 'Individual annual tax return filing. Mandatory for all NPWP holders with Indonesian income.',
    key_points: [
      'Deadline: March 31',
      'Covers worldwide income',
      '183+ days = tax resident',
      'Penalties for late filing',
    ],
    warning: 'Late filing penalty: IDR 100,000 + 2%/month interest',
  },
  {
    id: 'spt-company-zero',
    code: 'SPT-Z',
    title: 'SPT Annual Company (Zero)',
    title_id: 'SPT Tahunan Badan (Nihil)',
    category: 'Filing',
    price: 'IDR 3.000.000',
    price_note: 'Starting from',
    processing_time: '1-2 weeks',
    frequency: 'Annually (by April 30)',
    mandatory: true,
    icon: 'receipt',
    description: 'Annual tax return for dormant or zero-activity companies. Still mandatory even with no revenue.',
    key_points: [
      'For dormant companies',
      'NIL declaration required',
      'Maintains compliance',
      'Simpler documentation',
    ],
  },
  {
    id: 'spt-company-operational',
    code: 'SPT-OP',
    title: 'SPT Annual Company (Operational)',
    title_id: 'SPT Tahunan Badan (Operasional)',
    category: 'Filing',
    price: 'IDR 4.000.000',
    price_note: 'Starting from',
    processing_time: '2-4 weeks',
    frequency: 'Annually (by April 30)',
    mandatory: true,
    icon: 'receipt',
    description: 'Comprehensive annual tax return for active companies with revenue and expenses.',
    key_points: [
      'Full financial statements',
      '22% corporate tax rate',
      'Audit-ready documentation',
      'Professional preparation',
    ],
    warning: 'Late filing penalty: IDR 1,000,000 + potential audit',
  },
  {
    id: 'monthly-tax',
    code: 'MONTHLY',
    title: 'Monthly Tax Report',
    title_id: 'Laporan Pajak Bulanan',
    category: 'Filing',
    price: 'IDR 1.500.000',
    price_note: 'Starting from',
    processing_time: 'Monthly',
    frequency: 'Monthly (by 20th)',
    mandatory: true,
    icon: 'calendar',
    description: 'Monthly tax compliance including PPh 21, PPh 23, PPh 25, and PPN filing.',
    key_points: [
      'PPh 21 employee withholding',
      'PPh 23 service withholding',
      'PPN (VAT) reporting',
      'Payment reminders included',
    ],
  },
  {
    id: 'bpjs-health',
    code: 'BPJS-K',
    title: 'BPJS Health Insurance',
    title_id: 'BPJS Kesehatan',
    category: 'Insurance',
    price: 'IDR 2.500.000',
    price_note: 'Per company',
    processing_time: '2-3 weeks',
    frequency: 'One-time setup',
    mandatory: true,
    icon: 'users',
    description: 'National Health Insurance registration. Mandatory for all KITAS holders and PT PMA employees.',
    key_points: [
      'Required for KITAS extension',
      'Covers medical expenses',
      'Minimum 2 people/company',
      'Monthly premium varies by class',
    ],
    warning: 'Cannot extend KITAS without BPJS payment proof!',
  },
  {
    id: 'bpjs-employment',
    code: 'BPJS-TK',
    title: 'BPJS Employment Insurance',
    title_id: 'BPJS Ketenagakerjaan',
    category: 'Insurance',
    price: 'IDR 1.500.000',
    price_note: 'Per company',
    processing_time: '2-3 weeks',
    frequency: 'One-time setup',
    mandatory: true,
    icon: 'users',
    description: 'Employment Insurance covering work accidents, death benefits, and pension.',
    key_points: [
      'Work accident coverage (JKK)',
      'Death benefit (JKM)',
      'Old age savings (JHT)',
      'Pension program (JP)',
    ],
  },
  {
    id: 'lkpm',
    code: 'LKPM',
    title: 'LKPM Report',
    title_id: 'Laporan Kegiatan Penanaman Modal',
    category: 'Reporting',
    price: 'IDR 1.000.000',
    price_note: 'Per quarter',
    processing_time: '1 week',
    frequency: 'Quarterly',
    mandatory: true,
    icon: 'calendar',
    description: 'Quarterly Investment Activity Report to BKPM. Mandatory for all PT PMA companies.',
    key_points: [
      'Due 10th of Q+1 month',
      'Investment realization',
      'Employment data',
      'OSS suspension if late',
    ],
    warning: 'Late submission = OSS access suspended!',
  },
];

// =============================================================================
// Helper Functions
// =============================================================================

function getCategoryColor(category: string): string {
  switch (category) {
    case 'Registration':
      return 'from-blue-500/20 to-cyan-500/20 border-blue-500/30';
    case 'Filing':
      return 'from-purple-500/20 to-pink-500/20 border-purple-500/30';
    case 'Insurance':
      return 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30';
    case 'Reporting':
      return 'from-amber-500/20 to-orange-500/20 border-amber-500/30';
    default:
      return 'from-gray-500/20 to-slate-500/20 border-gray-500/30';
  }
}

function getCategoryBadgeColor(category: string): string {
  switch (category) {
    case 'Registration':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'Filing':
      return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    case 'Insurance':
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    case 'Reporting':
      return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    default:
      return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
  }
}

function getIcon(icon: string) {
  switch (icon) {
    case 'calculator':
      return Calculator;
    case 'receipt':
      return Receipt;
    case 'users':
      return Users;
    case 'calendar':
      return Calendar;
    case 'building':
      return Building2;
    default:
      return FileText;
  }
}

// =============================================================================
// Tax Card Component
// =============================================================================

interface TaxCardProps {
  service: TaxService;
  onClick: () => void;
}

function TaxCard({ service, onClick }: TaxCardProps) {
  const IconComponent = getIcon(service.icon);

  return (
    <div
      onClick={onClick}
      className={`
        group relative overflow-hidden rounded-xl border cursor-pointer
        bg-gradient-to-br ${getCategoryColor(service.category)}
        hover:scale-[1.02] hover:shadow-lg hover:shadow-[var(--accent)]/10
        transition-all duration-300 ease-out
      `}
    >
      {/* Mandatory Badge - 50% smaller */}
      {service.mandatory && (
        <div className="absolute top-1.5 right-1.5 z-10">
          <div className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-gradient-to-r from-red-500 to-orange-500 text-white text-[8px] font-semibold shadow-sm">
            <AlertTriangle className="w-2 h-2" />
            Mandatory
          </div>
        </div>
      )}

      {/* Card Content - 50% smaller */}
      <div className="p-2 pt-6">
        {/* Code and Icon */}
        <div className="flex items-center gap-1.5 mb-1.5">
          <div className="w-6 h-6 rounded bg-[var(--background)]/60 flex items-center justify-center">
            <IconComponent className="w-3 h-3 text-[var(--accent)]" />
          </div>
          <div>
            <span className="text-sm font-black text-[var(--foreground)] tracking-tight">
              {service.code}
            </span>
            <div className="flex items-center gap-1 mt-0.5">
              <span className={`px-1 py-0 text-[8px] font-medium rounded-full border ${getCategoryBadgeColor(service.category)}`}>
                {service.category}
              </span>
            </div>
          </div>
        </div>

        {/* Title */}
        <div className="mb-1.5">
          <h3 className="text-xs font-semibold text-[var(--foreground)] mb-0 group-hover:text-[var(--accent)] transition-colors line-clamp-1">
            {service.title}
          </h3>
          <p className="text-[10px] text-[var(--foreground-muted)] line-clamp-1">{service.title_id}</p>
        </div>

        {/* Price and Time */}
        <div className="grid grid-cols-2 gap-1.5 mb-1.5">
          <div className="flex items-center gap-1 p-1 rounded bg-[var(--background)]/50">
            <DollarSign className="w-2.5 h-2.5 text-emerald-400" />
            <div>
              <p className="text-[8px] text-[var(--foreground-muted)] leading-tight">
                {service.price_note || 'Price'}
              </p>
              <p className="text-[10px] font-semibold text-[var(--foreground)] leading-tight">{service.price}</p>
            </div>
          </div>
          <div className="flex items-center gap-1 p-1 rounded bg-[var(--background)]/50">
            <Clock className="w-2.5 h-2.5 text-blue-400" />
            <div>
              <p className="text-[8px] text-[var(--foreground-muted)] leading-tight">Frequency</p>
              <p className="text-[10px] font-semibold text-[var(--foreground)] leading-tight line-clamp-1">{service.frequency}</p>
            </div>
          </div>
        </div>

        {/* Key Points */}
        <div className="space-y-0.5 mb-1.5">
          {service.key_points.slice(0, 2).map((point, idx) => (
            <div key={idx} className="flex items-start gap-1">
              <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400 mt-0.5 flex-shrink-0" />
              <span className="text-[10px] text-[var(--foreground-secondary)] line-clamp-1">{point}</span>
            </div>
          ))}
        </div>

        {/* Warning if exists */}
        {service.warning && (
          <div className="p-1 rounded bg-red-500/10 border border-red-500/20 mb-1.5">
            <p className="text-[8px] text-red-400 flex items-center gap-1 line-clamp-1">
              <AlertTriangle className="w-2 h-2 flex-shrink-0" />
              {service.warning}
            </p>
          </div>
        )}

        {/* CTA */}
        <div className="flex items-center justify-between pt-1.5 border-t border-[var(--border)]">
          <span className="text-[8px] text-[var(--foreground-muted)]">{service.processing_time}</span>
          <div className="flex items-center gap-0.5 text-[var(--accent)] font-medium text-[10px] group-hover:gap-1 transition-all">
            <span>More</span>
            <ChevronRight className="w-2.5 h-2.5" />
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

export default function TaxPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const categories = ['Registration', 'Filing', 'Insurance', 'Reporting'];

  const filteredServices = TAX_SERVICES.filter((svc) => {
    const matchesSearch =
      !searchQuery ||
      svc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      svc.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      svc.title_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !selectedCategory || svc.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categoryCounts = TAX_SERVICES.reduce((acc, svc) => {
    acc[svc.category] = (acc[svc.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const handleCardClick = (service: TaxService) => {
    // Navigate to chat with context
    router.push(`/chat?q=${encodeURIComponent(`Tell me about ${service.title} in Indonesia`)}`);
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
          <h1 className="text-3xl font-bold text-[var(--foreground)]">Tax & NPWP Guide</h1>
          <p className="text-[var(--foreground-muted)] mt-2 max-w-2xl">
            Complete guide to Indonesian taxation. NPWP registration, SPT filing, BPJS insurance,
            and LKPM reporting - all with Bali Zero 2026 prices.
          </p>
        </div>

        {/* Bali Zero Branding */}
        <div className="hidden lg:flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
          <div className="w-10 h-10 rounded-lg bg-[var(--accent)] flex items-center justify-center">
            <Calculator className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">Bali Zero</p>
            <p className="text-xs text-[var(--foreground-muted)]">Tax Compliance Experts</p>
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
              <p className="text-2xl font-bold text-[var(--foreground)]">{TAX_SERVICES.length}</p>
              <p className="text-xs text-[var(--foreground-muted)]">Services</p>
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
              <p className="text-xs text-[var(--foreground-muted)]">Compliance</p>
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
              <p className="text-2xl font-bold text-[var(--foreground)]">24/7</p>
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
            placeholder="Search by service name or code..."
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
            All ({TAX_SERVICES.length})
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

      {/* Service Cards - 4 columns compact */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {filteredServices.map((service) => (
          <TaxCard key={service.id} service={service} onClick={() => handleCardClick(service)} />
        ))}
      </div>

      {/* Empty State */}
      {filteredServices.length === 0 && (
        <div className="p-12 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)] text-center">
          <FileText className="w-16 h-16 text-[var(--foreground-muted)] mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">No services found</h3>
          <p className="text-sm text-[var(--foreground-muted)]">
            Try adjusting your search or filter criteria.
          </p>
        </div>
      )}

      {/* Important Deadlines */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/20">
        <h3 className="text-lg font-bold text-[var(--foreground)] mb-4 flex items-center gap-2">
          <Calendar className="w-5 h-5 text-amber-400" />
          Important Tax Deadlines
        </h3>
        <div className="grid md:grid-cols-3 gap-4">
          <div className="p-3 rounded-lg bg-[var(--background)]/50">
            <p className="text-sm font-semibold text-[var(--foreground)]">SPT Personal</p>
            <p className="text-xs text-[var(--foreground-muted)]">March 31st each year</p>
          </div>
          <div className="p-3 rounded-lg bg-[var(--background)]/50">
            <p className="text-sm font-semibold text-[var(--foreground)]">SPT Corporate</p>
            <p className="text-xs text-[var(--foreground-muted)]">April 30th each year</p>
          </div>
          <div className="p-3 rounded-lg bg-[var(--background)]/50">
            <p className="text-sm font-semibold text-[var(--foreground)]">LKPM Quarterly</p>
            <p className="text-xs text-[var(--foreground-muted)]">10th of Q+1 month</p>
          </div>
        </div>
      </div>

      {/* Contact CTA */}
      <div className="p-8 rounded-2xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)] mb-2">
              Need Help with Tax Compliance?
            </h3>
            <p className="text-[var(--foreground-secondary)]">
              Our tax experts can guide you through registration, filing, and compliance.
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
