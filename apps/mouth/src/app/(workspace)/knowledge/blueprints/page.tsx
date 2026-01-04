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
  ShoppingCart,
  Monitor,
  Radio,
  Wrench,
  Laptop,
  HardHat,
  Factory,
  Warehouse,
  Stethoscope,
  GraduationCap,
  Sparkles,
  Car,
  Anchor,
  Mountain,
  Satellite,
  Antenna,
  LayoutGrid,
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
  category: 'Hospitality' | 'Real Estate' | 'Services' | 'Technology' | 'Trade' | 'Construction' | 'Leasing';
  risk_level: 'Low' | 'Medium' | 'High';
  pma_allowed: boolean;
  pma_percentage: string;
  // Technical version (default)
  pdf_filename: string;
  pdf_url?: string;
  // Business version (optional - adds Bisnis button)
  pdf_bisnis_filename?: string;
  pdf_bisnis_url?: string;
  has_bisnis?: boolean;
  // Indonesian version (optional - adds ID button)
  pdf_id_teknis_url?: string;
  pdf_id_bisnis_url?: string;
  has_indonesian?: boolean;
  icon: 'hotel' | 'home' | 'tent' | 'building' | 'scissors' | 'code' | 'gamepad' | 'globe' | 'database' | 'server' | 'cart' | 'monitor' | 'radio' | 'wrench' | 'laptop' | 'hardhat' | 'factory' | 'warehouse' | 'health' | 'education' | 'entertainment' | 'car' | 'anchor' | 'mining' | 'satellite' | 'antenna' | 'grid';
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
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
    has_indonesian: true,
    has_bisnis: true,
    icon: 'home',
    description: 'Long-term and alternative accommodation investment guide.',
  },
  {
    id: 'kbli-68111',
    kbli_code: '68111',
    title: 'Real Estate Operations',
    title_id: 'Real Estat Yang Dimiliki Sendiri',
    category: 'Real Estate',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_68111_Real_Estate.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'building',
    description: 'Strategic guide for real estate operations and property management.',
  },
  {
    id: 'kbli-96121',
    kbli_code: '96121',
    title: 'Massage Services',
    title_id: 'Rumah Pijat',
    category: 'Services',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_96121_Massage_Services.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'scissors',
    description: 'Blueprint for massage and wellness services business.',
  },
  // SPA Services (from Anton folder)
  {
    id: 'kbli-96122',
    kbli_code: '96122',
    title: 'SPA Services',
    title_id: 'Aktivitas SPA',
    category: 'Services',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_96122_SPA.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'scissors',
    description: 'Blueprint for spa and wellness center business operations.',
  },
  // Technology Category (English only - no Indonesian versions)
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
    pdf_bisnis_url: '/blueprints/KBLI_62011_Videogame_Bisnis.pdf',
    has_bisnis: true,
    icon: 'gamepad',
    description: 'Guide for video game development business in Indonesia.',
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
    has_bisnis: true,
    icon: 'globe',
    description: 'Guide for e-commerce application development.',
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
    pdf_bisnis_url: '/blueprints/KBLI_62014_Blockchain_Bisnis.pdf',
    has_bisnis: true,
    icon: 'code',
    description: 'Guide for blockchain technology development.',
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
    has_bisnis: true,
    icon: 'code',
    description: 'Guide for software development and programming services.',
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
    pdf_bisnis_url: '/blueprints/KBLI_63111_Data_Processing_Bisnis.pdf',
    has_bisnis: true,
    icon: 'database',
    description: 'Guide for data processing and analytics services.',
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
    pdf_bisnis_url: '/blueprints/KBLI_63112_Hosting_Bisnis.pdf',
    has_bisnis: true,
    icon: 'server',
    description: 'Guide for web hosting and cloud services.',
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
    has_bisnis: true,
    icon: 'globe',
    description: 'Technical guide for non-commercial web portals and platforms.',
  },
  // ============================================================
  // Construction Category (from Ari folder)
  // ============================================================
  {
    id: 'kbli-41011',
    kbli_code: '41011',
    title: 'Construction Developer - Residential Housing',
    title_id: 'Pengembang Perumahan',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41011_Perumahan_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'hardhat',
    description: 'Guide for residential housing development and construction.',
  },
  {
    id: 'kbli-41012',
    kbli_code: '41012',
    title: 'Construction Developer - Apartments',
    title_id: 'Pengembang Apartemen',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41012_Apartemen_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'building',
    description: 'Guide for apartment complex development and construction.',
  },
  {
    id: 'kbli-41013',
    kbli_code: '41013',
    title: 'Construction Developer - Hotels',
    title_id: 'Pengembang Hotel',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41013_Hotel_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'hotel',
    description: 'Guide for hotel construction and development projects.',
  },
  {
    id: 'kbli-41014',
    kbli_code: '41014',
    title: 'Construction Developer - Office Buildings',
    title_id: 'Pengembang Gedung Perkantoran',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41014_Perkantoran_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'building',
    description: 'Guide for office building construction and development.',
  },
  {
    id: 'kbli-41015',
    kbli_code: '41015',
    title: 'Construction Developer - Shopping Centers',
    title_id: 'Pengembang Pusat Perbelanjaan',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41015_Mall_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'cart',
    description: 'Guide for shopping center and mall construction.',
  },
  {
    id: 'kbli-41016',
    kbli_code: '41016',
    title: 'Construction Developer - Industrial',
    title_id: 'Pengembang Gedung Industri',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41016_Industri_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'factory',
    description: 'Guide for industrial building construction.',
  },
  {
    id: 'kbli-41017',
    kbli_code: '41017',
    title: 'Construction Developer - Hospitals',
    title_id: 'Pengembang Rumah Sakit',
    category: 'Construction',
    risk_level: 'High',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41017_RS_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'health',
    description: 'Guide for hospital and healthcare facility construction.',
  },
  {
    id: 'kbli-41018',
    kbli_code: '41018',
    title: 'Construction Developer - Schools',
    title_id: 'Pengembang Gedung Pendidikan',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41018_Pendidikan_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'education',
    description: 'Guide for educational building construction.',
  },
  {
    id: 'kbli-41019',
    kbli_code: '41019',
    title: 'Construction Developer - Entertainment',
    title_id: 'Pengembang Gedung Hiburan',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41019_Hiburan_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'entertainment',
    description: 'Guide for entertainment venue construction.',
  },
  {
    id: 'kbli-41020',
    kbli_code: '41020',
    title: 'General Building Construction',
    title_id: 'Konstruksi Gedung Umum',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_41020_Gedung_Umum_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'hardhat',
    description: 'Guide for general building construction services.',
  },
  {
    id: 'kbli-42203',
    kbli_code: '42203',
    title: 'Telecom Tower Construction',
    title_id: 'Konstruksi Menara Telekomunikasi',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_42203_Menara_Telekom_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'antenna',
    description: 'Guide for telecommunications tower construction.',
  },
  {
    id: 'kbli-42913',
    kbli_code: '42913',
    title: 'Pier & Dock Construction',
    title_id: 'Konstruksi Dermaga',
    category: 'Construction',
    risk_level: 'High',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_42913_Dermaga_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'anchor',
    description: 'Guide for pier, dock and marine construction.',
  },
  {
    id: 'kbli-42916',
    kbli_code: '42916',
    title: 'Mining Infrastructure Construction',
    title_id: 'Konstruksi Infrastruktur Pertambangan',
    category: 'Construction',
    risk_level: 'High',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_42916_Tambang_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'mining',
    description: 'Guide for mining infrastructure construction.',
  },
  {
    id: 'kbli-42924',
    kbli_code: '42924',
    title: 'Satellite Station Construction',
    title_id: 'Konstruksi Stasiun Satelit',
    category: 'Construction',
    risk_level: 'High',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_42924_Satelit_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'satellite',
    description: 'Guide for satellite ground station construction.',
  },
  {
    id: 'kbli-42930',
    kbli_code: '42930',
    title: 'Power Plant Construction',
    title_id: 'Konstruksi Pembangkit Listrik',
    category: 'Construction',
    risk_level: 'High',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_42930_Listrik_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'grid',
    description: 'Guide for power generation facility construction.',
  },
  {
    id: 'kbli-43212',
    kbli_code: '43212',
    title: 'Electrical Installation',
    title_id: 'Instalasi Listrik',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_43212_Instalasi_Listrik_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'grid',
    description: 'Guide for electrical installation services.',
  },
  {
    id: 'kbli-43903',
    kbli_code: '43903',
    title: 'Interior Fit-Out',
    title_id: 'Interior Fit-Out',
    category: 'Construction',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_43903_Interior_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'home',
    description: 'Guide for interior fit-out and finishing services.',
  },
  {
    id: 'kbli-43909',
    kbli_code: '43909',
    title: 'General Contractor',
    title_id: 'Kontraktor Umum',
    category: 'Construction',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_43909_Kontraktor_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'hardhat',
    description: 'Guide for general contracting services.',
  },
  // ============================================================
  // Additional Real Estate KBLIs (from Anton folder)
  // ============================================================
  {
    id: 'kbli-68112',
    kbli_code: '68112',
    title: 'Real Estate - Property Sale',
    title_id: 'Real Estat Penjualan Properti',
    category: 'Real Estate',
    risk_level: 'Medium',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_68112_RE_Penjualan_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'building',
    description: 'Guide for property sales and real estate transactions.',
  },
  {
    id: 'kbli-68120',
    kbli_code: '68120',
    title: 'Real Estate - Rental Services',
    title_id: 'Real Estat Persewaan',
    category: 'Real Estate',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_68120_RE_Sewa_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'building',
    description: 'Guide for property rental and leasing services.',
  },
  {
    id: 'kbli-68200',
    kbli_code: '68200',
    title: 'Property Management',
    title_id: 'Pengelolaan Real Estat',
    category: 'Real Estate',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_68200_Properti_Mgmt_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'building',
    description: 'Guide for property management services.',
  },
  {
    id: 'kbli-68130',
    kbli_code: '68130',
    title: 'Industrial Zone Management',
    title_id: 'Kawasan Industri',
    category: 'Real Estate',
    risk_level: 'High',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_68130_Kawasan_Industri_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'factory',
    description: 'Guide for industrial zone development and management.',
  },
  // ============================================================
  // Leasing Category (from Anton folder)
  // ============================================================
  {
    id: 'kbli-77100',
    kbli_code: '77100',
    title: 'Motor Vehicle Rental',
    title_id: 'Sewa Kendaraan Bermotor',
    category: 'Leasing',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_77100_Sewa_Kendaraan_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'car',
    description: 'Guide for motor vehicle rental and leasing business.',
  },
  {
    id: 'kbli-77292',
    kbli_code: '77292',
    title: 'Equipment Rental - Hospitality',
    title_id: 'Sewa Peralatan Perhotelan',
    category: 'Leasing',
    risk_level: 'Low',
    pma_allowed: true,
    pma_percentage: '100%',
    pdf_filename: 'KBLI_77292_Sewa_Peralatan_Teknis.pdf',
    has_indonesian: true,
    has_bisnis: true,
    icon: 'warehouse',
    description: 'Guide for hospitality equipment rental services.',
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
    case 'Construction':
      return 'from-yellow-500/20 to-amber-500/20 border-yellow-500/30';
    case 'Leasing':
      return 'from-indigo-500/20 to-violet-500/20 border-indigo-500/30';
    case 'Trade':
      return 'from-lime-500/20 to-green-500/20 border-lime-500/30';
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
    case 'hardhat':
      return HardHat;
    case 'factory':
      return Factory;
    case 'warehouse':
      return Warehouse;
    case 'health':
      return Stethoscope;
    case 'education':
      return GraduationCap;
    case 'entertainment':
      return Sparkles;
    case 'car':
      return Car;
    case 'anchor':
      return Anchor;
    case 'mining':
      return Mountain;
    case 'satellite':
      return Satellite;
    case 'antenna':
      return Antenna;
    case 'grid':
      return LayoutGrid;
    case 'cart':
      return ShoppingCart;
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
  const [showIndonesian, setShowIndonesian] = useState(false);
  const [showBisnis, setShowBisnis] = useState(false);
  const IconComponent = getIcon(blueprint.icon);

  const handleDownload = () => {
    // Determine which PDF to download based on toggles
    let pdfUrl = blueprint.pdf_url;
    let pdfFilename = blueprint.pdf_filename;

    if (showIndonesian && blueprint.has_indonesian) {
      // Indonesian version
      if (showBisnis && blueprint.has_bisnis && blueprint.pdf_id_bisnis_url) {
        pdfUrl = blueprint.pdf_id_bisnis_url;
        pdfFilename = blueprint.pdf_bisnis_filename || blueprint.pdf_filename;
      } else if (blueprint.pdf_id_teknis_url) {
        pdfUrl = blueprint.pdf_id_teknis_url;
      }
    } else if (showBisnis && blueprint.has_bisnis && blueprint.pdf_bisnis_url) {
      // English Business version
      pdfUrl = blueprint.pdf_bisnis_url;
      pdfFilename = blueprint.pdf_bisnis_filename || blueprint.pdf_filename;
    }

    if (pdfUrl) {
      const link = document.createElement('a');
      link.href = pdfUrl;
      link.download = pdfFilename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      // Fallback to Google Drive folder
      const driveFolder = 'https://drive.google.com/drive/folders/1DOBzlToHhYrq_qZb5hAVdTsBOKBCCCti';
      window.open(driveFolder, '_blank');
    }
  };

  // Build download label
  const getDownloadLabel = () => {
    const parts = [];
    if (showIndonesian && blueprint.has_indonesian) parts.push('ID');
    if (showBisnis && blueprint.has_bisnis) parts.push('Bisnis');
    else if (blueprint.has_bisnis) parts.push('Teknis');
    return parts.length > 0 ? parts.join(' ') : 'PDF';
  };

  return (
    <div
      className={`
        group relative overflow-hidden rounded-xl border cursor-pointer
        bg-gradient-to-br ${getCategoryColor(blueprint.category)}
        hover:scale-[1.02] hover:shadow-lg hover:shadow-[var(--accent)]/10
        transition-all duration-300 ease-out
      `}
    >
      {/* Top badges row - 50% smaller */}
      <div className="absolute top-1.5 left-1.5 right-1.5 z-10 flex items-center gap-1">
        {/* Indonesian Toggle Button */}
        {blueprint.has_indonesian && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowIndonesian(!showIndonesian);
            }}
            className={`
              flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[8px] font-bold
              border transition-all duration-200
              ${showIndonesian
                ? 'bg-red-600 text-white border-red-600 shadow-sm'
                : 'bg-white text-red-600 border-red-300 hover:bg-red-50'
              }
            `}
            title={showIndonesian ? 'Viewing Indonesian' : 'Switch to Indonesian'}
          >
            <span className="text-[8px]">🇮🇩</span>
            ID
          </button>
        )}

        {/* Bisnis Toggle Button */}
        {blueprint.has_bisnis && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowBisnis(!showBisnis);
            }}
            className={`
              flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[8px] font-bold
              border transition-all duration-200
              ${showBisnis
                ? 'bg-blue-600 text-white border-blue-600 shadow-sm'
                : 'bg-white text-blue-600 border-blue-300 hover:bg-blue-50'
              }
            `}
            title={showBisnis ? 'Viewing Business guide' : 'Switch to Business guide'}
          >
            {showBisnis ? 'Bisnis' : 'Teknis'}
          </button>
        )}

        {/* PMA Badge */}
        {blueprint.pma_allowed && (
          <div className="flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-[8px] font-semibold shadow-sm ml-auto">
            <Shield className="w-2 h-2" />
            {blueprint.pma_percentage}
          </div>
        )}
      </div>

      {/* Card Content - 50% smaller */}
      <div className="p-2 pt-7">
        {/* KBLI Code - Compact Display */}
        <div className="flex items-center gap-1.5 mb-1.5">
          <div className="w-6 h-6 rounded bg-[var(--background)]/60 flex items-center justify-center">
            <IconComponent className="w-3 h-3 text-[var(--accent)]" />
          </div>
          <div>
            <span className="text-sm font-black text-[var(--foreground)] tracking-tight">
              {blueprint.kbli_code}
            </span>
            <div className="flex items-center gap-1 mt-0.5">
              <span className={`px-1 py-0 text-[8px] font-medium rounded-full border ${getRiskColor(blueprint.risk_level)}`}>
                {blueprint.risk_level}
              </span>
            </div>
          </div>
        </div>

        {/* Title - Compact */}
        <div className="mb-1.5">
          <h3 className="text-xs font-semibold text-[var(--foreground)] mb-0 group-hover:text-[var(--accent)] transition-colors line-clamp-1">
            {blueprint.title}
          </h3>
          <p className="text-[10px] text-[var(--foreground-muted)] line-clamp-1">{blueprint.title_id}</p>
        </div>

        {/* Description - Compact */}
        <p className="text-[10px] text-[var(--foreground-secondary)] mb-2 line-clamp-2 leading-tight">
          {blueprint.description}
        </p>

        {/* Download Button - Compact */}
        <div className="flex items-center justify-between pt-1.5 border-t border-[var(--border)]">
          <span className="text-[8px] text-[var(--foreground-muted)]">{blueprint.category}</span>
          <Button
            onClick={handleDownload}
            variant="outline"
            size="sm"
            className="gap-1 text-[10px] px-1.5 py-0.5 h-5 bg-[var(--background)]/60 hover:bg-[var(--accent)] hover:text-white transition-all"
          >
            <Download className="w-2.5 h-2.5" />
            {getDownloadLabel()}
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

  const categories = ['Hospitality', 'Real Estate', 'Services', 'Technology', 'Construction', 'Leasing'];

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

      {/* Blueprint Cards - 4 columns for compact cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
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
