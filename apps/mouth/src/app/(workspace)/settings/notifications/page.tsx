'use client';

import React, { useState } from 'react';
import { Bell, Mail, MessageSquare, AlertTriangle, ArrowLeft, Save } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

interface NotificationSetting {
  id: string;
  label: string;
  description: string;
  email: boolean;
  push: boolean;
  inApp: boolean;
}

export default function NotificationsSettingsPage() {
  const router = useRouter();
  const [isSaving, setIsSaving] = useState(false);
  const [settings, setSettings] = useState<NotificationSetting[]>([
    {
      id: 'new_message',
      label: 'New Messages',
      description: 'When you receive a new chat message',
      email: true,
      push: true,
      inApp: true,
    },
    {
      id: 'whatsapp',
      label: 'WhatsApp Notifications',
      description: 'New WhatsApp messages from clients',
      email: false,
      push: true,
      inApp: true,
    },
    {
      id: 'case_updates',
      label: 'Case Updates',
      description: 'Updates on cases you\'re assigned to',
      email: true,
      push: true,
      inApp: true,
    },
    {
      id: 'deadlines',
      label: 'Deadline Reminders',
      description: 'Reminders for upcoming deadlines',
      email: true,
      push: true,
      inApp: true,
    },
    {
      id: 'team_activity',
      label: 'Team Activity',
      description: 'When team members clock in/out',
      email: false,
      push: false,
      inApp: true,
    },
    {
      id: 'system_alerts',
      label: 'System Alerts',
      description: 'Important system notifications',
      email: true,
      push: true,
      inApp: true,
    },
  ]);

  const toggleSetting = (id: string, type: 'email' | 'push' | 'inApp') => {
    setSettings(settings.map(s =>
      s.id === id ? { ...s, [type]: !s[type] } : s
    ));
  };

  const handleSave = async () => {
    setIsSaving(true);
    // Save to localStorage or API
    localStorage.setItem('notificationSettings', JSON.stringify(settings));
    setTimeout(() => {
      setIsSaving(false);
    }, 1000);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.push('/settings')}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <Bell className="w-6 h-6 text-yellow-400" />
            Notification Settings
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Configure how you want to receive notifications
          </p>
        </div>
      </div>

      {/* Legend */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
        <div className="flex gap-6 text-sm">
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-blue-400" />
            <span className="text-[var(--foreground-muted)]">Email</span>
          </div>
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-purple-400" />
            <span className="text-[var(--foreground-muted)]">Push</span>
          </div>
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-green-400" />
            <span className="text-[var(--foreground-muted)]">In-App</span>
          </div>
        </div>
      </div>

      {/* Notification Settings */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] overflow-hidden">
        <div className="divide-y divide-[var(--border)]">
          {settings.map((setting) => (
            <div key={setting.id} className="p-4 flex items-center justify-between">
              <div>
                <h3 className="font-medium text-[var(--foreground)]">{setting.label}</h3>
                <p className="text-sm text-[var(--foreground-muted)]">{setting.description}</p>
              </div>
              <div className="flex gap-3">
                {/* Email Toggle */}
                <button
                  onClick={() => toggleSetting(setting.id, 'email')}
                  className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                    setting.email
                      ? 'bg-blue-500/20 text-blue-400'
                      : 'bg-[var(--background)] text-[var(--foreground-muted)] hover:bg-[var(--background-secondary)]'
                  }`}
                  title="Email notifications"
                >
                  <Mail className="w-4 h-4" />
                </button>
                {/* Push Toggle */}
                <button
                  onClick={() => toggleSetting(setting.id, 'push')}
                  className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                    setting.push
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'bg-[var(--background)] text-[var(--foreground-muted)] hover:bg-[var(--background-secondary)]'
                  }`}
                  title="Push notifications"
                >
                  <Bell className="w-4 h-4" />
                </button>
                {/* In-App Toggle */}
                <button
                  onClick={() => toggleSetting(setting.id, 'inApp')}
                  className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${
                    setting.inApp
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-[var(--background)] text-[var(--foreground-muted)] hover:bg-[var(--background-secondary)]'
                  }`}
                  title="In-app notifications"
                >
                  <MessageSquare className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quiet Hours */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Quiet Hours</h2>
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm text-[var(--foreground)]">Enable Quiet Hours</p>
            <p className="text-xs text-[var(--foreground-muted)]">Pause notifications during specific hours</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" className="sr-only peer" />
            <div className="w-11 h-6 bg-[var(--background)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent)]"></div>
          </label>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-[var(--foreground-muted)] mb-1">Start Time</label>
            <input
              type="time"
              defaultValue="22:00"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)]"
            />
          </div>
          <div>
            <label className="block text-sm text-[var(--foreground-muted)] mb-1">End Time</label>
            <input
              type="time"
              defaultValue="07:00"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)]"
            />
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          <Save className="w-4 h-4 mr-2" />
          {isSaving ? 'Saving...' : 'Save Changes'}
        </Button>
      </div>
    </div>
  );
}
