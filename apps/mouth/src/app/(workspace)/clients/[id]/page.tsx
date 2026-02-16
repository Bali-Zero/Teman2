'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  MessageCircle,
  MapPin,
  Calendar,
  FileText,
  DollarSign,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Building2,
  Globe,
  CreditCard,
  Users,
  FolderOpen,
  Bell,
  ExternalLink,
  Plus,
  Trash2,
  Edit2,
  AlertCircle,
  Send,
  X,
  Save,
  Upload,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { fileToBase64 } from '@/lib/utils';
import type {
  ClientProfile,
  FamilyMember,
  ClientDocument,
  ExpiryAlert,
  Practice,
  Interaction,
  Client,
  DocumentCategory,
  DocumentCategoryType,
  ClientCompanyLink,
} from '@/lib/api/crm/crm.types';
import { COMMON_NATIONALITIES, CLIENT_STATUSES } from '@/lib/api/crm/crm.types';
import { cropToSquare } from '@/lib/utils/imageResize';
import { DriveFolderStructure } from '@/components/crm/DriveFolderStructure';
import { FolderFilesBrowser } from '@/components/crm/FolderFilesBrowser';

const STANDARD_FOLDERS: Record<string, { label: string; icon: string }> = {
  '00_Profile': { label: 'Profile', icon: '👤' },
  '01_Immigration': { label: 'Immigration', icon: '🛂' },
  '02_Company': { label: 'Company', icon: '🏢' },
  '03_Tax': { label: 'Tax', icon: '💰' },
  '04_Family': { label: 'Family', icon: '👨‍👩‍👧‍👦' },
  '99_Misc': { label: 'Misc', icon: '📁' },
};

// Status badge colors
const STATUS_COLORS: Record<string, string> = {
  inquiry: 'bg-blue-500/20 text-blue-400',
  quotation_sent: 'bg-yellow-500/20 text-yellow-400',
  payment_pending: 'bg-orange-500/20 text-orange-400',
  in_progress: 'bg-purple-500/20 text-purple-400',
  waiting_documents: 'bg-pink-500/20 text-pink-400',
  submitted_to_gov: 'bg-indigo-500/20 text-indigo-400',
  approved: 'bg-emerald-500/20 text-emerald-400',
  completed: 'bg-green-500/20 text-green-400',
};

// Alert color styles
const ALERT_COLORS: Record<string, string> = {
  green: 'bg-green-500/20 text-green-400 border-green-500/30',
  yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  red: 'bg-red-500/20 text-red-400 border-red-500/30',
  expired: 'bg-red-600/30 text-red-300 border-red-600/50',
};

// Document category colors
const CATEGORY_COLORS: Record<string, string> = {
  immigration: 'bg-blue-500/20 text-blue-400',
  pma: 'bg-purple-500/20 text-purple-400',
  tax: 'bg-emerald-500/20 text-emerald-400',
  personal: 'bg-orange-500/20 text-orange-400',
  other: 'bg-gray-500/20 text-gray-400',
};

// Country codes with flags for phone input
const COUNTRY_CODES = [
  { code: '+62', country: 'Indonesia', flag: '🇮🇩' },
  { code: '+82', country: 'South Korea', flag: '🇰🇷' },
  { code: '+39', country: 'Italy', flag: '🇮🇹' },
  { code: '+1', country: 'USA/Canada', flag: '🇺🇸' },
  { code: '+44', country: 'UK', flag: '🇬🇧' },
  { code: '+61', country: 'Australia', flag: '🇦🇺' },
  { code: '+49', country: 'Germany', flag: '🇩🇪' },
  { code: '+33', country: 'France', flag: '🇫🇷' },
  { code: '+31', country: 'Netherlands', flag: '🇳🇱' },
  { code: '+34', country: 'Spain', flag: '🇪🇸' },
  { code: '+7', country: 'Russia', flag: '🇷🇺' },
  { code: '+380', country: 'Ukraine', flag: '🇺🇦' },
  { code: '+81', country: 'Japan', flag: '🇯🇵' },
  { code: '+86', country: 'China', flag: '🇨🇳' },
  { code: '+91', country: 'India', flag: '🇮🇳' },
  { code: '+55', country: 'Brazil', flag: '🇧🇷' },
  { code: '+52', country: 'Mexico', flag: '🇲🇽' },
  { code: '+54', country: 'Argentina', flag: '🇦🇷' },
  { code: '+27', country: 'South Africa', flag: '🇿🇦' },
  { code: '+64', country: 'New Zealand', flag: '🇳🇿' },
  { code: '+353', country: 'Ireland', flag: '🇮🇪' },
  { code: '+351', country: 'Portugal', flag: '🇵🇹' },
  { code: '+48', country: 'Poland', flag: '🇵🇱' },
  { code: '+90', country: 'Turkey', flag: '🇹🇷' },
  { code: '+66', country: 'Thailand', flag: '🇹🇭' },
  { code: '+84', country: 'Vietnam', flag: '🇻🇳' },
  { code: '+63', country: 'Philippines', flag: '🇵🇭' },
  { code: '+60', country: 'Malaysia', flag: '🇲🇾' },
  { code: '+65', country: 'Singapore', flag: '🇸🇬' },
];

// Extract country code from phone number
const extractCountryCode = (phone: string): { countryCode: string; localNumber: string } => {
  if (!phone) return { countryCode: '+62', localNumber: '' };

  // If starts with +, try to match
  if (phone.startsWith('+')) {
    for (const { code } of COUNTRY_CODES.sort((a, b) => b.code.length - a.code.length)) {
      if (phone.startsWith(code)) {
        return { countryCode: code, localNumber: phone.slice(code.length).trim() };
      }
    }
  }

  // Try to detect from raw digits
  const digits = phone.replace(/\D/g, '');
  for (const { code } of COUNTRY_CODES.sort((a, b) => b.code.length - a.code.length)) {
    const codeDigits = code.replace('+', '');
    if (digits.startsWith(codeDigits) && digits.length >= codeDigits.length + 6) {
      return { countryCode: code, localNumber: digits.slice(codeDigits.length) };
    }
  }

  return { countryCode: '+62', localNumber: phone };
};

// ============================================
// GOOGLE DRIVE URL HELPERS
// ============================================

// Extract file ID from Google Drive URL
const extractDriveFileId = (url: string): string | null => {
  if (!url) return null;
  // Format: /file/d/{FILE_ID}/
  const match1 = url.match(/\/d\/([^/]+)/);
  if (match1) return match1[1];
  // Format: ?id={FILE_ID}
  const match2 = url.match(/[?&]id=([^&]+)/);
  if (match2) return match2[1];
  return null;
};

// Get proxy thumbnail URL for displaying document without Google branding
const getDriveProxyUrl = (url: string, type: 'thumbnail' | 'full' = 'thumbnail'): string | null => {
  const fileId = extractDriveFileId(url);
  if (fileId) {
    return type === 'thumbnail'
      ? `/api/documents/thumbnail/${fileId}`
      : `/api/documents/proxy/${fileId}`;
  }
  return null;
};

// Map nationalities to flag emojis
const NATIONALITY_FLAGS: Record<string, string> = {
  Italian: '🇮🇹',
  Italy: '🇮🇹',
  Russian: '🇷🇺',
  Russia: '🇷🇺',
  Ukrainian: '🇺🇦',
  Ukraine: '🇺🇦',
  American: '🇺🇸',
  USA: '🇺🇸',
  'United States': '🇺🇸',
  British: '🇬🇧',
  UK: '🇬🇧',
  'United Kingdom': '🇬🇧',
  Australian: '🇦🇺',
  Australia: '🇦🇺',
  German: '🇩🇪',
  Germany: '🇩🇪',
  French: '🇫🇷',
  France: '🇫🇷',
  Spanish: '🇪🇸',
  Spain: '🇪🇸',
  Dutch: '🇳🇱',
  Netherlands: '🇳🇱',
  Indonesian: '🇮🇩',
  Indonesia: '🇮🇩',
  Chinese: '🇨🇳',
  China: '🇨🇳',
  Japanese: '🇯🇵',
  Japan: '🇯🇵',
  Korean: '🇰🇷',
  Korea: '🇰🇷',
  'South Korea': '🇰🇷',
  Indian: '🇮🇳',
  India: '🇮🇳',
  Brazilian: '🇧🇷',
  Brazil: '🇧🇷',
  Canadian: '🇨🇦',
  Canada: '🇨🇦',
  Mexican: '🇲🇽',
  Mexico: '🇲🇽',
  Argentinian: '🇦🇷',
  Argentina: '🇦🇷',
  'South African': '🇿🇦',
  'South Africa': '🇿🇦',
  'New Zealander': '🇳🇿',
  'New Zealand': '🇳🇿',
  Irish: '🇮🇪',
  Ireland: '🇮🇪',
  Portuguese: '🇵🇹',
  Portugal: '🇵🇹',
  Polish: '🇵🇱',
  Poland: '🇵🇱',
  Turkish: '🇹🇷',
  Turkey: '🇹🇷',
  Thai: '🇹🇭',
  Thailand: '🇹🇭',
  Vietnamese: '🇻🇳',
  Vietnam: '🇻🇳',
  Filipino: '🇵🇭',
  Philippines: '🇵🇭',
  Malaysian: '🇲🇾',
  Malaysia: '🇲🇾',
  Singaporean: '🇸🇬',
  Singapore: '🇸🇬',
};

// Get flag emoji from nationality
const getCountryFlag = (nationality: string | undefined): string | null => {
  if (!nationality) return null;
  return NATIONALITY_FLAGS[nationality] || null;
};

// Format phone number with country code detection
const formatPhoneNumber = (phone: string): string => {
  if (!phone) return '';

  // Remove all non-digit characters except leading +
  const hasPlus = phone.startsWith('+');
  const digits = phone.replace(/\D/g, '');

  // If already has +, just return formatted
  if (hasPlus) {
    return phone;
  }

  // Country codes sorted by length (longest first to match correctly)
  const countryCodes: { code: string; length: number }[] = [
    { code: '380', length: 3 }, // Ukraine
    { code: '62', length: 2 }, // Indonesia
    { code: '82', length: 2 }, // South Korea
    { code: '81', length: 2 }, // Japan
    { code: '86', length: 2 }, // China
    { code: '91', length: 2 }, // India
    { code: '44', length: 2 }, // UK
    { code: '49', length: 2 }, // Germany
    { code: '33', length: 2 }, // France
    { code: '39', length: 2 }, // Italy
    { code: '34', length: 2 }, // Spain
    { code: '31', length: 2 }, // Netherlands
    { code: '61', length: 2 }, // Australia
    { code: '55', length: 2 }, // Brazil
    { code: '52', length: 2 }, // Mexico
    { code: '65', length: 2 }, // Singapore
    { code: '66', length: 2 }, // Thailand
    { code: '63', length: 2 }, // Philippines
    { code: '60', length: 2 }, // Malaysia
    { code: '84', length: 2 }, // Vietnam
    { code: '7', length: 1 }, // Russia
    { code: '1', length: 1 }, // USA/Canada
  ];

  // Try to match country code
  for (const { code, length } of countryCodes) {
    if (digits.startsWith(code) && digits.length >= length + 8) {
      const rest = digits.slice(length);
      return `+${code} ${rest}`;
    }
  }

  // If no country code detected, return as-is
  return phone;
};

// Calculate passport validity color based on months until expiry
// Green: >14 months, Orange: 9-13 months, Red: <9 months
const getPassportValidityColor = (
  expiryDate: string | undefined
): { color: string; label: string; bgClass: string; textClass: string } => {
  if (!expiryDate)
    return {
      color: 'gray',
      label: 'No expiry',
      bgClass: 'bg-gray-500/20',
      textClass: 'text-gray-400',
    };

  const now = new Date();
  const expiry = new Date(expiryDate);
  const monthsUntilExpiry = (expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24 * 30);

  if (monthsUntilExpiry <= 0) {
    return { color: 'red', label: 'EXPIRED', bgClass: 'bg-red-600/30', textClass: 'text-red-300' };
  } else if (monthsUntilExpiry < 9) {
    return {
      color: 'red',
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: 'bg-red-500/20',
      textClass: 'text-red-400',
    };
  } else if (monthsUntilExpiry < 14) {
    return {
      color: 'orange',
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: 'bg-orange-500/20',
      textClass: 'text-orange-400',
    };
  } else {
    return {
      color: 'green',
      label: `${Math.floor(monthsUntilExpiry)} months`,
      bgClass: 'bg-green-500/20',
      textClass: 'text-green-400',
    };
  }
};

const INTERACTION_ICONS: Record<string, React.ReactNode> = {
  chat: <MessageCircle className="w-4 h-4" />,
  email: <Mail className="w-4 h-4" />,
  whatsapp: <MessageCircle className="w-4 h-4 text-green-500" />,
  call: <Phone className="w-4 h-4" />,
  meeting: <Calendar className="w-4 h-4" />,
  note: <FileText className="w-4 h-4" />,
};

type TabType = 'overview' | 'family' | 'documents' | 'process' | 'timeline' | 'company' | 'tax';
type ModalType = 'none' | 'edit_client' | 'add_family' | 'add_document' | 'edit_document';

export default function ClientDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const clientId = Number(params.id);

  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [interactions, setInteractions] = useState<Interaction[]>([]);
  const [docCategories, setDocCategories] = useState<DocumentCategory[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [activeModal, setActiveModal] = useState<ModalType>('none');
  const [editingDocument, setEditingDocument] = useState<ClientDocument | null>(null);
  const [isMounted, setIsMounted] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [profileData, interactionsData, categoriesData] = await Promise.all([
        api.crm.getClientProfile(clientId),
        api.crm.getClientTimeline(clientId, 20),
        api.crm.getDocumentCategories().catch(() => []),
      ]);
      setProfile(profileData);
      setInteractions(interactionsData);
      setDocCategories(categoriesData);
    } catch (err) {
      logger.error('Failed to load client data:', {}, err as Error);
      setError('Failed to load client data');
      toast.error('Failed to load client data');
    } finally {
      setIsLoading(false);
    }
  };

  const refreshProfile = async () => {
    try {
      const profileData = await api.crm.getClientProfile(clientId);
      setProfile(profileData);
    } catch (err) {
      logger.error('Failed to refresh client data:', {}, err as Error);
    }
  };

  // Fix hydration mismatch: only render dates on client
  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (clientId) {
      loadData();
    }
  }, [clientId]);

  // Read tab from URL params and set active tab
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam && ['overview', 'family', 'documents', 'process', 'timeline'].includes(tabParam)) {
      setActiveTab(tabParam as TabType);
    }
  }, [searchParams]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    // Return placeholder during SSR to avoid hydration mismatch
    if (!isMounted) return '...';
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  };

  const formatTime = (dateStr: string) => {
    if (!dateStr) return '';
    // Return placeholder during SSR to avoid hydration mismatch
    if (!isMounted) return '...';
    return new Date(dateStr).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
        <AlertTriangle className="w-12 h-12 text-red-500" />
        <p className="text-[var(--foreground-muted)]">{error || 'Client not found'}</p>
        <Button variant="outline" onClick={() => router.push('/clients')}>
          Back to Clients
        </Button>
      </div>
    );
  }

  const { client, family_members, documents, expiry_alerts, practices, stats } = profile;

  // Group documents by category
  const documentsByCategory = documents.reduce(
    (acc, doc) => {
      const cat = doc.document_category || 'other';
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(doc);
      return acc;
    },
    {} as Record<string, ClientDocument[]>
  );

  // Calculate stats
  const activePractices = practices.filter(
    (p) => !['completed', 'cancelled', 'approved'].includes(p.status)
  );
  const completedPractices = practices.filter((p) => ['completed', 'approved'].includes(p.status));

  // Get country flag for fallback
  const countryFlag = getCountryFlag(client.nationality);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.back()}>
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div className="flex items-center gap-4 flex-1">
          {/* Avatar */}
          <div className="w-16 h-16 rounded-full bg-[var(--accent)]/20 flex items-center justify-center overflow-hidden">
            {client.avatar_url ? (
              <img
                src={client.avatar_url}
                alt={client.full_name}
                className="w-full h-full object-cover"
              />
            ) : countryFlag ? (
              <div className="w-full h-full rounded-full bg-[var(--background)] flex items-center justify-center text-4xl">
                {countryFlag}
              </div>
            ) : (
              <div className="w-full h-full rounded-full bg-white dark:bg-gray-300" />
            )}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--foreground)]">{client.full_name}</h1>
            <p className="text-sm text-[var(--foreground-muted)]">
              Client #{client.id} • {client.client_type || 'Individual'}
              {client.company_name && ` • ${client.company_name}`}
            </p>
          </div>
        </div>

        {/* Alert badges */}
        {(stats.expired_count > 0 || stats.red_alerts > 0 || stats.yellow_alerts > 0) && (
          <div className="flex gap-2">
            {stats.expired_count > 0 && (
              <span className="px-2 py-1 text-xs rounded-full bg-red-600/30 text-red-300 flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                {stats.expired_count} expired
              </span>
            )}
            {stats.red_alerts > 0 && (
              <span className="px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400 flex items-center gap-1">
                <Bell className="w-3 h-3" />
                {stats.red_alerts} urgent
              </span>
            )}
            {stats.yellow_alerts > 0 && (
              <span className="px-2 py-1 text-xs rounded-full bg-yellow-500/20 text-yellow-400 flex items-center gap-1">
                <Bell className="w-3 h-3" />
                {stats.yellow_alerts} soon
              </span>
            )}
          </div>
        )}

        {/* Quick Actions */}
        <div className="flex gap-2">
          {client.phone && (
            <>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 text-green-500 border-green-500/30 hover:bg-green-500/10"
                onClick={() => {
                  const phone = client.phone?.replace(/\D/g, '');
                  if (phone)
                    window.open(
                      `https://wa.me/${phone.startsWith('0') ? '62' + phone.slice(1) : phone}`,
                      '_blank'
                    );
                }}
              >
                <MessageCircle className="w-4 h-4" />
                WhatsApp
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="gap-2 text-sky-500 border-sky-500/30 hover:bg-sky-500/10"
                onClick={() => {
                  const phone = client.phone?.replace(/\D/g, '');
                  if (phone)
                    window.open(
                      `https://t.me/+${phone.startsWith('0') ? '62' + phone.slice(1) : phone}`,
                      '_blank'
                    );
                }}
              >
                <Send className="w-4 h-4" />
                Telegram
              </Button>
            </>
          )}
          {client.google_drive_folder_id && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2 text-blue-500 border-blue-500/30 hover:bg-blue-500/10"
              onClick={() => {
                // Scroll to Drive Folder section instead of opening Drive
                const element = document.querySelector('[data-drive-folder-section]');
                element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
              }}
            >
              <FolderOpen className="w-4 h-4" />
              View Documents
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-[var(--border)] pb-2 overflow-x-auto">
        {[
          { key: 'overview', label: 'Overview', icon: User },
          { key: 'family', label: `Family (${stats.family_count})`, icon: Users },
          { key: 'documents', label: `Documents (${stats.documents_count})`, icon: FileText },
          { key: 'process', label: `Process (${stats.practices_count})`, icon: FolderOpen },
          { key: 'timeline', label: 'Timeline', icon: Clock },
          { key: 'company', label: 'Company', icon: Building2 },
          { key: 'tax', label: 'Tax', icon: DollarSign },
        ].map(({ key, label, icon: Icon }) => (
          <Button
            key={key}
            variant={activeTab === key ? 'default' : 'ghost'}
            size="sm"
            className="gap-2 whitespace-nowrap"
            onClick={() => setActiveTab(key as TabType)}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <OverviewTab
          client={client}
          stats={stats}
          documents={documents}
          activePractices={activePractices}
          completedPractices={completedPractices}
          recentInteractions={interactions}
          formatDate={formatDate}
          formatCurrency={formatCurrency}
          formatTime={formatTime}
          router={router}
          clientId={clientId}
          onEditClick={() => setActiveModal('edit_client')}
          onAddNote={async (note: string) => {
            const user = await api.getProfile();
            await api.crm.createInteraction({
              client_id: clientId,
              interaction_type: 'note',
              summary: note,
              team_member: user.email,
            });
            const interactionsData = await api.crm.getClientTimeline(clientId, 20);
            setInteractions(interactionsData);
            toast.success('Note Added');
          }}
        />
      )}

      {activeTab === 'family' && (
        <FamilyTab
          clientId={clientId}
          familyMembers={family_members}
          formatDate={formatDate}
          onAddClick={() => setActiveModal('add_family')}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'documents' && (
        <DocumentsTab
          clientId={clientId}
          documentsByCategory={documentsByCategory}
          formatDate={formatDate}
          onAddClick={() => setActiveModal('add_document')}
          onEditClick={(doc) => {
            setEditingDocument(doc);
            setActiveModal('edit_document');
          }}
          onRefresh={refreshProfile}
        />
      )}

      {activeTab === 'process' && (
        <ProcessTab
          clientId={clientId}
          practices={practices}
          formatDate={formatDate}
          formatCurrency={formatCurrency}
          router={router}
        />
      )}

      {activeTab === 'timeline' && (
        <TimelineTab interactions={interactions} formatDate={formatDate} formatTime={formatTime} />
      )}

      {activeTab === 'company' && (
        <CompanyTab clientId={clientId} formatDate={formatDate} />
      )}

      {activeTab === 'tax' && (
        <TaxTab clientId={clientId} formatDate={formatDate} />
      )}

      {/* Modals */}
      {activeModal === 'edit_client' && profile && (
        <EditClientModal
          client={profile.client}
          onClose={() => setActiveModal('none')}
          onSave={refreshProfile}
        />
      )}

      {activeModal === 'add_family' && (
        <AddFamilyMemberModal
          clientId={clientId}
          onClose={() => setActiveModal('none')}
          onSave={refreshProfile}
        />
      )}

      {activeModal === 'add_document' && (
        <AddDocumentModal
          clientId={clientId}
          categories={docCategories}
          familyMembers={family_members}
          clientHasDriveFolder={!!client.google_drive_folder_id}
          onClose={() => setActiveModal('none')}
          onSave={refreshProfile}
        />
      )}

      {activeModal === 'edit_document' && editingDocument && (
        <EditDocumentModal
          clientId={clientId}
          document={editingDocument}
          categories={docCategories}
          familyMembers={family_members}
          onClose={() => {
            setActiveModal('none');
            setEditingDocument(null);
          }}
          onSave={refreshProfile}
        />
      )}
    </div>
  );
}

// ============================================
// OVERVIEW TAB
// ============================================
function OverviewTab({
  client,
  stats,
  documents,
  activePractices,
  completedPractices,
  recentInteractions,
  formatDate,
  formatCurrency,
  formatTime,
  router,
  clientId,
  onEditClick,
  onAddNote,
}: {
  client: ClientProfile['client'];
  stats: ClientProfile['stats'];
  documents: ClientDocument[];
  activePractices: ClientProfile['practices'];
  completedPractices: ClientProfile['practices'];
  recentInteractions: Interaction[];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  formatTime: (d: string) => string;
  router: ReturnType<typeof useRouter>;
  clientId: number;
  onEditClick: () => void;
  onAddNote: (note: string) => Promise<void>;
}) {
  const [quickNote, setQuickNote] = useState('');
  const [isAddingNote, setIsAddingNote] = useState(false);
  const [viewingFolder, setViewingFolder] = useState<string | null>(null);

  const handleAddNote = async () => {
    if (!quickNote.trim()) return;
    setIsAddingNote(true);
    try {
      await onAddNote(quickNote);
      setQuickNote('');
    } catch (err) {
      toast.error('Failed', { description: (err as Error).message });
    } finally {
      setIsAddingNote(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Row 1: Contact Info (2 cols) + Passport + Visa/Process */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Contact Info Card - DOUBLE WIDTH with all OCR data */}
        <div className="lg:col-span-2 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--foreground)]">Contact Info</h3>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                onClick={onEditClick}
              >
                <Edit2 className="w-3.5 h-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-[var(--foreground-muted)] hover:text-red-500"
                onClick={async () => {
                  if (
                    confirm(
                      `⚠️ Delete client "${client.full_name}"?\n\nThis will mark the client as inactive. All process and documents remain in the system.\n\nContinue?`
                    )
                  ) {
                    try {
                      const user = await api.getProfile();
                      await api.crm.deleteClient(client.id, user.email);
                      toast.success('Client deleted', { description: 'Marked as inactive' });
                      router.push('/clients');
                      router.refresh();
                    } catch (err) {
                      toast.error('Error deleting client', { description: (err as Error).message });
                    }
                  }
                }}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>

          {/* Two-column grid for contact + passport info */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Left column: Contact details */}
            <div className="space-y-2.5 text-xs">
              {client.assigned_to && (
                <div className="flex items-center gap-2">
                  {getTeamMemberAvatar(client.assigned_to) ? (
                    <img
                      src={getTeamMemberAvatar(client.assigned_to)}
                      alt={client.assigned_to.split('@')[0]}
                      className="w-6 h-6 rounded-full object-cover ring-1 ring-[var(--accent)]/30"
                    />
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
                      <User className="w-3 h-3 text-[var(--accent)]" />
                    </div>
                  )}
                  <span className="font-medium text-[var(--accent)]">
                    {client.assigned_to.split('@')[0]}
                  </span>
                </div>
              )}
              {client.email && (
                <div className="flex items-center gap-2">
                  <Mail className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <a
                    href={`mailto:${client.email}`}
                    className="text-[var(--foreground)] hover:underline truncate"
                  >
                    {client.email}
                  </a>
                </div>
              )}
              {client.phone && (
                <div className="flex items-center gap-2">
                  <Phone className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)]">
                    {formatPhoneNumber(client.phone)}
                  </span>
                </div>
              )}
              {client.nationality && (
                <div className="flex items-center gap-2">
                  <Globe className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)]">{client.nationality}</span>
                </div>
              )}
              {client.company_name && (
                <div className="flex items-center gap-2">
                  <Building2 className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)]">{client.company_name}</span>
                </div>
              )}
            </div>

            {/* Right column: Passport/OCR extracted data */}
            <div className="space-y-2.5 text-xs border-l border-[var(--border)] pl-4">
              <p className="text-[10px] uppercase tracking-wider text-[var(--foreground-muted)] font-semibold mb-2">
                Passport Data
              </p>
              {client.passport_number && (
                <div className="flex items-center gap-2">
                  <CreditCard className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)] font-mono">
                    {client.passport_number}
                  </span>
                </div>
              )}
              {client.passport_expiry && (
                <div className="flex items-center gap-2">
                  <Calendar className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)]">
                    Exp: {formatDate(client.passport_expiry)}
                  </span>
                </div>
              )}
              {client.date_of_birth && (
                <div className="flex items-center gap-2">
                  <Calendar className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)]">
                    DOB: {formatDate(client.date_of_birth)}
                  </span>
                </div>
              )}
              {client.gender && (
                <div className="flex items-center gap-2">
                  <User className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)]">
                    {client.gender === 'M' ? 'Male' : 'Female'}
                  </span>
                </div>
              )}
              {client.birthplace && (
                <div className="flex items-center gap-2">
                  <MapPin className="w-3.5 h-3.5 text-[var(--foreground-muted)]" />
                  <span className="text-[var(--foreground)]">{client.birthplace}</span>
                </div>
              )}
              {!client.passport_number &&
                !client.passport_expiry &&
                !client.date_of_birth &&
                !client.gender &&
                !client.birthplace && (
                  <p className="text-[var(--foreground-muted)] italic">
                    No passport data yet. Use OCR to extract.
                  </p>
                )}
            </div>
          </div>
        </div>

        {/* Column 3: Passport Card + Quick Note */}
        <div className="space-y-4">
          <PassportCard client={client} documents={documents} formatDate={formatDate} />

          {/* Quick Note */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-3">
            <h3 className="text-xs font-semibold text-[var(--foreground)] mb-2 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5" />
              Quick Note
            </h3>
            <textarea
              value={quickNote}
              onChange={(e) => setQuickNote(e.target.value)}
              placeholder="Add note..."
              rows={2}
              className="w-full px-2 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 resize-none text-xs"
            />
            <Button
              size="sm"
              onClick={handleAddNote}
              disabled={!quickNote.trim() || isAddingNote}
              className="w-full mt-2 h-7 text-xs"
            >
              {isAddingNote ? (
                <Loader2 className="w-3 h-3 animate-spin" />
              ) : (
                <>
                  <Plus className="w-3 h-3 mr-1" />
                  Add
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Column 4: Visa */}
        <div className="self-start">
          <ActualVisaCard
            client={client}
            documents={documents}
            activePractices={activePractices}
            formatDate={formatDate}
            formatCurrency={formatCurrency}
          />
        </div>

        {/* Column 5: Process */}
        <div className="self-start">
          <ActiveProcessCard
            activePractices={activePractices}
            formatDate={formatDate}
            router={router}
          />
        </div>
      </div>

      {/* Row 2: Stats Cards - 4 columns */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Users className="w-3.5 h-3.5 text-blue-500" />
            <span className="text-[10px] text-[var(--foreground-muted)]">Family</span>
          </div>
          <p className="text-xl font-bold text-[var(--foreground)]">{stats.family_count}</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <FileText className="w-3.5 h-3.5 text-purple-500" />
            <span className="text-[10px] text-[var(--foreground-muted)]">Docs</span>
          </div>
          <p className="text-xl font-bold text-[var(--foreground)]">{stats.documents_count}</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Clock className="w-3.5 h-3.5 text-orange-500" />
            <span className="text-[10px] text-[var(--foreground-muted)]">Active</span>
          </div>
          <p className="text-xl font-bold text-[var(--foreground)]">{activePractices.length}</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
            <span className="text-[10px] text-[var(--foreground-muted)]">Done</span>
          </div>
          <p className="text-xl font-bold text-[var(--foreground)]">{completedPractices.length}</p>
        </div>
      </div>

      {/* Row 3: Google Drive Folder Structure or Browser */}
      <div data-drive-folder-section>
        {viewingFolder ? (
          <FolderFilesBrowser
            clientId={clientId}
            clientName={client.full_name}
            folderName={viewingFolder}
            folderLabel={STANDARD_FOLDERS[viewingFolder]?.label || viewingFolder}
            onBack={() => setViewingFolder(null)}
          />
        ) : (
          <DriveFolderStructure
            clientId={clientId}
            clientName={client.full_name}
            existingFolderId={client.google_drive_folder_id}
            onFolderCreated={(folderId) => {
              // Refresh client data to update google_drive_folder_id
              router.refresh();
            }}
            onFolderLinked={(folderId) => {
              // Refresh client data to update google_drive_folder_id
              router.refresh();
            }}
            onViewFolder={(folderName) => {
              setViewingFolder(folderName);
            }}
          />
        )}
      </div>
    </div>
  );
}

// ============================================
// PASSPORT CARD COMPONENT (Compact rectangular - passport shape)
// ============================================
function PassportCard({
  client,
  documents,
  formatDate,
}: {
  client: ClientProfile['client'];
  documents: ClientDocument[];
  formatDate: (d: string) => string;
}) {
  const [isExtracting, setIsExtracting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Find passport document from documents
  const passportDoc = documents.find(
    (doc) =>
      doc.document_type?.toLowerCase().includes('passport') ||
      (doc.document_category === 'personal' && doc.document_type?.toLowerCase() === 'passport')
  );

  // Get passport validity color
  const passportValidity = getPassportValidityColor(client.passport_expiry);
  const passportImageUrl = passportDoc?.google_drive_file_url;

  // Convert Drive view URL to direct download URL
  const getDownloadUrl = (url: string) => {
    const fileId = extractDriveFileId(url);
    if (fileId) {
      return `https://drive.google.com/uc?export=download&id=${fileId}`;
    }
    return url;
  };

  const handleDownload = (e: React.MouseEvent) => {
    e.preventDefault();
    if (passportImageUrl) {
      const downloadUrl = getDownloadUrl(passportImageUrl);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `passport_${client.full_name?.replace(/\s+/g, '_') || 'document'}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  };

  // Enhanced OCR extraction with Gemini Vision
  const handleExtractData = async () => {
    if (!passportImageUrl || isExtracting) return;
    const fileId = extractDriveFileId(passportImageUrl);
    if (!fileId) {
      toast.error('Invalid document URL');
      return;
    }
    setIsExtracting(true);
    try {
      const response = (await api.post('/api/crm/clients/extract-passport-enhanced', {
        client_id: client.id,
        file_id: fileId,
      })) as {
        success: boolean;
        passport_number?: string;
        expiry_date?: string;
        full_name?: string;
        gender?: string;
        birthplace?: string;
        name_match?: boolean;
        message?: string;
      };
      if (response.success) {
        const details = [];
        if (response.passport_number) details.push(`Passport: ${response.passport_number}`);
        if (response.expiry_date) details.push(`Expiry: ${response.expiry_date}`);
        if (response.gender) details.push(`Gender: ${response.gender}`);
        if (response.birthplace) details.push(`Birthplace: ${response.birthplace}`);
        if (response.name_match === false) {
          toast.warning('Name mismatch', {
            description: 'Passport name differs from client record',
          });
        }
        toast.success('Passport data extracted!', { description: details.join(' | ') });
        window.location.reload();
      } else {
        toast.warning('OCR failed', {
          description: response.message || 'Could not extract passport data',
        });
      }
    } catch (err) {
      toast.error('Extraction failed', { description: (err as Error).message });
    } finally {
      setIsExtracting(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Invalid file type', { description: 'Please upload JPG, PNG, or PDF' });
      return;
    }

    // Validate file size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error('File too large', { description: 'Maximum file size is 10MB' });
      return;
    }

    setIsUploading(true);
    try {
      // Convert file to base64 using utility function
      const base64 = await fileToBase64(file);

      const response = (await api.post(`/api/crm/clients/${client.id}/documents/upload`, {
        file: base64,
        file_name: file.name,
        document_type: 'passport',
        mime_type: file.type,
      })) as {
        success: boolean;
        message?: string;
      };

      if (response.success) {
        toast.success('Passport uploaded successfully');
        window.location.reload();
      } else {
        toast.error('Upload failed', { description: response.message });
      }
    } catch (err) {
      toast.error('Upload failed', { description: (err as Error).message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async () => {
    if (!passportDoc) return;

    if (!confirm('Delete passport document? This will mark it as deleted.')) {
      return;
    }

    setIsDeleting(true);
    try {
      await api.request(`/api/crm/documents/${passportDoc.id}`, { method: 'DELETE' });
      toast.success('Passport deleted');
      window.location.reload();
    } catch (err) {
      toast.error('Delete failed', { description: (err as Error).message });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <h3 className="text-base font-semibold text-[var(--foreground)] flex items-center gap-2">
          <CreditCard className="w-5 h-5" />
          Passport
        </h3>
      </div>

      {/* Content */}
      <div className="p-4">
        {passportImageUrl ? (
          <div className="space-y-3">
            <button
              onClick={handleDownload}
              className="w-full block relative group cursor-pointer"
              title="Click to download passport"
            >
              <div className="aspect-[3/2] rounded-lg overflow-hidden border-2 border-dashed border-[var(--border)] bg-[var(--background)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getDriveProxyUrl(passportImageUrl) || passportImageUrl}
                  alt="Passport"
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    // Fallback to Google preview if proxy fails
                    (e.target as HTMLImageElement).src = passportImageUrl.replace(
                      '/view',
                      '/preview'
                    );
                  }}
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/40 transition-colors flex items-center justify-center">
                  <div className="flex items-center gap-2 bg-white/90 rounded-lg px-3 py-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Download className="w-4 h-4 text-gray-700" />
                    <span className="text-sm font-medium text-gray-700">Download</span>
                  </div>
                </div>
              </div>
            </button>
            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleExtractData}
                disabled={isExtracting}
              >
                {isExtracting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <FileText className="w-4 h-4 mr-2" />
                )}
                {isExtracting ? 'Extracting...' : 'Extract Data'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDelete}
                disabled={isDeleting}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                {isDeleting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4 mr-2" />
                )}
                {isDeleting ? 'Deleting...' : 'Delete'}
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-[var(--border)] flex flex-col items-center justify-center gap-2 bg-[var(--background)]/50">
              <CreditCard className="w-10 h-10 text-[var(--foreground-muted)] opacity-50" />
              <span className="text-sm text-[var(--foreground-muted)]">No passport</span>
            </div>

            {/* Upload Button */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,application/pdf"
              onChange={handleFileUpload}
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-3"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 mr-2" />
              )}
              {isUploading ? 'Uploading...' : 'Upload Passport'}
            </Button>
          </div>
        )}

        {/* Caption */}
        <p className="text-xs text-[var(--foreground-muted)] text-center mt-3">
          {passportImageUrl ? 'Passport document' : 'Upload passport (JPG, PNG, PDF - max 10MB)'}
        </p>
      </div>
    </div>
  );
}

// ============================================
// ACTUAL VISA CARD COMPONENT (Same size as Passport)
// ============================================
// Visa pricing listino (from visa_types table)
const VISA_PRICES: Record<string, { name: string; price: number }> = {
  c1: { name: 'C1 Tourist Visa', price: 2500000 },
  c1_visa: { name: 'C1 Tourist Visa', price: 2500000 },
  d12: { name: 'D12 Business Visa', price: 3500000 },
  voa: { name: 'Visa on Arrival', price: 500000 },
  e33e: { name: 'Retirement KITAS', price: 18000000 },
  e33g: { name: 'Digital Nomad KITAS', price: 8000000 },
  e28a: { name: 'Investor KITAS', price: 25000000 },
  kitas: { name: 'KITAS', price: 15000000 },
  kitap: { name: 'KITAP', price: 20000000 },
};

function ActualVisaCard({
  client,
  documents,
  activePractices,
  formatDate,
  formatCurrency,
}: {
  client: ClientProfile['client'];
  documents: ClientDocument[];
  activePractices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Find latest visa/KITAS document
  const visaDocs = documents.filter(
    (doc) =>
      doc.document_category === 'immigration' &&
      (doc.document_type?.toLowerCase().includes('visa') ||
        doc.document_type?.toLowerCase().includes('kitas') ||
        doc.document_type?.toLowerCase().includes('kitap') ||
        doc.document_type?.toLowerCase().includes('e-visa') ||
        doc.document_type?.toLowerCase().includes('evisa'))
  );

  const sortedVisaDocs = visaDocs.sort((a, b) => {
    if (!a.expiry_date) return 1;
    if (!b.expiry_date) return -1;
    return new Date(b.expiry_date).getTime() - new Date(a.expiry_date).getTime();
  });

  const latestVisa = sortedVisaDocs[0];

  // Find active visa process
  const visaProcess = activePractices.find(
    (p) =>
      p.practice_type_code?.toLowerCase().includes('visa') ||
      p.practice_type_code?.toLowerCase().includes('kitas') ||
      p.practice_type_code?.toLowerCase().includes('kitap') ||
      p.practice_type_name?.toLowerCase().includes('visa') ||
      p.practice_type_name?.toLowerCase().includes('kitas')
  );

  // Get price from listino
  const getVisaPrice = () => {
    const code = visaProcess?.practice_type_code?.toLowerCase() || '';
    return VISA_PRICES[code]?.price || null;
  };

  const visaPrice = getVisaPrice();

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Invalid file type', { description: 'Please upload JPG, PNG, or PDF' });
      return;
    }

    // Validate file size (max 10MB)
    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
      toast.error('File too large', { description: 'Maximum file size is 10MB' });
      return;
    }

    setIsUploading(true);
    try {
      // Convert file to base64 using utility function
      const base64 = await fileToBase64(file);

      const response = (await api.post(`/api/crm/clients/${client.id}/documents/upload`, {
        file: base64,
        file_name: file.name,
        document_type: 'visa',
        mime_type: file.type,
      })) as {
        success: boolean;
        message?: string;
      };

      if (response.success) {
        toast.success('Visa uploaded successfully');
        window.location.reload();
      } else {
        toast.error('Upload failed', { description: response.message });
      }
    } catch (err) {
      toast.error('Upload failed', { description: (err as Error).message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async () => {
    if (!latestVisa) return;

    if (!confirm('Delete visa document? This will mark it as deleted.')) {
      return;
    }

    setIsDeleting(true);
    try {
      await api.request(`/api/crm/documents/${latestVisa.id}`, { method: 'DELETE' });
      toast.success('Visa deleted');
      window.location.reload();
    } catch (err) {
      toast.error('Delete failed', { description: (err as Error).message });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <h3 className="text-base font-semibold text-[var(--foreground)] flex items-center gap-2">
          <FileText className="w-5 h-5" />
          Actual Visa
        </h3>
      </div>

      {/* Content */}
      <div className="p-4">
        {visaProcess ? (
          /* Visa in Process */
          <div className="aspect-[3/2] rounded-lg bg-blue-500/10 border-2 border-dashed border-blue-500/30 flex flex-col items-center justify-center gap-2">
            <Loader2 className="w-10 h-10 text-blue-400 animate-spin" />
            <p className="text-sm font-medium text-blue-400">Visa on process</p>
          </div>
        ) : latestVisa?.google_drive_file_url ? (
          <div className="space-y-3">
            <a
              href={latestVisa.google_drive_file_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block relative group"
            >
              <div className="aspect-[3/2] rounded-lg overflow-hidden border-2 border-dashed border-[var(--border)] bg-[var(--background)]">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={
                    getDriveProxyUrl(latestVisa.google_drive_file_url) ||
                    latestVisa.google_drive_file_url
                  }
                  alt="Visa"
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    if (latestVisa.google_drive_file_url) {
                      (e.target as HTMLImageElement).src = latestVisa.google_drive_file_url.replace(
                        '/view',
                        '/preview'
                      );
                    }
                  }}
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                  <ExternalLink className="w-5 h-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            </a>
            {/* Delete Button */}
            <Button
              variant="outline"
              size="sm"
              className="w-full text-red-600 hover:text-red-700 hover:bg-red-50"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Trash2 className="w-4 h-4 mr-2" />
              )}
              {isDeleting ? 'Deleting...' : 'Delete Visa'}
            </Button>
          </div>
        ) : (
          <div>
            <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-[var(--border)] flex flex-col items-center justify-center gap-2 bg-[var(--background)]/50">
              <FileText className="w-10 h-10 text-[var(--foreground-muted)] opacity-50" />
              <span className="text-sm text-[var(--foreground-muted)]">No visa</span>
            </div>

            {/* Upload Button */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/jpg,image/png,application/pdf"
              onChange={handleFileUpload}
              className="hidden"
            />
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-3"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 mr-2" />
              )}
              {isUploading ? 'Uploading...' : 'Upload Visa'}
            </Button>
          </div>
        )}

        {/* Caption */}
        <p className="text-xs text-[var(--foreground-muted)] text-center mt-3">
          {latestVisa?.google_drive_file_url
            ? 'Visa document'
            : 'Upload visa (JPG, PNG, PDF - max 10MB)'}
        </p>
      </div>
    </div>
  );
}

// ============================================
// ACTIVE PROCESS CARD COMPONENT (Same size as others)
// ============================================
function ActiveProcessCard({
  activePractices,
  formatDate,
  router,
}: {
  activePractices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  router: ReturnType<typeof useRouter>;
}) {
  const mainProcess = activePractices[0];

  // Calculate estimated issue date (+7 days from now as fallback)
  const getEstimatedDate = () => {
    return new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  };

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)]">
        <h3 className="text-base font-semibold text-[var(--foreground)] flex items-center gap-2">
          <FolderOpen className="w-5 h-5" />
          Process
        </h3>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 px-2 text-xs"
          onClick={() => router.push('/process/new')}
        >
          <Plus className="w-3 h-3 mr-1" />
          New
        </Button>
      </div>

      {/* Content */}
      <div className="p-4">
        {mainProcess ? (
          <div
            className="aspect-[3/2] rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 border-2 border-dashed border-blue-500/40 flex flex-col items-center justify-center cursor-pointer relative overflow-hidden group"
            onClick={() => router.push(`/process/${mainProcess.id}`)}
            style={{
              animation: 'pulse-glow 2s ease-in-out infinite',
            }}
          >
            {/* Pulsing overlay */}
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-purple-500/10 animate-pulse" />

            <div className="relative text-center z-10">
              <p className="text-sm font-semibold text-blue-400">
                {mainProcess.practice_type_name || mainProcess.practice_type_code?.toUpperCase()}
              </p>
              <p className="text-xs text-blue-300 mt-1">on process</p>
            </div>
          </div>
        ) : (
          <div className="aspect-[3/2] rounded-lg border-2 border-dashed border-[var(--border)] flex flex-col items-center justify-center gap-2 bg-[var(--background)]/50">
            <FolderOpen className="w-10 h-10 text-[var(--foreground-muted)] opacity-50" />
            <span className="text-sm text-[var(--foreground-muted)]">No process</span>
          </div>
        )}

        {/* Caption */}
        <p className="text-xs text-[var(--foreground-muted)] text-center mt-3">
          Click "New" to start
        </p>
      </div>

      {/* Pulsing animation keyframes */}
      <style jsx>{`
        @keyframes pulse-glow {
          0%,
          100% {
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.15);
          }
          50% {
            box-shadow: 0 0 25px rgba(59, 130, 246, 0.25);
          }
        }
      `}</style>
    </div>
  );
}

// ============================================
// FAMILY TAB
// ============================================
function FamilyTab({
  clientId,
  familyMembers,
  formatDate,
  onAddClick,
  onRefresh,
}: {
  clientId: number;
  familyMembers: FamilyMember[];
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onRefresh: () => void;
}) {
  const handleDelete = async (id: number, name: string) => {
    if (confirm(`Remove ${name} from family members?`)) {
      try {
        await api.crm.deleteFamilyMember(clientId, id);
        toast.success('Family member removed');
        onRefresh();
      } catch (err) {
        toast.error('Error', { description: (err as Error).message });
      }
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Family Members</h3>
        <Button size="sm" className="gap-2" onClick={onAddClick}>
          <Plus className="w-4 h-4" />
          Add Member
        </Button>
      </div>

      {familyMembers.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Users className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No family members added yet</p>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">
            Add spouse, children, or dependents
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {familyMembers.map((member) => (
            <div
              key={member.id}
              className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4 relative group"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
                    <User className="w-5 h-5 text-[var(--accent)]" />
                  </div>
                  <div>
                    <h4 className="font-medium text-[var(--foreground)]">{member.full_name}</h4>
                    <p className="text-xs text-[var(--foreground-muted)] capitalize">
                      {member.relationship}
                    </p>
                  </div>
                </div>
                <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-red-400 hover:text-red-500 hover:bg-red-500/10"
                    onClick={() => handleDelete(member.id, member.full_name)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                {member.nationality && (
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <span>{member.nationality}</span>
                  </div>
                )}
                {member.passport_number && (
                  <div className="flex items-center gap-2">
                    <CreditCard className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <span>
                      {member.passport_number}
                      {member.passport_expiry && (
                        <span
                          className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                            ALERT_COLORS[member.passport_alert || 'green']
                          }`}
                        >
                          {formatDate(member.passport_expiry)}
                        </span>
                      )}
                    </span>
                  </div>
                )}
                {member.current_visa_type && (
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-[var(--foreground-muted)]" />
                    <span>
                      {member.current_visa_type}
                      {member.visa_expiry && (
                        <span
                          className={`ml-2 px-1.5 py-0.5 rounded text-xs ${
                            ALERT_COLORS[member.visa_alert || 'green']
                          }`}
                        >
                          {formatDate(member.visa_expiry)}
                        </span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// DOCUMENTS TAB
// ============================================
function DocumentsTab({
  clientId,
  documentsByCategory,
  formatDate,
  onAddClick,
  onEditClick,
  onRefresh,
}: {
  clientId: number;
  documentsByCategory: Record<string, ClientDocument[]>;
  formatDate: (d: string) => string;
  onAddClick: () => void;
  onEditClick: (doc: ClientDocument) => void;
  onRefresh: () => void;
}) {
  const categoryNames: Record<string, string> = {
    immigration: 'Immigration Documents',
    pma: 'PT PMA Documents',
    tax: 'Tax Documents',
    personal: 'Personal Documents',
    other: 'Other Documents',
  };

  const categoryOrder = ['immigration', 'pma', 'tax', 'personal', 'other'];

  const handleDelete = async (docId: number, fileName: string) => {
    if (confirm(`Archive document "${fileName || 'Document'}"?`)) {
      try {
        await api.crm.deleteDocument(clientId, docId);
        toast.success('Document archived');
        onRefresh();
      } catch (err) {
        toast.error('Error', { description: (err as Error).message });
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">Documents</h3>
        <Button size="sm" className="gap-2" onClick={onAddClick}>
          <Plus className="w-4 h-4" />
          Add Document
        </Button>
      </div>

      {Object.keys(documentsByCategory).length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <FileText className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No documents uploaded yet</p>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">
            Upload passport, KITAS, PT PMA documents, and more
          </p>
        </div>
      ) : (
        categoryOrder.map((category) => {
          const docs = documentsByCategory[category];
          if (!docs || docs.length === 0) return null;

          return (
            <div key={category} className="space-y-3">
              <h4 className="font-medium text-[var(--foreground)] flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${CATEGORY_COLORS[category]}`}>
                  {categoryNames[category] || category}
                </span>
                <span className="text-[var(--foreground-muted)]">({docs.length})</span>
              </h4>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {docs.map((doc) => (
                  <div
                    key={doc.id}
                    className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden group"
                  >
                    {/* Document Preview - 3:2 aspect ratio like passport */}
                    {doc.google_drive_file_url && (
                      <a
                        href={doc.google_drive_file_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block relative"
                      >
                        <div
                          className={`aspect-[3/2] overflow-hidden border-b bg-[var(--background)] ${
                            doc.alert_color === 'expired' || doc.alert_color === 'red'
                              ? 'border-red-500/50'
                              : doc.alert_color === 'yellow'
                                ? 'border-yellow-500/50'
                                : 'border-[var(--border)]'
                          }`}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={
                              getDriveProxyUrl(doc.google_drive_file_url) ||
                              doc.google_drive_file_url
                            }
                            alt={doc.document_type}
                            className="w-full h-full object-contain"
                            onError={(e) => {
                              if (doc.google_drive_file_url) {
                                (e.target as HTMLImageElement).src =
                                  doc.google_drive_file_url.replace('/view', '/preview');
                              }
                            }}
                          />
                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                            <ExternalLink className="w-5 h-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                          </div>
                        </div>
                      </a>
                    )}

                    <div className="p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-[var(--foreground)]">
                          {doc.document_type.replace(/_/g, ' ')}
                        </span>
                        <div className="flex items-center gap-1">
                          {doc.google_drive_file_url && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7"
                              onClick={() => window.open(doc.google_drive_file_url!, '_blank')}
                            >
                              <ExternalLink className="w-3 h-3" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={() => onEditClick(doc)}
                          >
                            <Edit2 className="w-3 h-3" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7 text-red-400 hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-opacity"
                            onClick={() => handleDelete(doc.id, doc.file_name || doc.document_type)}
                          >
                            <Trash2 className="w-3 h-3" />
                          </Button>
                        </div>
                      </div>

                      {doc.file_name && (
                        <p
                          className="text-xs text-[var(--foreground-muted)] truncate mb-1"
                          title={doc.file_name}
                        >
                          {doc.file_name}
                        </p>
                      )}

                      {doc.expiry_date && (
                        <div
                          className={`text-xs px-2 py-1 rounded inline-flex items-center gap-1 ${
                            ALERT_COLORS[doc.alert_color || 'green']
                          }`}
                        >
                          <Calendar className="w-3 h-3" />
                          {doc.alert_color === 'expired'
                            ? 'Expired'
                            : `Expires: ${formatDate(doc.expiry_date)}`}
                        </div>
                      )}

                      {doc.family_member_name && (
                        <p className="text-xs text-[var(--foreground-muted)] mt-1">
                          → {doc.family_member_name}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

// ============================================
// PROCESS TAB
// ============================================
function ProcessTab({
  clientId,
  practices,
  formatDate,
  formatCurrency,
  router,
}: {
  clientId: number;
  practices: ClientProfile['practices'];
  formatDate: (d: string) => string;
  formatCurrency: (n: number) => string;
  router: ReturnType<typeof useRouter>;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-[var(--foreground)]">All Process</h3>
        <Button
          size="sm"
          className="gap-2"
          onClick={() => router.push(`/process/new?client_id=${clientId}`)}
        >
          <Plus className="w-4 h-4" />
          New Process
        </Button>
      </div>

      {practices.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <FolderOpen className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No process yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {practices.map((practice) => (
            <div
              key={practice.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-4 hover:border-[var(--accent)]/50 transition-colors group"
            >
              <div className="flex items-center justify-between mb-2">
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => router.push(`/process/${practice.id}`)}
                >
                  <span className="text-sm font-medium text-[var(--foreground)]">
                    {practice.practice_type_name}
                  </span>
                  <span className="text-xs text-[var(--foreground-muted)] ml-2">
                    #{practice.id}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${
                      STATUS_COLORS[practice.status] || 'bg-gray-500/20 text-gray-400'
                    }`}
                  >
                    {practice.status.replace(/_/g, ' ')}
                  </span>
                  {/* Edit/Delete buttons - show on hover */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/process/${practice.id}/edit`);
                      }}
                      className="p-1 rounded hover:bg-[var(--background-elevated)] text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
                      title="Edit process"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (
                          confirm(
                            `Delete process "${practice.practice_type_name}"?\n\nThis will mark the process as cancelled.`
                          )
                        ) {
                          try {
                            const user = await api.getProfile();
                            await api.crm.deletePractice(practice.id, user.email);
                            toast.success('Process deleted');
                            window.location.reload();
                          } catch (err) {
                            toast.error('Error', { description: (err as Error).message });
                          }
                        }
                      }}
                      className="p-1 rounded hover:bg-red-500/20 text-[var(--foreground-muted)] hover:text-red-500"
                      title="Delete process"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              {practice.expiry_date && (
                <div
                  className={`text-xs inline-flex items-center gap-1 px-2 py-0.5 rounded ${
                    ALERT_COLORS[practice.alert_color || 'green']
                  }`}
                >
                  <Calendar className="w-3 h-3" />
                  Expires: {formatDate(practice.expiry_date)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// TIMELINE TAB
// ============================================
function TimelineTab({
  interactions,
  formatDate,
  formatTime,
}: {
  interactions: Interaction[];
  formatDate: (d: string) => string;
  formatTime: (d: string) => string;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-[var(--foreground)]">Activity Timeline</h3>

      {interactions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Clock className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No activity yet</p>
        </div>
      ) : (
        <div className="space-y-1">
          {interactions.map((interaction, idx) => (
            <div key={interaction.id} className="flex gap-3">
              {/* Timeline Line */}
              <div className="flex flex-col items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    interaction.interaction_type === 'whatsapp'
                      ? 'bg-green-500/20 text-green-500'
                      : interaction.interaction_type === 'email'
                        ? 'bg-blue-500/20 text-blue-500'
                        : interaction.interaction_type === 'call'
                          ? 'bg-purple-500/20 text-purple-500'
                          : 'bg-[var(--accent)]/20 text-[var(--accent)]'
                  }`}
                >
                  {INTERACTION_ICONS[interaction.interaction_type] || (
                    <MessageCircle className="w-4 h-4" />
                  )}
                </div>
                {idx < interactions.length - 1 && (
                  <div className="w-0.5 h-full min-h-[40px] bg-[var(--border)]" />
                )}
              </div>

              {/* Content */}
              <div className="flex-1 pb-4">
                <div className="rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-[var(--foreground)]">
                      {interaction.interaction_type.charAt(0).toUpperCase() +
                        interaction.interaction_type.slice(1)}
                    </span>
                    <span className="text-[10px] text-[var(--foreground-muted)]">
                      {formatDate(interaction.interaction_date)}{' '}
                      {formatTime(interaction.interaction_date)}
                    </span>
                  </div>
                  {interaction.subject && (
                    <p className="text-sm text-[var(--foreground)] mb-1">{interaction.subject}</p>
                  )}
                  {interaction.summary && (
                    <p className="text-xs text-[var(--foreground-muted)] line-clamp-2">
                      {interaction.summary}
                    </p>
                  )}
                  <div className="flex items-center gap-2 mt-2 text-[10px] text-[var(--foreground-muted)]">
                    <span>{interaction.team_member}</span>
                    {interaction.sentiment && (
                      <span
                        className={`px-1.5 py-0.5 rounded ${
                          interaction.sentiment === 'positive'
                            ? 'bg-green-500/20 text-green-400'
                            : interaction.sentiment === 'negative'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-gray-500/20 text-gray-400'
                        }`}
                      >
                        {interaction.sentiment}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// MODAL COMPONENTS
// ============================================

function Modal({
  title,
  onClose,
  children,
  isSaving,
  onSave,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  isSaving: boolean;
  onSave: (e: React.FormEvent) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-[var(--background)] border border-[var(--border)] rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-6 border-b border-[var(--border)]">
          <h2 className="text-xl font-semibold text-[var(--foreground)]">{title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>
        <form onSubmit={onSave} className="overflow-y-auto flex-1">
          <div className="p-6 space-y-6">{children}</div>
          <div className="flex items-center justify-end gap-3 p-6 border-t border-[var(--border)] bg-[var(--background-secondary)] mt-auto">
            <Button type="button" variant="outline" onClick={onClose} disabled={isSaving}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSaving} className="gap-2">
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Changes
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// TEAM MEMBERS - Should fetch from API but hardcoded for now as per NewClientPage
const TEAM_MEMBERS = [
  { value: 'adit@balizero.com', label: 'Adit', avatar: '/avatars/team/adit.png' },
  { value: 'ari@balizero.com', label: 'Ari', avatar: '/avatars/team/ari.png' },
  { value: 'krisna@balizero.com', label: 'Krisna', avatar: '/avatars/team/krisna.png' },
  { value: 'dea@balizero.com', label: 'Dea', avatar: '/avatars/team/dea.png' },
  { value: 'zero@balizero.com', label: 'Anton' },
  { value: 'damar@balizero.com', label: 'Damar' },
  { value: 'vino@balizero.com', label: 'Vino' },
  { value: 'ruslana@balizero.com', label: 'Ruslana', avatar: '/avatars/team/ruslana.jpg' },
  { value: 'anna@balizero.com', label: 'Anna', avatar: '/avatars/team/anna.jpeg' },
  { value: 'marta@balizero.com', label: 'Marta', avatar: '/avatars/team/marta.jpeg' },
  { value: 'olena@balizero.com', label: 'Olena', avatar: '/avatars/team/olena.jpeg' },
  { value: 'veronika@balizero.com', label: 'Veronika' },
  { value: 'dewaayu@balizero.com', label: 'Dewa Ayu' },
  { value: 'faysha@balizero.com', label: 'Faysha' },
  { value: 'kadek@balizero.com', label: 'Kadek' },
  { value: 'angel@balizero.com', label: 'Angel' },
  { value: 'surya@balizero.com', label: 'Surya' },
  { value: 'sahira@balizero.com', label: 'Sahira', avatar: '/avatars/team/sahira.png' },
];

// Helper to get team member avatar
const getTeamMemberAvatar = (email: string): string | undefined => {
  return TEAM_MEMBERS.find((m) => m.value === email)?.avatar;
};

function EditClientModal({
  client,
  onClose,
  onSave,
}: {
  client: Client;
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    full_name: client.full_name || '',
    email: client.email || '',
    phone: client.phone || '',
    whatsapp: client.whatsapp || '',
    company_name: client.company_name || '',
    nationality: client.nationality || '',
    passport_number: client.passport_number || '',
    passport_expiry: client.passport_expiry?.split('T')[0] || '',
    address: client.address || '',
    notes: client.notes || '',
    status: client.status || 'lead',
    client_type: client.client_type || 'individual',
    assigned_to: client.assigned_to || '',
    avatar_url: client.avatar_url || '',
  });

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert('Image size must be less than 2MB');
      return;
    }

    try {
      // Crop to square and resize to 400x400px
      const resizedImage = await cropToSquare(file, 400, 0.85);
      setFormData((prev) => ({ ...prev, avatar_url: resizedImage }));
    } catch (error) {
      logger.error(
        'Failed to process image',
        { component: 'ClientDetail', action: 'processImage' },
        error instanceof Error ? error : new Error(String(error))
      );
      alert('Failed to process image. Please try again.');
    }
  };

  const removeAvatar = () => {
    setFormData((prev) => ({ ...prev, avatar_url: '' }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name.trim()) return alert('Full name is required');
    setIsSaving(true);
    try {
      const user = await api.getProfile();
      const updates: Record<string, string> = {};
      Object.entries(formData).forEach(([key, value]) => {
        if (value !== undefined && value !== null) updates[key] = value;
      });
      await api.crm.updateClient(client.id, updates, user.email);
      onSave();
      onClose();
      toast.success('Client updated');
    } catch (err) {
      toast.error('Failed to update', { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:border-[var(--accent)]';

  return (
    <Modal title="Edit Client" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      {/* Avatar Upload */}
      <div className="flex items-center gap-6 pb-6 border-b border-[var(--border)]">
        <div className="relative">
          <div className="w-24 h-24 rounded-full overflow-hidden border-2 border-[var(--border)] bg-[var(--background-secondary)] flex items-center justify-center">
            {formData.avatar_url ? (
              <img
                src={formData.avatar_url}
                alt="Avatar preview"
                className="w-full h-full object-cover"
              />
            ) : formData.status === 'lead' ? (
              <img
                src="/avatars/default-lead.svg"
                alt="Default Lead"
                className="w-full h-full object-cover"
              />
            ) : formData.status === 'active' ? (
              <img
                src="/avatars/default-active.svg"
                alt="Default Active"
                className="w-full h-full object-cover"
              />
            ) : (
              <User className="w-12 h-12 text-[var(--foreground-muted)]" />
            )}
          </div>
          {formData.avatar_url && (
            <button
              type="button"
              onClick={removeAvatar}
              className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Client Photo</label>
          <p className="text-xs text-[var(--foreground-muted)] mb-2">
            Upload a profile picture (max 2MB)
          </p>
          <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)] text-white hover:bg-[var(--accent)]/90 transition-colors cursor-pointer">
            <Upload className="w-4 h-4" />
            {formData.avatar_url ? 'Change Photo' : 'Upload Photo'}
            <input type="file" accept="image/*" onChange={handleAvatarUpload} className="hidden" />
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Full Name *</label>
          <input
            type="text"
            value={formData.full_name}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            className={inputClass}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Email</label>
          <input
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Phone</label>
          <div className="flex gap-1">
            <select
              value={extractCountryCode(formData.phone).countryCode}
              onChange={(e) => {
                const { localNumber } = extractCountryCode(formData.phone);
                setFormData({ ...formData, phone: e.target.value + localNumber });
              }}
              className={`${inputClass} w-[100px] flex-shrink-0`}
            >
              {COUNTRY_CODES.map(({ code, country, flag }) => (
                <option key={code} value={code}>
                  {flag} {code}
                </option>
              ))}
            </select>
            <input
              type="tel"
              value={extractCountryCode(formData.phone).localNumber}
              onChange={(e) => {
                const { countryCode } = extractCountryCode(formData.phone);
                const digits = e.target.value.replace(/[^\d]/g, '');
                setFormData({ ...formData, phone: countryCode + digits });
              }}
              className={`${inputClass} flex-1`}
              placeholder="Phone number"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Nationality</label>
          <select
            value={formData.nationality}
            onChange={(e) => setFormData({ ...formData, nationality: e.target.value })}
            className={inputClass}
          >
            <option value="">Select...</option>
            {COMMON_NATIONALITIES.map((nat) => (
              <option key={nat} value={nat}>
                {nat}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Number</label>
          <input
            type="text"
            value={formData.passport_number}
            onChange={(e) =>
              setFormData({ ...formData, passport_number: e.target.value.toUpperCase() })
            }
            className={inputClass}
            placeholder="e.g. YA123456"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Expiry</label>
          <input
            type="date"
            value={formData.passport_expiry}
            onChange={(e) => setFormData({ ...formData, passport_expiry: e.target.value })}
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Assigned To</label>
          <select
            value={formData.assigned_to}
            onChange={(e) => setFormData({ ...formData, assigned_to: e.target.value })}
            className={inputClass}
          >
            <option value="">Unassigned</option>
            {TEAM_MEMBERS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Status</label>
          <div className="flex gap-2 flex-wrap">
            {CLIENT_STATUSES.map(({ value, label, color }) => (
              <button
                key={value}
                type="button"
                onClick={() => setFormData({ ...formData, status: value })}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all border ${
                  formData.status === value
                    ? `border-${color}-500/50`
                    : 'border-transparent bg-[var(--background-secondary)]'
                }`}
                style={{
                  backgroundColor:
                    formData.status === value
                      ? `var(--${color === 'blue' ? 'accent' : color}-500-20, rgba(59, 130, 246, 0.2))`
                      : undefined,
                  color:
                    formData.status === value
                      ? `var(--${color === 'blue' ? 'accent' : color}-500, #3b82f6)`
                      : 'var(--foreground-muted)',
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}

function AddFamilyMemberModal({
  clientId,
  onClose,
  onSave,
}: {
  clientId: number;
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    full_name: '',
    relationship: 'spouse',
    nationality: '',
    passport_number: '',
    passport_expiry: '',
    current_visa_type: '',
    visa_expiry: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name) return;
    setIsSaving(true);
    try {
      await api.crm.createFamilyMember(clientId, formData);
      toast.success('Family member added');
      onSave();
      onClose();
    } catch (err) {
      toast.error('Failed to add', { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50';

  return (
    <Modal title="Add Family Member" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Full Name *</label>
          <input
            type="text"
            value={formData.full_name}
            onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
            className={inputClass}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Relationship</label>
          <select
            value={formData.relationship}
            onChange={(e) => setFormData({ ...formData, relationship: e.target.value })}
            className={inputClass}
          >
            <option value="spouse">Spouse</option>
            <option value="child">Child</option>
            <option value="parent">Parent</option>
            <option value="dependent">Dependent</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Nationality</label>
          <select
            value={formData.nationality}
            onChange={(e) => setFormData({ ...formData, nationality: e.target.value })}
            className={inputClass}
          >
            <option value="">Select...</option>
            {COMMON_NATIONALITIES.map((nat) => (
              <option key={nat} value={nat}>
                {nat}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Number</label>
          <input
            type="text"
            value={formData.passport_number}
            onChange={(e) =>
              setFormData({ ...formData, passport_number: e.target.value.toUpperCase() })
            }
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Passport Expiry</label>
          <input
            type="date"
            value={formData.passport_expiry}
            onChange={(e) => setFormData({ ...formData, passport_expiry: e.target.value })}
            className={inputClass}
          />
        </div>
      </div>
    </Modal>
  );
}

function AddDocumentModal({
  clientId,
  categories,
  familyMembers,
  clientHasDriveFolder,
  onClose,
  onSave,
}: {
  clientId: number;
  categories: DocumentCategory[];
  familyMembers: FamilyMember[];
  clientHasDriveFolder?: boolean;
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    file_name: '',
    document_type: '',
    document_category: 'other' as DocumentCategoryType,
    expiry_date: '',
    google_drive_file_url: '',
    family_member_id: '',
    drive_folder: '', // Selected folder name
  });

  // Auto-select folder based on category
  React.useEffect(() => {
    const categoryToFolder: Record<string, string> = {
      immigration: '01_Immigration',
      pma: '02_Company',
      tax: '03_Tax',
      personal: '04_Family',
      other: '99_Misc',
    };

    if (formData.document_category && clientHasDriveFolder) {
      setFormData((prev) => ({
        ...prev,
        drive_folder: categoryToFolder[formData.document_category] || '99_Misc',
      }));
    }
  }, [formData.document_category, clientHasDriveFolder]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.file_name) return;
    setIsSaving(true);
    try {
      await api.crm.createDocument(clientId, {
        ...formData,
        family_member_id: formData.family_member_id ? Number(formData.family_member_id) : undefined,
      });
      toast.success('Document added');
      onSave();
      onClose();
    } catch (err) {
      toast.error('Failed to add', { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50';

  return (
    <Modal title="Add Document" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Document Name *</label>
          <input
            type="text"
            value={formData.file_name}
            onChange={(e) => setFormData({ ...formData, file_name: e.target.value })}
            className={inputClass}
            placeholder="e.g. Passport Scan"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Category</label>
          <select
            value={formData.document_category}
            onChange={(e) =>
              setFormData({
                ...formData,
                document_category: e.target.value as DocumentCategoryType,
              })
            }
            className={inputClass}
          >
            <option value="immigration">Immigration</option>
            <option value="pma">Company (PMA)</option>
            <option value="tax">Tax</option>
            <option value="personal">Personal</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Type</label>
          <input
            type="text"
            value={formData.document_type}
            onChange={(e) => setFormData({ ...formData, document_type: e.target.value })}
            className={inputClass}
            placeholder="passport, kitas, etc"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Expiry Date</label>
          <input
            type="date"
            value={formData.expiry_date}
            onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })}
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Belongs To</label>
          <select
            value={formData.family_member_id}
            onChange={(e) => setFormData({ ...formData, family_member_id: e.target.value })}
            className={inputClass}
          >
            <option value="">Main Client</option>
            {familyMembers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name} ({m.relationship})
              </option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Google Drive Link</label>
          <input
            type="url"
            value={formData.google_drive_file_url}
            onChange={(e) => setFormData({ ...formData, google_drive_file_url: e.target.value })}
            className={inputClass}
            placeholder="https://drive.google.com/..."
          />
        </div>
      </div>
    </Modal>
  );
}

// ============================================
// EDIT DOCUMENT MODAL
// ============================================
function EditDocumentModal({
  clientId,
  document,
  categories,
  familyMembers,
  onClose,
  onSave,
}: {
  clientId: number;
  document: ClientDocument;
  categories: DocumentCategory[];
  familyMembers: FamilyMember[];
  onClose: () => void;
  onSave: () => void;
}) {
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    file_name: document.file_name || '',
    document_type: document.document_type || '',
    document_category: document.document_category || 'other',
    expiry_date: document.expiry_date?.split('T')[0] || '',
    google_drive_file_url: document.google_drive_file_url || '',
    family_member_id: document.family_member_id?.toString() || '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.file_name) return;
    setIsSaving(true);
    try {
      await api.crm.updateDocument(clientId, document.id, {
        file_name: formData.file_name,
        document_type: formData.document_type,
        document_category: formData.document_category,
        expiry_date: formData.expiry_date || undefined,
        google_drive_file_url: formData.google_drive_file_url || undefined,
        family_member_id: formData.family_member_id ? Number(formData.family_member_id) : undefined,
      });
      toast.success('Document updated');
      onSave();
      onClose();
    } catch (err) {
      toast.error('Failed to update', { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    'w-full px-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50';

  return (
    <Modal title="Edit Document" onClose={onClose} isSaving={isSaving} onSave={handleSubmit}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Document Name *</label>
          <input
            type="text"
            value={formData.file_name}
            onChange={(e) => setFormData({ ...formData, file_name: e.target.value })}
            className={inputClass}
            placeholder="e.g. Passport Scan"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Category</label>
          <select
            value={formData.document_category}
            onChange={(e) =>
              setFormData({
                ...formData,
                document_category: e.target.value as DocumentCategoryType,
              })
            }
            className={inputClass}
          >
            <option value="immigration">Immigration</option>
            <option value="pma">Company (PMA)</option>
            <option value="tax">Tax</option>
            <option value="personal">Personal</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Type</label>
          <input
            type="text"
            value={formData.document_type}
            onChange={(e) => setFormData({ ...formData, document_type: e.target.value })}
            className={inputClass}
            placeholder="passport, kitas, etc"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Expiry Date</label>
          <input
            type="date"
            value={formData.expiry_date}
            onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })}
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Belongs To</label>
          <select
            value={formData.family_member_id}
            onChange={(e) => setFormData({ ...formData, family_member_id: e.target.value })}
            className={inputClass}
          >
            <option value="">Main Client</option>
            {familyMembers.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name} ({m.relationship})
              </option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Google Drive Link</label>
          <input
            type="url"
            value={formData.google_drive_file_url}
            onChange={(e) => setFormData({ ...formData, google_drive_file_url: e.target.value })}
            className={inputClass}
            placeholder="https://drive.google.com/..."
          />
        </div>
      </div>
    </Modal>
  );
}

// ============================================
// COMPANY TAB (Company-Centric CRM)
// ============================================
function CompanyTab({
  clientId,
  formatDate,
}: {
  clientId: number;
  formatDate: (d: string) => string;
}) {
  const [companies, setCompanies] = useState<ClientCompanyLink[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadCompanies();
  }, [clientId]);

  const loadCompanies = async () => {
    try {
      setIsLoading(true);
      const data = await api.crm.getClientCompanies(clientId);
      setCompanies(data);
    } catch (err) {
      logger.error('Failed to load companies:', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--foreground)]">Companies</h3>
          <p className="text-sm text-[var(--foreground-muted)]">
            PT PMA, companies, and business entities
          </p>
        </div>
        <Button
          size="sm"
          className="gap-2"
          onClick={() => {
            toast.info('Coming soon', { description: 'Company creation will be available shortly' });
          }}
        >
          <Plus className="w-4 h-4" />
          Add Company
        </Button>
      </div>

      {companies.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Building2 className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-[var(--foreground-muted)]">No companies linked yet</p>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">
            Link this client to PT PMA or other companies
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {companies.map((company) => (
            <div
              key={company.company_id}
              className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
                    <Building2 className="w-6 h-6 text-purple-400" />
                  </div>
                  <div>
                    <h4 className="font-semibold text-[var(--foreground)]">
                      {company.company_name}
                    </h4>
                    <p className="text-xs text-[var(--foreground-muted)]">
                      {company.company_type}
                    </p>
                  </div>
                </div>
                <span
                  className={`px-2 py-1 rounded text-xs font-medium ${
                    company.status === 'active'
                      ? 'bg-green-500/20 text-green-400'
                      : company.status === 'in_setup'
                        ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-gray-500/20 text-gray-400'
                  }`}
                >
                  {company.status}
                </span>
              </div>

              <div className="mt-4 space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-[var(--foreground-muted)]">Role</span>
                  <span className="font-medium">{company.role}</span>
                </div>
                {company.ownership_percentage !== undefined && company.ownership_percentage > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--foreground-muted)]">Ownership</span>
                    <span className="font-medium">{company.ownership_percentage}%</span>
                  </div>
                )}
                {company.nib && (
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--foreground-muted)]">NIB</span>
                    <span className="font-mono text-xs">{company.nib}</span>
                  </div>
                )}
                {company.kbli_code && (
                  <div className="flex items-center justify-between">
                    <span className="text-[var(--foreground-muted)]">KBLI</span>
                    <span className="text-xs">{company.kbli_code}</span>
                  </div>
                )}
                {company.setup_progress > 0 && company.setup_progress < 100 && (
                  <div className="pt-2">
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-[var(--foreground-muted)]">Setup Progress</span>
                      <span>{company.setup_progress}%</span>
                    </div>
                    <div className="h-1.5 bg-[var(--border)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded-full"
                        style={{ width: `${company.setup_progress}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-4 pt-4 border-t border-[var(--border)] flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 text-xs"
                  onClick={() => {
                    toast.info('Company details', { 
                      description: 'Full company management coming soon' 
                    });
                  }}
                >
                  View Details
                </Button>
                {company.is_primary && (
                  <span className="px-2 py-1 rounded bg-[var(--accent)]/20 text-[var(--accent)] text-xs">
                    Primary
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================
// TAX TAB (Company-Centric CRM)
// ============================================
function TaxTab({
  clientId,
  formatDate,
}: {
  clientId: number;
  formatDate: (d: string) => string;
}) {
  const [companies, setCompanies] = useState<ClientCompanyLink[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [clientId]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const data = await api.crm.getClientCompanies(clientId);
      setCompanies(data);
    } catch (err) {
      logger.error('Failed to load tax data:', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[var(--foreground)]">Tax Overview</h3>
          <p className="text-sm text-[var(--foreground-muted)]">
            Tax obligations and filings for linked companies
          </p>
        </div>
      </div>

      {/* Personal Tax Card */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center">
            <User className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h4 className="font-semibold text-[var(--foreground)]">Personal Tax</h4>
            <p className="text-xs text-[var(--foreground-muted)]">Individual NPWP & obligations</p>
          </div>
        </div>
        <div className="text-sm text-[var(--foreground-muted)]">
          Personal tax management will be available in the next update.
        </div>
      </div>

      {/* Company Tax Cards */}
      {companies.length > 0 && (
        <div className="space-y-4">
          <h4 className="font-medium text-[var(--foreground)]">Company Tax</h4>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {companies.map((company) => (
              <div
                key={company.company_id}
                className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-5"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center">
                      <Building2 className="w-5 h-5 text-blue-400" />
                    </div>
                    <div>
                      <h4 className="font-semibold text-[var(--foreground)]">
                        {company.company_name}
                      </h4>
                      <p className="text-xs text-[var(--foreground-muted)]">{company.npwp_company || 'NPWP pending'}</p>
                    </div>
                  </div>
                </div>

                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Status</span>
                    <span className="text-emerald-400">Compliant</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Last Filing</span>
                    <span className="text-[var(--foreground-muted)]">-</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Next Deadline</span>
                    <span className="text-[var(--foreground-muted)]">-</span>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-[var(--border)]">
                  <Button
                    variant="outline"
                    size="sm"
                    className="w-full text-xs"
                    onClick={() => {
                      toast.info('Tax details', { 
                        description: 'Full tax management coming soon' 
                      });
                    }}
                  >
                    View Tax Details
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Info Card */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-[var(--foreground-muted)] mt-0.5" />
          <div>
            <h4 className="font-medium text-[var(--foreground)]">Tax Management</h4>
            <p className="text-sm text-[var(--foreground-muted)] mt-1">
              Tax document tracking and filing deadlines will be integrated here. 
              For now, tax documents are stored in the 03_Tax folder in Google Drive.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
