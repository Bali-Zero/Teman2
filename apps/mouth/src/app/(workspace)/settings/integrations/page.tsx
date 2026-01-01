'use client';

import React, { useState, useEffect } from 'react';
import { Plug, MessageCircle, Mail, Cloud, Database, Calendar, ArrowLeft, CheckCircle2, XCircle, Settings, ExternalLink, Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

interface Integration {
  id: string;
  name: string;
  description: string;
  icon: typeof MessageCircle;
  iconColor: string;
  status: 'connected' | 'disconnected' | 'error';
  lastSync?: string;
  configUrl?: string;
}

export default function IntegrationsPage() {
  const router = useRouter();
  const [connecting, setConnecting] = useState<string | null>(null);
  const [integrations, setIntegrations] = useState<Integration[]>([
    {
      id: 'whatsapp',
      name: 'WhatsApp Business',
      description: 'Receive and send WhatsApp messages from clients',
      icon: MessageCircle,
      iconColor: '#25D366',
      status: 'connected',
      lastSync: '5 minutes ago',
    },
    {
      id: 'zoho',
      name: 'Zoho Mail',
      description: 'Email integration with Zoho Mail',
      icon: Mail,
      iconColor: '#E42527',
      status: 'connected',
      lastSync: '10 minutes ago',
    },
    {
      id: 'google_drive',
      name: 'Google Drive',
      description: 'Store and access documents from Google Drive',
      icon: Cloud,
      iconColor: '#4285F4',
      status: 'disconnected',
    },
    {
      id: 'qdrant',
      name: 'Qdrant Vector DB',
      description: 'Vector database for AI knowledge storage',
      icon: Database,
      iconColor: '#7C3AED',
      status: 'connected',
      lastSync: 'Just now',
    },
    {
      id: 'google_calendar',
      name: 'Google Calendar',
      description: 'Sync appointments and deadlines',
      icon: Calendar,
      iconColor: '#4285F4',
      status: 'disconnected',
    },
  ]);

  // Check Google Drive connection status on mount
  useEffect(() => {
    const checkGoogleDriveStatus = async () => {
      try {
        const status = await api.drive.getStatus();
        setIntegrations(prev => prev.map(i =>
          i.id === 'google_drive'
            ? { ...i, status: status.connected ? 'connected' : 'disconnected', lastSync: status.connected ? 'Just now' : undefined }
            : i
        ));
      } catch (error) {
        console.error('Failed to check Google Drive status:', error);
      }
    };
    checkGoogleDriveStatus();

    // Check for OAuth callback success
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('success') === 'google_drive_connected') {
      setIntegrations(prev => prev.map(i =>
        i.id === 'google_drive'
          ? { ...i, status: 'connected', lastSync: 'Just now' }
          : i
      ));
      // Clean URL
      window.history.replaceState({}, document.title, '/settings/integrations');
    }
  }, []);

  const toggleConnection = async (id: string) => {
    if (id === 'google_drive') {
      const integration = integrations.find(i => i.id === id);
      if (integration?.status === 'connected') {
        // Disconnect
        try {
          await api.drive.disconnect();
          setIntegrations(prev => prev.map(i =>
            i.id === id ? { ...i, status: 'disconnected', lastSync: undefined } : i
          ));
        } catch (error) {
          console.error('Failed to disconnect Google Drive:', error);
        }
      } else {
        // Connect - redirect to OAuth
        setConnecting(id);
        try {
          const { auth_url } = await api.drive.getAuthUrl();
          window.location.href = auth_url;
        } catch (error) {
          console.error('Failed to get auth URL:', error);
          setConnecting(null);
        }
      }
      return;
    }

    // For other integrations, just toggle state (placeholder)
    setIntegrations(integrations.map(i => {
      if (i.id === id) {
        return {
          ...i,
          status: i.status === 'connected' ? 'disconnected' : 'connected',
          lastSync: i.status === 'disconnected' ? 'Just now' : undefined,
        };
      }
      return i;
    }));
  };

  const getStatusBadge = (status: Integration['status']) => {
    switch (status) {
      case 'connected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-500/20 text-green-400">
            <CheckCircle2 className="w-3 h-3" />
            Connected
          </span>
        );
      case 'disconnected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-[var(--background)] text-[var(--foreground-muted)]">
            <XCircle className="w-3 h-3" />
            Disconnected
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-500/20 text-red-400">
            <XCircle className="w-3 h-3" />
            Error
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.push('/settings')}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <Plug className="w-6 h-6 text-cyan-400" />
            Integrations
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Connect external services to Zantara
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
          <p className="text-sm text-[var(--foreground-muted)]">Total Integrations</p>
          <p className="text-2xl font-bold text-[var(--foreground)]">{integrations.length}</p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
          <p className="text-sm text-[var(--foreground-muted)]">Active</p>
          <p className="text-2xl font-bold text-green-400">
            {integrations.filter(i => i.status === 'connected').length}
          </p>
        </div>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
          <p className="text-sm text-[var(--foreground-muted)]">Inactive</p>
          <p className="text-2xl font-bold text-[var(--foreground-muted)]">
            {integrations.filter(i => i.status === 'disconnected').length}
          </p>
        </div>
      </div>

      {/* Integrations List */}
      <div className="space-y-3">
        {integrations.map((integration) => {
          const Icon = integration.icon;
          return (
            <div
              key={integration.id}
              className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div
                    className="w-12 h-12 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: `${integration.iconColor}20` }}
                  >
                    <Icon className="w-6 h-6" style={{ color: integration.iconColor }} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium text-[var(--foreground)]">{integration.name}</h3>
                      {getStatusBadge(integration.status)}
                    </div>
                    <p className="text-sm text-[var(--foreground-muted)]">{integration.description}</p>
                    {integration.lastSync && (
                      <p className="text-xs text-[var(--foreground-muted)] mt-1">
                        Last sync: {integration.lastSync}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {integration.status === 'connected' && (
                    <Button variant="ghost" size="sm">
                      <Settings className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    variant={integration.status === 'connected' ? 'outline' : 'default'}
                    size="sm"
                    onClick={() => toggleConnection(integration.id)}
                    disabled={connecting === integration.id}
                  >
                    {connecting === integration.id ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Connecting...
                      </>
                    ) : (
                      integration.status === 'connected' ? 'Disconnect' : 'Connect'
                    )}
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Add More Integrations */}
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6 text-center">
        <Plug className="w-10 h-10 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
        <h3 className="font-medium text-[var(--foreground)] mb-2">Need more integrations?</h3>
        <p className="text-sm text-[var(--foreground-muted)] mb-4">
          Contact us to request new integrations for your workflow
        </p>
        <Button variant="outline" size="sm">
          <ExternalLink className="w-4 h-4 mr-2" />
          Request Integration
        </Button>
      </div>

      {/* Webhook Section */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h3 className="font-semibold text-[var(--foreground)] mb-4">Webhooks</h3>
        <p className="text-sm text-[var(--foreground-muted)] mb-4">
          Receive real-time notifications when events happen in Zantara
        </p>
        <div className="space-y-2">
          <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]">
            <div>
              <p className="font-medium text-[var(--foreground)]">New Client Webhook</p>
              <p className="text-xs text-[var(--foreground-muted)]">Triggered when a new client is created</p>
            </div>
            <Button variant="ghost" size="sm">Configure</Button>
          </div>
          <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]">
            <div>
              <p className="font-medium text-[var(--foreground)]">Case Status Webhook</p>
              <p className="text-xs text-[var(--foreground-muted)]">Triggered when case status changes</p>
            </div>
            <Button variant="ghost" size="sm">Configure</Button>
          </div>
        </div>
      </div>
    </div>
  );
}
