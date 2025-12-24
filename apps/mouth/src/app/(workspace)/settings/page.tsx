'use client';

import React from 'react';
import { useRouter } from 'next/navigation';
import { Settings, User, Bell, Shield, Palette, Globe, Key, Building } from 'lucide-react';
import { Button } from '@/components/ui/button';

import { Sparkles } from 'lucide-react';

const settingsSections = [
  {
    title: 'Profile',
    description: 'Manage your personal information',
    icon: User,
    href: '/settings/profile',
  },
  {
    title: 'Notifications',
    description: 'Configure notification preferences',
    icon: Bell,
    href: '/settings/notifications',
  },
  {
    title: 'Security',
    description: 'Password, 2FA and active sessions',
    icon: Shield,
    href: '/settings/security',
  },
  {
    title: 'Appearance',
    description: 'Theme and visual preferences',
    icon: Palette,
    href: '/settings/appearance',
  },
  {
    title: 'Language & Region',
    description: 'Language, timezone and date format',
    icon: Globe,
    href: '/settings/locale',
  },
  {
    title: 'API Keys',
    description: 'Manage API keys',
    icon: Key,
    href: '/settings/api',
  },
  {
    title: 'AUTO CRM',
    description: 'AI-powered CRM extraction settings and statistics',
    icon: Sparkles,
    href: '/settings/auto-crm',
  },
];

export default function SettingsPage() {
  const router = useRouter();

  const handleSettingsClick = (href: string) => {
    router.push(href);
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Settings</h1>
        <p className="text-sm text-[var(--foreground-muted)]">
          Manage your account and preferences
        </p>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {settingsSections.map((section) => (
          <div
            key={section.title}
            onClick={() => handleSettingsClick(section.href)}
            className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] hover:bg-[var(--background-elevated)]/50 cursor-pointer transition-colors group"
          >
            <div className="flex items-start gap-4">
              <div className="p-2 rounded-lg bg-[var(--background-elevated)] group-hover:bg-[var(--accent)]/10 transition-colors">
                <section.icon className="w-5 h-5 text-[var(--foreground-muted)] group-hover:text-[var(--accent)] transition-colors" />
              </div>
              <div>
                <h3 className="font-medium text-[var(--foreground)]">{section.title}</h3>
                <p className="text-sm text-[var(--foreground-muted)]">
                  {section.description}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Admin Section */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden">
        <div className="p-4 border-b border-[var(--border)] bg-[var(--background-elevated)]/30">
          <div className="flex items-center gap-2">
            <Building className="w-5 h-5 text-[var(--accent)]" />
            <h2 className="font-semibold text-[var(--foreground)]">Administration</h2>
          </div>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">
            Settings reserved for administrators
          </p>
        </div>
        <div className="p-4 space-y-3">
          {[
            { label: 'User Management', description: 'Add, modify or remove users' },
            { label: 'Roles & Permissions', description: 'Configure roles and permissions' },
            { label: 'Integrations', description: 'WhatsApp, Google Drive, other services' },
            { label: 'Backup & Export', description: 'Data backup and export' },
          ].map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between p-3 rounded-lg hover:bg-[var(--background-elevated)]/50 cursor-pointer transition-colors"
            >
              <div>
                <p className="text-sm font-medium text-[var(--foreground)]">{item.label}</p>
                <p className="text-xs text-[var(--foreground-muted)]">{item.description}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  if (item.label === 'User Management') {
                    router.push('/settings/users');
                  } else if (item.label === 'Roles & Permissions') {
                    router.push('/settings/roles');
                  } else if (item.label === 'Integrations') {
                    router.push('/settings/integrations');
                  } else if (item.label === 'Backup & Export') {
                    router.push('/settings/backup');
                  }
                }}
              >
                Configure
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <Settings className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          Complete settings center to manage profile, security,
          notifications and administrative configurations.
        </p>
      </div>
    </div>
  );
}
