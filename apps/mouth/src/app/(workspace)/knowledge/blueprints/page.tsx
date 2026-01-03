'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Download,
  Building2,
  Hotel,
  Home,
  Tent,
  Briefcase,
  Scissors,
  FileText,
  Shield,
  TrendingUp,
  Star,
  Search,
  Filter,
  Code,
  Gamepad2,
  Globe,
  Database,
  Server,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// =============================================================================
// Blueprint Data
// =============================================================================

interface Blueprint {
  id: string;
  kbli_code: string;
  title: string;
  title_id: string;
  category: 'Hospitality' | 'Real Estate' | 'Services' | 'Technology';
  risk_level: 'Low' | 'Medium' | 'High';
  pma_allowed: boolean;
  pma_percentage: string;
  pdf_filename: string;
  pdf_url?: string; // Direct download URL
  icon: 'hotel' | 'home' | 'tent' | 'building' | 'scissors' | 'code' | 'gamepad' | 'globe' | 'database' | 'server';
  description: string;
}

const BLUEPRINTS: Blueprint[] = [
  {
    id: 'kbli-55110',
    kbli_code: '55110',
    title: 'Star Hotel',
    title_id: 'Hotel Bintang',
    category: 'Hospitality',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55110_Star_Hotel.pdf',
    icon: 'hotel',
    description: 'Comprehensive guide for establishing star-rated hotels in Indonesia under PP 28/2025.',
  },
  {
    id: 'kbli-55120',
    kbli_code: '55120',
    title: 'Budget Hotel (Melati)',
    title_id: 'Hotel Melati',
    category: 'Hospitality',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55120_Budget_Hotel.pdf',
    icon: 'hotel',
    description: 'Investment guide for non-star rated hotels and budget accommodations.',
  },
  {
    id: 'kbli-55130',
    kbli_code: '55130',
    title: 'Homestay (Pondok Wisata)',
    title_id: 'Pondok Wisata',
    category: 'Hospitality',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55130_Homestay.pdf',
    icon: 'home',
    description: 'Blueprint for tourism homestays with high guest interaction.',
  },
  {
    id: 'kbli-55191',
    kbli_code: '55191',
    title: 'Youth Hostel',
    title_id: 'Penginapan Remaja',
    category: 'Hospitality',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55191_Youth_Hostel.pdf',
    icon: 'home',
    description: 'Guide for youth hostels with shared room accommodations.',
  },
  {
    id: 'kbli-55192',
    kbli_code: '55192',
    title: 'Campground & Caravan Park',
    title_id: 'Bumi Perkemahan',
    category: 'Hospitality',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55192_Campground_Caravan.pdf',
    icon: 'tent',
    description: 'Investment guide for campgrounds and caravan parks.',
  },
  {
    id: 'kbli-55193',
    kbli_code: '55193',
    title: 'Villa',
    title_id: 'Vila',
    category: 'Hospitality',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55193_Villa.pdf',
    icon: 'home',
    description: 'Complete guide for villa investment and operations in Indonesia.',
  },
  {
    id: 'kbli-55194',
    kbli_code: '55194',
    title: 'Apartment Hotel (Condotel)',
    title_id: 'Kondominium Hotel',
    category: 'Hospitality',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55194_Condotel.pdf',
    icon: 'building',
    description: 'Blueprint for apartment hotels and condotel investments.',
  },
  {
    id: 'kbli-55199',
    kbli_code: '55199',
    title: 'Other Short-Term Accommodation',
    title_id: 'Akomodasi Jangka Pendek Lainnya',
    category: 'Hospitality',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55199_Bungalow_Cottage.pdf',
    icon: 'home',
    description: 'Guide for bungalows, cottages and other short-term accommodations.',
  },
  {
    id: 'kbli-55900',
    kbli_code: '55900',
    title: 'Alternative Accommodation',
    title_id: 'Akomodasi Lainnya',
    category: 'Hospitality',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_55900_Alternative_Accommodation.pdf',
    icon: 'home',
    description: 'Long-term and alternative accommodation investment guide.',
  },
  {
    id: 'kbli-68111',
    kbli_code: '68111',
    title: 'Real Estate Operations',
    title_id: 'Real Estat',
    category: 'Real Estate',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_68111_Real_Estate.pdf',
    icon: 'building',
    description: 'Strategic guide for real estate operations and property management.',
  },
  {
    id: 'kbli-96121',
    kbli_code: '96121',
    title: 'Massage Services',
    title_id: 'Aktivitas Pijat',
    category: 'Services',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_96121_Massage_Services.pdf',
    icon: 'scissors',
    description: 'Blueprint for massage and wellness services business.',
  },
  // Technology Category
  {
    id: 'kbli-62011',
    kbli_code: '62011',
    title: 'Video Game Development',
    title_id: 'Aktivitas Pengembangan Video Game',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_62011_Videogame_Teknis.pdf',
    pdf_url: '/blueprints/KBLI_62011_Videogame_Teknis.pdf',
    icon: 'gamepad',
    description: 'Technical guide for video game development business in Indonesia.',
  },
  {
    id: 'kbli-62011-bisnis',
    kbli_code: '62011',
    title: 'Video Game Development (Business)',
    title_id: 'Aktivitas Pengembangan Video Game - Bisnis',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_62011_Videogame_Bisnis.pdf',
    pdf_url: '/blueprints/KBLI_62011_Videogame_Bisnis.pdf',
    icon: 'gamepad',
    description: 'Business guide for video game development company setup.',
  },
  {
    id: 'kbli-62012',
    kbli_code: '62012',
    title: 'E-Commerce App Development',
    title_id: 'Aplikasi Perdagangan Internet',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_62012_Ecommerce_Teknis.pdf',
    pdf_url: '/blueprints/KBLI_62012_Ecommerce_Teknis.pdf',
    icon: 'globe',
    description: 'Technical guide for e-commerce application development.',
  },
  {
    id: 'kbli-62014',
    kbli_code: '62014',
    title: 'Blockchain Technology',
    title_id: 'Teknologi Blockchain',
    category: 'Technology',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_62014_Blockchain_Teknis.pdf',
    pdf_url: '/blueprints/KBLI_62014_Blockchain_Teknis.pdf',
    icon: 'code',
    description: 'Technical guide for blockchain technology development.',
  },
  {
    id: 'kbli-62014-bisnis',
    kbli_code: '62014',
    title: 'Blockchain Technology (Business)',
    title_id: 'Teknologi Blockchain - Bisnis',
    category: 'Technology',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_62014_Blockchain_Bisnis.pdf',
    pdf_url: '/blueprints/KBLI_62014_Blockchain_Bisnis.pdf',
    icon: 'code',
    description: 'Business guide for blockchain company setup in Indonesia.',
  },
  {
    id: 'kbli-62019',
    kbli_code: '62019',
    title: 'Computer Programming',
    title_id: 'Pemrograman Komputer Lainnya',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_62019_Programming_Teknis.pdf',
    pdf_url: '/blueprints/KBLI_62019_Programming_Teknis.pdf',
    icon: 'code',
    description: 'Technical guide for software development and programming services.',
  },
  {
    id: 'kbli-63111',
    kbli_code: '63111',
    title: 'Data Processing',
    title_id: 'Aktivitas Pengolahan Data',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_63111_Data_Processing_Teknis.pdf',
    pdf_url: '/blueprints/KBLI_63111_Data_Processing_Teknis.pdf',
    icon: 'database',
    description: 'Technical guide for data processing and analytics services.',
  },
  {
    id: 'kbli-63111-bisnis',
    kbli_code: '63111',
    title: 'Data Processing (Business)',
    title_id: 'Aktivitas Pengolahan Data - Bisnis',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_63111_Data_Processing_Bisnis.pdf',
    pdf_url: '/blueprints/KBLI_63111_Data_Processing_Bisnis.pdf',
    icon: 'database',
    description: 'Business guide for data processing company setup.',
  },
  {
    id: 'kbli-63112',
    kbli_code: '63112',
    title: 'Web Hosting Services',
    title_id: 'Aktivitas Hosting',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_63112_Hosting_Teknis.pdf',
    pdf_url: '/blueprints/KBLI_63112_Hosting_Teknis.pdf',
    icon: 'server',
    description: 'Technical guide for web hosting and cloud services.',
  },
  {
    id: 'kbli-63112-bisnis',
    kbli_code: '63112',
    title: 'Web Hosting Services (Business)',
    title_id: 'Aktivitas Hosting - Bisnis',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_63112_Hosting_Bisnis.pdf',
    pdf_url: '/blueprints/KBLI_63112_Hosting_Bisnis.pdf',
    icon: 'server',
    description: 'Business guide for hosting company setup in Indonesia.',
  },
  {
    id: 'kbli-63121',
    kbli_code: '63121',
    title: 'Web Portal (Non-Commercial)',
    title_id: 'Portal Web Digital Non-Komersial',
    category: 'Technology',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_63121_Portal_Web_Teknis.pdf',
    pdf_url: '/blueprints/KBLI_63121_Portal_Web_Teknis.pdf',
    icon: 'globe',
    description: 'Technical guide for non-commercial web portals and platforms.',
  },
];

// =============================================================================
// Helper Functions
// =============================================================================

function getRiskColor(risk: string): string {
  switch (risk) {
    case 'Low':
      return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30';
    case 'Medium':
      return 'text-amber-400 bg-amber-400/10 border-amber-400/30';
    case 'High':
      return 'text-red-400 bg-red-400/10 border-red-400/30';
    default:
      return 'text-gray-400 bg-gray-400/10 border-gray-400/30';
  }
}

function getCategoryColor(category: string): string {
  switch (category) {
    case 'Hospitality':
      return 'from-blue-500/20 to-cyan-500/20 border-blue-500/30';
    case 'Real Estate':
      return 'from-purple-500/20 to-pink-500/20 border-purple-500/30';
    case 'Services':
      return 'from-emerald-500/20 to-teal-500/20 border-emerald-500/30';
    case 'Technology':
      return 'from-orange-500/20 to-red-500/20 border-orange-500/30';
    default:
      return 'from-gray-500/20 to-slate-500/20 border-gray-500/30';
  }
}

function getIcon(icon: string) {
  switch (icon) {
    case 'hotel':
      return Hotel;
    case 'home':
      return Home;
    case 'tent':
      return Tent;
    case 'building':
      return Building2;
    case 'scissors':
      return Scissors;
    case 'code':
      return Code;
    case 'gamepad':
      return Gamepad2;
    case 'globe':
      return Globe;
    case 'database':
      return Database;
    case 'server':
      return Server;
    default:
      return FileText;
  }
}

// =============================================================================
// Blueprint Card Component
// =============================================================================

interface BlueprintCardProps {
  blueprint: Blueprint;
}

function BlueprintCard({ blueprint }: BlueprintCardProps) {
  const IconComponent = getIcon(blueprint.icon);

  const handleDownload = () => {
    if (blueprint.pdf_url) {
      // Direct download from public folder
      const link = document.createElement('a');
      link.href = blueprint.pdf_url;
      link.download = blueprint.pdf_filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      // Fallback to Google Drive folder
      const driveFolder = 'https://drive.google.com/drive/folders/1DOBzlToHhYrq_qZb5hAVdTsBOKBCCCti';
      window.open(driveFolder, '_blank');
    }
  };

  return (
    <div
      className={`
        group relative overflow-hidden rounded-2xl border cursor-pointer
        bg-gradient-to-br ${getCategoryColor(blueprint.category)}
        hover:scale-[1.02] hover:shadow-xl hover:shadow-[var(--accent)]/10
        transition-all duration-300 ease-out
      `}
    >
      {/* PMA Badge */}
      {blueprint.pma_allowed && (
        <div className="absolute top-4 right-4 z-10">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-semibold shadow-lg">
            <Shield className="w-3.5 h-3.5" />
            {blueprint.pma_percentage} PMA
          </div>
        </div>
      )}

      {/* Card Content */}
      <div className="p-6">
        {/* KBLI Code - Prominent Display */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-xl bg-[var(--background)]/60 flex items-center justify-center">
            <IconComponent className="w-6 h-6 text-[var(--accent)]" />
          </div>
          <div>
            <span className="text-2xl font-black text-[var(--foreground)] tracking-tight">
              {blueprint.kbli_code}
            </span>
            <div className="flex items-center gap-2 mt-1">
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${getRiskColor(blueprint.risk_level)}`}>
                {blueprint.risk_level} Risk
              </span>
            </div>
          </div>
        </div>

        {/* Title */}
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-1 group-hover:text-[var(--accent)] transition-colors">
            {blueprint.title}
          </h3>
          <p className="text-sm text-[var(--foreground-muted)]">{blueprint.title_id}</p>
        </div>

        {/* Description */}
        <p className="text-sm text-[var(--foreground-secondary)] mb-5 line-clamp-2">
          {blueprint.description}
        </p>

        {/* Download Button */}
        <div className="flex items-center justify-between pt-4 border-t border-[var(--border)]">
          <span className="text-xs text-[var(--foreground-muted)]">{blueprint.category}</span>
          <Button
            onClick={handleDownload}
            variant="outline"
            size="sm"
            className="gap-2 bg-[var(--background)]/60 hover:bg-[var(--accent)] hover:text-white transition-all"
          >
            <Download className="w-4 h-4" />
            Download PDF
          </Button>
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

export default function BlueprintsPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  const categories = ['Hospitality', 'Real Estate', 'Services', 'Technology'];

  const filteredBlueprints = BLUEPRINTS.filter((bp) => {
    const matchesSearch =
      !searchQuery ||
      bp.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      bp.kbli_code.includes(searchQuery) ||
      bp.title_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = !selectedCategory || bp.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const categoryCounts = BLUEPRINTS.reduce((acc, bp) => {
    acc[bp.category] = (acc[bp.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

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
          <h1 className="text-3xl font-bold text-[var(--foreground)]">Company & Classifications</h1>
          <p className="text-[var(--foreground-muted)] mt-2 max-w-2xl">
            KBLI Business Classification Blueprints based on PP 28/2025. Download comprehensive guides
            for starting your business in Indonesia.
          </p>
        </div>

        {/* Bali Zero Branding */}
        <div className="hidden lg:flex items-center gap-3 px-4 py-3 rounded-xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
          <div className="w-10 h-10 rounded-lg bg-[var(--accent)] flex items-center justify-center">
            <Building2 className="w-5 h-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">Bali Zero</p>
            <p className="text-xs text-[var(--foreground-muted)]">Business Setup Experts</p>
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
              <p className="text-2xl font-bold text-[var(--foreground)]">{BLUEPRINTS.length}</p>
              <p className="text-xs text-[var(--foreground-muted)]">Blueprints</p>
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
              <p className="text-xs text-[var(--foreground-muted)]">PMA Allowed</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 flex items-center justify-center">
              <Star className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">PP 28/2025</p>
              <p className="text-xs text-[var(--foreground-muted)]">Latest Regulation</p>
            </div>
          </div>
        </div>
        <div className="p-4 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <p className="text-2xl font-bold text-[var(--foreground)]">Free</p>
              <p className="text-xs text-[var(--foreground-muted)]">Download</p>
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
            placeholder="Search by KBLI code or title..."
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
            All ({BLUEPRINTS.length})
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

      {/* Blueprint Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredBlueprints.map((blueprint) => (
          <BlueprintCard key={blueprint.id} blueprint={blueprint} />
        ))}
      </div>

      {/* Empty State */}
      {filteredBlueprints.length === 0 && (
        <div className="p-12 rounded-xl bg-[var(--background-secondary)] border border-[var(--border)] text-center">
          <FileText className="w-16 h-16 text-[var(--foreground-muted)] mx-auto mb-4 opacity-50" />
          <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">No blueprints found</h3>
          <p className="text-sm text-[var(--foreground-muted)]">
            Try adjusting your search or filter criteria.
          </p>
        </div>
      )}

      {/* Contact CTA */}
      <div className="p-8 rounded-2xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)] mb-2">
              Need Help Setting Up Your Business?
            </h3>
            <p className="text-[var(--foreground-secondary)]">
              Our PT PMA experts can guide you through the entire process.
              Free consultation available.
            </p>
          </div>
          <Button
            onClick={() => router.push('/chat')}
            className="gap-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white whitespace-nowrap"
          >
            <Building2 className="w-4 h-4" />
            Ask Zantara AI
          </Button>
        </div>
      </div>
    </div>
  );
}
