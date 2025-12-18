'use client';

import React from 'react';
import { Settings, User, Bell, Shield, Palette, Globe, Key, Building } from 'lucide-react';
import { Button } from '@/components/ui/button';

const settingsSections = [
  {
    title: 'Profilo',
    description: 'Gestisci le tue informazioni personali',
    icon: User,
    href: '/settings/profile',
  },
  {
    title: 'Notifiche',
    description: 'Configura le preferenze di notifica',
    icon: Bell,
    href: '/settings/notifications',
  },
  {
    title: 'Sicurezza',
    description: 'Password, 2FA e sessioni attive',
    icon: Shield,
    href: '/settings/security',
  },
  {
    title: 'Aspetto',
    description: 'Tema e preferenze visuali',
    icon: Palette,
    href: '/settings/appearance',
  },
  {
    title: 'Lingua & Regione',
    description: 'Lingua, fuso orario e formato data',
    icon: Globe,
    href: '/settings/locale',
  },
  {
    title: 'API Keys',
    description: 'Gestisci le chiavi API',
    icon: Key,
    href: '/settings/api',
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)]">Impostazioni</h1>
        <p className="text-sm text-[var(--foreground-muted)]">
          Gestisci il tuo account e le preferenze
        </p>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {settingsSections.map((section) => (
          <div
            key={section.title}
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
            <h2 className="font-semibold text-[var(--foreground)]">Amministrazione</h2>
          </div>
          <p className="text-sm text-[var(--foreground-muted)] mt-1">
            Impostazioni riservate agli amministratori
          </p>
        </div>
        <div className="p-4 space-y-3">
          {[
            { label: 'Gestione Utenti', description: 'Aggiungi, modifica o rimuovi utenti' },
            { label: 'Ruoli & Permessi', description: 'Configura i ruoli e i permessi' },
            { label: 'Integrazioni', description: 'WhatsApp, Google Drive, altri servizi' },
            { label: 'Backup & Export', description: 'Backup dati e export' },
          ].map((item) => (
            <div
              key={item.label}
              className="flex items-center justify-between p-3 rounded-lg hover:bg-[var(--background-elevated)]/50 cursor-pointer transition-colors"
            >
              <div>
                <p className="text-sm font-medium text-[var(--foreground)]">{item.label}</p>
                <p className="text-xs text-[var(--foreground-muted)]">{item.description}</p>
              </div>
              <Button variant="ghost" size="sm">
                Configura
              </Button>
            </div>
          ))}
        </div>
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <Settings className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          Centro impostazioni completo per gestire profilo, sicurezza,
          notifiche e configurazioni amministrative.
        </p>
      </div>
    </div>
  );
}
