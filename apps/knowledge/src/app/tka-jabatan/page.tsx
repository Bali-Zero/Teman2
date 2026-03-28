'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Search,
  Users,
  Building2,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  ChevronRight,
  X,
  Briefcase,
  Factory,
  GraduationCap,
  Landmark,
  Plane,
  Utensils,
  Pickaxe,
  Zap,
  Droplets,
  Truck,
  Music,
  Building,
  Stethoscope,
  Wifi,
  Coins,
  Wrench,
  TreePine,
  HardHat,
  Cog,
} from 'lucide-react';
import api from '@/lib/api';

// Types
interface ForbiddenPosition {
  id: number;
  name_id: string;
  name_en: string;
  category: string;
  risk_level: string;
}

interface AllowedSector {
  id: number;
  sector_name: string;
  sector_name_en: string;
  kbli_range: string[];
  kbli_section: string;
  allowed_positions_count?: number;
  example_positions?: string[];
  special_note?: string;
}

// Data
const forbiddenPositions: ForbiddenPosition[] = [
  {
    id: 1,
    name_id: 'Direktur Personalia',
    name_en: 'Personnel Director',
    category: 'director',
    risk_level: 'absolute',
  },
  {
    id: 2,
    name_id: 'Manajer Hubungan Industrial',
    name_en: 'Industrial Relations Manager',
    category: 'manager',
    risk_level: 'absolute',
  },
  {
    id: 3,
    name_id: 'Manajer Personalia',
    name_en: 'Human Resource Manager',
    category: 'manager',
    risk_level: 'absolute',
  },
  {
    id: 4,
    name_id: 'Supervisor Pengembangan Personalia',
    name_en: 'Personnel Development Supervisor',
    category: 'supervisor',
    risk_level: 'absolute',
  },
  {
    id: 5,
    name_id: 'Supervisor Perekrutan Personalia',
    name_en: 'Personnel Recruitment Supervisor',
    category: 'supervisor',
    risk_level: 'absolute',
  },
  {
    id: 6,
    name_id: 'Supervisor Penempatan Personalia',
    name_en: 'Personnel Placement Supervisor',
    category: 'supervisor',
    risk_level: 'absolute',
  },
  {
    id: 7,
    name_id: 'Supervisor Pembinaan Karir Pegawai',
    name_en: 'Employee Career Development Supervisor',
    category: 'supervisor',
    risk_level: 'absolute',
  },
  {
    id: 8,
    name_id: 'Penata Usaha Personalia',
    name_en: 'Personnel Administrator',
    category: 'administrator',
    risk_level: 'absolute',
  },
  {
    id: 9,
    name_id: 'Kepala Eksekutif Kantor',
    name_en: 'Chief Executive Officer',
    category: 'executive',
    risk_level: 'conditional',
  },
  {
    id: 10,
    name_id: 'Ahli Pengembangan Personalia dan Karir',
    name_en: 'Personnel and Career Development Specialist',
    category: 'specialist',
    risk_level: 'absolute',
  },
  {
    id: 11,
    name_id: 'Spesialis Personalia',
    name_en: 'Personnel Specialist',
    category: 'specialist',
    risk_level: 'absolute',
  },
  {
    id: 12,
    name_id: 'Penasehat Karir',
    name_en: 'Career Advisor',
    category: 'advisor',
    risk_level: 'absolute',
  },
  {
    id: 13,
    name_id: 'Penasehat Tenaga Kerja',
    name_en: 'Job Advisor',
    category: 'advisor',
    risk_level: 'absolute',
  },
  {
    id: 14,
    name_id: 'Pembimbing dan Konseling Jabatan',
    name_en: 'Job Counselor',
    category: 'advisor',
    risk_level: 'absolute',
  },
  {
    id: 15,
    name_id: 'Perantara Tenaga Kerja',
    name_en: 'Employment Mediator',
    category: 'intermediary',
    risk_level: 'absolute',
  },
  {
    id: 16,
    name_id: 'Pengadministrasi Pelatihan Pegawai',
    name_en: 'Employee Training Administrator',
    category: 'administrator',
    risk_level: 'absolute',
  },
  {
    id: 17,
    name_id: 'Pewawancara Pegawai',
    name_en: 'Job Interviewer',
    category: 'specialist',
    risk_level: 'absolute',
  },
  {
    id: 18,
    name_id: 'Analis Jabatan',
    name_en: 'Job Analyst',
    category: 'analyst',
    risk_level: 'absolute',
  },
  {
    id: 19,
    name_id: 'Penyelenggara Keselamatan Kerja Pegawai',
    name_en: 'Occupational Safety Specialist',
    category: 'safety',
    risk_level: 'absolute',
  },
];

const allowedSectors: AllowedSector[] = [
  {
    id: 1,
    sector_name: 'Konstruksi',
    sector_name_en: 'Construction',
    kbli_range: ['41', '42', '43'],
    kbli_section: 'F',
    allowed_positions_count: 181,
    example_positions: ['Manajer Proyek', 'Ahli Geofisika', 'Ahli Teknik', 'Arsitek', 'Topografer'],
  },
  {
    id: 2,
    sector_name: 'Real Estate',
    sector_name_en: 'Real Estate',
    kbli_range: ['68'],
    kbli_section: 'L',
  },
  {
    id: 3,
    sector_name: 'Pendidikan',
    sector_name_en: 'Education',
    kbli_range: ['85'],
    kbli_section: 'P',
    allowed_positions_count: 143,
    example_positions: ['Kepala Sekolah', 'Dosen', 'Guru', 'Instruktur Keterampilan'],
  },
  {
    id: 4,
    sector_name: 'Industri Pengolahan',
    sector_name_en: 'Manufacturing',
    kbli_range: [
      '10',
      '11',
      '12',
      '13',
      '14',
      '15',
      '16',
      '17',
      '18',
      '19',
      '20',
      '21',
      '22',
      '23',
      '24',
      '25',
      '26',
      '27',
      '28',
      '29',
      '30',
      '31',
      '32',
      '33',
    ],
    kbli_section: 'C',
  },
  {
    id: 5,
    sector_name: 'Pengelolaan Air',
    sector_name_en: 'Water Collection and Supply',
    kbli_range: ['36'],
    kbli_section: 'E',
  },
  {
    id: 6,
    sector_name: 'Pengelolaan Air Limbah',
    sector_name_en: 'Sewerage',
    kbli_range: ['37'],
    kbli_section: 'E',
  },
  {
    id: 7,
    sector_name: 'Pengelolaan dan Daur Ulang Sampah',
    sector_name_en: 'Waste Management',
    kbli_range: ['38', '39'],
    kbli_section: 'E',
  },
  {
    id: 8,
    sector_name: 'Pengangkutan dan Pergudangan',
    sector_name_en: 'Transportation and Storage',
    kbli_range: ['49', '50', '51', '52', '53'],
    kbli_section: 'H',
  },
  {
    id: 9,
    sector_name: 'Kesenian, Hiburan, dan Rekreasi',
    sector_name_en: 'Arts, Entertainment and Recreation',
    kbli_range: ['90', '91', '92', '93'],
    kbli_section: 'R',
  },
  {
    id: 10,
    sector_name: 'Penyediaan Akomodasi dan Makan Minum',
    sector_name_en: 'Accommodation and Food Service',
    kbli_range: ['55', '56'],
    kbli_section: 'I',
  },
  {
    id: 11,
    sector_name: 'Pertanian, Kehutanan dan Perikanan',
    sector_name_en: 'Agriculture, Forestry and Fishing',
    kbli_range: ['01', '02', '03'],
    kbli_section: 'A',
  },
  {
    id: 12,
    sector_name: 'Aktivitas Penyewaan dan Ketenagakerjaan',
    sector_name_en: 'Rental, Employment Activities',
    kbli_range: ['77', '78', '79', '80', '81', '82'],
    kbli_section: 'N',
  },
  {
    id: 13,
    sector_name: 'Aktivitas Keuangan dan Asuransi',
    sector_name_en: 'Financial and Insurance',
    kbli_range: ['64', '65', '66'],
    kbli_section: 'K',
  },
  {
    id: 14,
    sector_name: 'Aktivitas Kesehatan Manusia',
    sector_name_en: 'Human Health and Social Work',
    kbli_range: ['86', '87', '88'],
    kbli_section: 'Q',
  },
  {
    id: 15,
    sector_name: 'Informasi dan Telekomunikasi',
    sector_name_en: 'Information and Communication',
    kbli_range: ['58', '59', '60', '61', '62', '63'],
    kbli_section: 'J',
  },
  {
    id: 16,
    sector_name: 'Pertambangan dan Penggalian',
    sector_name_en: 'Mining and Quarrying',
    kbli_range: ['05', '06', '07', '08', '09'],
    kbli_section: 'B',
    special_note:
      'Satu-satunya sektor yang membolehkan TKA sebagai Direktur Utama (S1 + 15 tahun pengalaman)',
  },
  {
    id: 17,
    sector_name: 'Pengadaan Listrik, Gas, Uap',
    sector_name_en: 'Electricity, Gas, Steam',
    kbli_range: ['35'],
    kbli_section: 'D',
  },
  {
    id: 18,
    sector_name: 'Perdagangan Besar dan Eceran',
    sector_name_en: 'Wholesale and Retail Trade',
    kbli_range: ['45', '46', '47'],
    kbli_section: 'G',
  },
  {
    id: 19,
    sector_name: 'Aktivitas Jasa Lainnya',
    sector_name_en: 'Other Service Activities',
    kbli_range: ['94', '95', '96'],
    kbli_section: 'S',
  },
  {
    id: 20,
    sector_name: 'Aktivitas Profesional, Ilmiah, dan Teknis',
    sector_name_en: 'Professional, Scientific and Technical',
    kbli_range: ['69', '70', '71', '72', '73', '74', '75'],
    kbli_section: 'M',
  },
];

const categoryColors: Record<string, string> = {
  director: 'bg-red-500/20 text-red-400 border-red-500/30',
  manager: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  supervisor: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  administrator: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  specialist: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  advisor: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  analyst: 'bg-green-500/20 text-green-400 border-green-500/30',
  safety: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
  intermediary: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  executive: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
};

const sectorIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  F: HardHat,
  L: Building,
  P: GraduationCap,
  C: Factory,
  E: Droplets,
  H: Truck,
  R: Music,
  I: Utensils,
  A: TreePine,
  N: Briefcase,
  K: Coins,
  Q: Stethoscope,
  J: Wifi,
  B: Pickaxe,
  D: Zap,
  G: Building2,
  S: Wrench,
  M: Cog,
};

export default function TkaJabatanPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState<AllowedSector | null>(null);
  const [activeTab, setActiveTab] = useState<'sectors' | 'forbidden'>('sectors');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');

  useEffect(() => {
    api.kbActivity.logView(
      'tka-jabatan-kbli',
      undefined,
      'TKA Jabatan & KBLI Explorer',
      'employment'
    );
  }, []);

  // Escape key to close detail panel
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && selectedSector) {
        setSelectedSector(null);
      }
    },
    [selectedSector]
  );

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const filteredSectors = allowedSectors.filter(
    (sector) =>
      sector.sector_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sector.sector_name_en.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sector.kbli_range.some((code) => code.includes(searchQuery))
  );

  const filteredPositions = forbiddenPositions.filter((pos) => {
    const matchesSearch =
      pos.name_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      pos.name_en.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = categoryFilter === 'all' || pos.category === categoryFilter;
    return matchesSearch && matchesCategory;
  });

  const categories = [...new Set(forbiddenPositions.map((p) => p.category))];

  return (
    <div className="min-h-screen bg-[var(--background)]">
      {/* Header */}
      <div className="border-b border-[var(--border)] bg-[var(--background-secondary)]">
        <div className="mx-auto max-w-7xl px-4 py-6">
          <button
            onClick={() => router.push('/')}
            className="mb-4 flex items-center gap-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Kembali ke Knowledge Base
          </button>
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-purple-600">
              <Users className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-[var(--foreground)]">
                TKA Jabatan &amp; KBLI Explorer
              </h1>
              <p className="text-sm text-[var(--foreground-muted)]">
                Kepmenaker 228/2019 &amp; 349/2019 - Regulasi Tenaga Kerja Asing
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-6">
        {/* Stats Cards */}
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/20">
                <Building2 className="h-5 w-5 text-green-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[var(--foreground)]">22</p>
                <p className="text-xs text-[var(--foreground-muted)]">Kategori KBLI 2025</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-500/20">
                <ShieldAlert className="h-5 w-5 text-red-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[var(--foreground)]">19</p>
                <p className="text-xs text-[var(--foreground-muted)]">Jabatan Dilarang</p>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/20">
                <Briefcase className="h-5 w-5 text-blue-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-[var(--foreground)]">1.562</p>
                <p className="text-xs text-[var(--foreground-muted)]">Kode KBLI 2025</p>
              </div>
            </div>
          </div>
        </div>

        {/* Search and Tabs */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--foreground-muted)]" />
            <input
              type="text"
              placeholder="Cari sektor, KBLI, atau jabatan..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] py-2 pl-10 pr-4 text-sm text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:border-[var(--accent)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('sectors')}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'sectors'
                  ? 'bg-[var(--accent)] text-white'
                  : 'bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
              }`}
            >
              <CheckCircle2 className="mr-2 inline h-4 w-4" />
              Sektor Diizinkan
            </button>
            <button
              onClick={() => setActiveTab('forbidden')}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === 'forbidden'
                  ? 'bg-red-500 text-white'
                  : 'bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
              }`}
            >
              <XCircle className="mr-2 inline h-4 w-4" />
              Jabatan Dilarang
            </button>
          </div>
        </div>

        {/* Content */}
        {activeTab === 'sectors' ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredSectors.map((sector) => {
              const IconComponent = sectorIcons[sector.kbli_section] || Building2;
              return (
                <button
                  key={sector.id}
                  onClick={() => setSelectedSector(sector)}
                  className="group rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4 text-left transition-all hover:border-[var(--accent)] hover:shadow-lg hover:shadow-[var(--accent)]/10"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20">
                      <IconComponent className="h-5 w-5 text-[var(--accent)]" />
                    </div>
                    <span className="rounded-full bg-[var(--accent)]/20 px-2 py-0.5 text-xs font-medium text-[var(--accent)]">
                      {sector.kbli_section}
                    </span>
                  </div>
                  <h3 className="mt-3 font-semibold text-[var(--foreground)] group-hover:text-[var(--accent)]">
                    {sector.sector_name}
                  </h3>
                  <p className="mt-1 text-xs text-[var(--foreground-muted)]">
                    {sector.sector_name_en}
                  </p>
                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-xs text-[var(--foreground-muted)]">
                      KBLI: {sector.kbli_range.join(', ')}
                    </span>
                    <ChevronRight className="h-4 w-4 text-[var(--foreground-muted)] group-hover:text-[var(--accent)]" />
                  </div>
                  {sector.allowed_positions_count && (
                    <div className="mt-2 rounded-md bg-green-500/10 px-2 py-1 text-xs text-green-400">
                      {sector.allowed_positions_count} posisi diizinkan
                    </div>
                  )}
                  {sector.special_note && (
                    <div className="mt-2 rounded-md bg-amber-500/10 px-2 py-1 text-xs text-amber-400">
                      {sector.special_note}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        ) : (
          <div>
            <div className="mb-4 flex flex-wrap gap-2">
              <button
                onClick={() => setCategoryFilter('all')}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  categoryFilter === 'all'
                    ? 'bg-[var(--accent)] text-white'
                    : 'bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
                }`}
              >
                Semua ({forbiddenPositions.length})
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat)}
                  className={`rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors ${
                    categoryFilter === cat
                      ? 'bg-[var(--accent)] text-white'
                      : 'bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]'
                  }`}
                >
                  {cat} ({forbiddenPositions.filter((p) => p.category === cat).length})
                </button>
              ))}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filteredPositions.map((position) => (
                <div
                  key={position.id}
                  className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-500/20">
                      <XCircle className="h-4 w-4 text-red-400" />
                    </div>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${
                        categoryColors[position.category] ||
                        'bg-gray-500/20 text-gray-400 border-gray-500/30'
                      }`}
                    >
                      {position.category}
                    </span>
                  </div>
                  <h3 className="mt-3 font-semibold text-[var(--foreground)]">
                    {position.name_id}
                  </h3>
                  <p className="mt-1 text-xs text-[var(--foreground-muted)]">{position.name_en}</p>
                  {position.risk_level === 'conditional' && (
                    <div className="mt-2 rounded-md bg-amber-500/10 px-2 py-1 text-xs text-amber-400">
                      Kondisional - tergantung fungsi
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Legal Basis */}
        <div className="mt-8 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="mb-3 font-semibold text-[var(--foreground)]">Dasar Hukum</h3>
          <div className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
            <div className="rounded-lg bg-[var(--background)] p-3">
              <p className="font-medium text-[var(--foreground)]">Kepmenaker 228/2019</p>
              <p className="text-xs text-[var(--foreground-muted)]">20 Sektor yang diizinkan TKA</p>
            </div>
            <div className="rounded-lg bg-[var(--background)] p-3">
              <p className="font-medium text-[var(--foreground)]">Kepmenaker 349/2019</p>
              <p className="text-xs text-[var(--foreground-muted)]">19 Jabatan yang dilarang TKA</p>
            </div>
            <div className="rounded-lg bg-[var(--background)] p-3">
              <p className="font-medium text-[var(--foreground)]">PP 34/2021</p>
              <p className="text-xs text-[var(--foreground-muted)]">
                Penggunaan Tenaga Kerja Asing
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Sector Detail Slide-out Panel */}
      {selectedSector && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSelectedSector(null)} />
          <div className="relative w-full max-w-md overflow-y-auto bg-[var(--background)] shadow-xl">
            <div className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--background-secondary)] p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold text-[var(--foreground)]">
                  {selectedSector.sector_name}
                </h2>
                <button
                  onClick={() => setSelectedSector(null)}
                  className="rounded-lg p-2 hover:bg-[var(--background)]"
                  aria-label="Chiudi dettaglio settore"
                >
                  <X className="h-5 w-5 text-[var(--foreground-muted)]" />
                </button>
              </div>
              <p className="mt-1 text-sm text-[var(--foreground-muted)]">
                {selectedSector.sector_name_en}
              </p>
            </div>

            <div className="p-4">
              <div className="mb-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-[var(--foreground-muted)]">Seksi KBLI</p>
                    <p className="text-lg font-bold text-[var(--accent)]">
                      {selectedSector.kbli_section}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--foreground-muted)]">Kode KBLI</p>
                    <p className="font-semibold text-[var(--foreground)]">
                      {selectedSector.kbli_range.join(', ')}
                    </p>
                  </div>
                </div>
                {selectedSector.allowed_positions_count && (
                  <div className="mt-3 rounded-lg bg-green-500/10 p-3">
                    <p className="text-sm font-medium text-green-400">
                      {selectedSector.allowed_positions_count} posisi diizinkan untuk TKA
                    </p>
                  </div>
                )}
                {selectedSector.special_note && (
                  <div className="mt-3 rounded-lg bg-amber-500/10 p-3">
                    <p className="text-sm text-amber-400">{selectedSector.special_note}</p>
                  </div>
                )}
              </div>

              {selectedSector.example_positions && (
                <div className="mb-4">
                  <h3 className="mb-2 text-sm font-semibold text-[var(--foreground)]">
                    Contoh Jabatan Diizinkan
                  </h3>
                  <div className="space-y-2">
                    {selectedSector.example_positions.map((pos, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-2 rounded-lg bg-[var(--background-secondary)] p-3"
                      >
                        <CheckCircle2 className="h-4 w-4 text-green-400" />
                        <span className="text-sm text-[var(--foreground)]">{pos}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <h3 className="mb-2 text-sm font-semibold text-[var(--foreground)]">
                  Jabatan Tetap Dilarang (Universal)
                </h3>
                <p className="mb-3 text-xs text-[var(--foreground-muted)]">
                  Walaupun sektor ini diizinkan TKA, 19 jabatan berikut tetap dilarang:
                </p>
                <div className="space-y-1">
                  {forbiddenPositions.slice(0, 5).map((pos) => (
                    <div
                      key={pos.id}
                      className="flex items-center gap-2 rounded-lg bg-red-500/10 p-2"
                    >
                      <XCircle className="h-3 w-3 text-red-400" />
                      <span className="text-xs text-red-400">{pos.name_id}</span>
                    </div>
                  ))}
                  <p className="pt-2 text-xs text-[var(--foreground-muted)]">
                    ... e {forbiddenPositions.length - 5} jabatan lainnya
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
