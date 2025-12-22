'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FolderKanban, AlertTriangle, MessageCircle, Clock } from 'lucide-react';
import {
  StatsCard,
  PratichePreview,
  WhatsAppPreview,
  PraticaPreview,
  WhatsAppMessage,
} from '@/components/dashboard';

// Mock data - TODO: Replace with API calls
const mockPratiche: PraticaPreview[] = [
  {
    id: 1042,
    title: 'E33G KITAS Remote Worker',
    client: 'Marco Rossi',
    status: 'in_progress',
    daysRemaining: 4,
  },
  {
    id: 1038,
    title: 'PT PMA Setup',
    client: 'Sunrise Ventures',
    status: 'documents',
    daysRemaining: 12,
  },
  {
    id: 1035,
    title: 'NPWP Personal Setup',
    client: 'Sarah Johnson',
    status: 'completed',
    completedAt: 'Ieri',
  },
];

const mockWhatsAppMessages: WhatsAppMessage[] = [
  {
    id: '1',
    contactName: 'Marco Rossi',
    message: 'Ho caricato i documenti sul drive...',
    timestamp: '2m',
    isRead: false,
    hasAiSuggestion: true,
    practiceId: 1042,
  },
  {
    id: '2',
    contactName: 'Sarah Johnson',
    message: 'When will my KITAS be ready?',
    timestamp: '15m',
    isRead: false,
    practiceId: 1038,
  },
  {
    id: '3',
    contactName: '+62 812 xxx xxxx',
    message: 'Info visa please',
    timestamp: '1h',
    isRead: true,
    isNewLead: true,
  },
];

interface DashboardStats {
  praticheAttive: number;
  scadenzeUrgenti: number;
  whatsappUnread: number;
  oreLavorate: string;
}

export default function DashboardPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>({
    praticheAttive: 0,
    scadenzeUrgenti: 0,
    whatsappUnread: 0,
    oreLavorate: '0h 0m',
  });
  const [pratiche, setPratiche] = useState<PraticaPreview[]>([]);
  const [whatsappMessages, setWhatsappMessages] = useState<WhatsAppMessage[]>([]);

  useEffect(() => {
    // Simulate API call
    const loadDashboardData = async () => {
      setIsLoading(true);

      // TODO: Replace with actual API calls
      await new Promise((resolve) => setTimeout(resolve, 500));

      setStats({
        praticheAttive: 8,
        scadenzeUrgenti: 2,
        whatsappUnread: 5,
        oreLavorate: '4h 32m',
      });
      setPratiche(mockPratiche);
      setWhatsappMessages(mockWhatsAppMessages);

      setIsLoading(false);
    };

    loadDashboardData();
  }, []);

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Pratiche Attive"
          value={isLoading ? '-' : stats.praticheAttive}
          icon={FolderKanban}
          href="/pratiche"
        />
        <StatsCard
          title="Scadenze Urgenti"
          value={isLoading ? '-' : stats.scadenzeUrgenti}
          icon={AlertTriangle}
          href="/pratiche/scadenze"
          variant={stats.scadenzeUrgenti > 0 ? 'warning' : 'default'}
        />
        <StatsCard
          title="WhatsApp Non Letti"
          value={isLoading ? '-' : stats.whatsappUnread}
          icon={MessageCircle}
          href="/whatsapp"
          variant={stats.whatsappUnread > 0 ? 'danger' : 'default'}
        />
        <StatsCard
          title="Ore Oggi"
          value={isLoading ? '-' : stats.oreLavorate}
          icon={Clock}
          href="/team/timesheet"
        />
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pratiche Preview */}
        <PratichePreview pratiche={pratiche} isLoading={isLoading} />

        {/* WhatsApp Preview */}
        <WhatsAppPreview messages={whatsappMessages} isLoading={isLoading} />
      </div>

      {/* Future Space */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <p className="text-sm text-[var(--foreground-muted)]">
          Spazio per futuri widget: Activity feed, Calendar, AI suggestions...
        </p>
      </div>
    </div>
  );
}
