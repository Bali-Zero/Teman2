'use client';

import React, { useState, useEffect } from 'react';
import { Globe, Clock, Calendar, ArrowLeft, Save, Check } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

interface LocaleOption {
  code: string;
  label: string;
  native: string;
}

const languages: LocaleOption[] = [
  { code: 'en', label: 'English', native: 'English' },
  { code: 'id', label: 'Indonesian', native: 'Bahasa Indonesia' },
  { code: 'it', label: 'Italian', native: 'Italiano' },
  { code: 'zh', label: 'Chinese', native: '中文' },
  { code: 'ja', label: 'Japanese', native: '日本語' },
];

const timezones = [
  { value: 'Asia/Jakarta', label: 'Jakarta (WIB) UTC+7' },
  { value: 'Asia/Makassar', label: 'Bali (WITA) UTC+8' },
  { value: 'Asia/Jayapura', label: 'Papua (WIT) UTC+9' },
  { value: 'Asia/Singapore', label: 'Singapore UTC+8' },
  { value: 'Europe/Rome', label: 'Rome (CET) UTC+1' },
  { value: 'Europe/London', label: 'London (GMT) UTC+0' },
  { value: 'America/New_York', label: 'New York (EST) UTC-5' },
  { value: 'America/Los_Angeles', label: 'Los Angeles (PST) UTC-8' },
];

const dateFormats = [
  { value: 'DD/MM/YYYY', label: '31/12/2024', example: 'DD/MM/YYYY' },
  { value: 'MM/DD/YYYY', label: '12/31/2024', example: 'MM/DD/YYYY' },
  { value: 'YYYY-MM-DD', label: '2024-12-31', example: 'YYYY-MM-DD' },
  { value: 'DD MMM YYYY', label: '31 Dec 2024', example: 'DD MMM YYYY' },
];

const timeFormats = [
  { value: '24h', label: '14:30', example: '24-hour' },
  { value: '12h', label: '2:30 PM', example: '12-hour' },
];

export default function LocaleSettingsPage() {
  const router = useRouter();
  const [isSaving, setIsSaving] = useState(false);
  const [settings, setSettings] = useState({
    language: 'en',
    timezone: 'Asia/Makassar',
    dateFormat: 'DD/MM/YYYY',
    timeFormat: '24h',
    firstDayOfWeek: 'monday',
  });

  useEffect(() => {
    // Load saved preferences
    const saved = localStorage.getItem('localeSettings');
    if (saved) {
      setSettings(JSON.parse(saved));
    }
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    localStorage.setItem('localeSettings', JSON.stringify(settings));
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
            <Globe className="w-6 h-6 text-blue-400" />
            Language & Region
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Set your language, timezone, and date format preferences
          </p>
        </div>
      </div>

      {/* Language Selection */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Language</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {languages.map((lang) => {
            const isSelected = settings.language === lang.code;
            return (
              <button
                key={lang.code}
                onClick={() => setSettings({ ...settings, language: lang.code })}
                className={`relative p-3 rounded-lg border-2 text-left transition-all ${
                  isSelected
                    ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                    : 'border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]'
                }`}
              >
                <p className={`font-medium ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}`}>
                  {lang.label}
                </p>
                <p className="text-sm text-[var(--foreground-muted)]">{lang.native}</p>
                {isSelected && (
                  <Check className="absolute top-2 right-2 w-4 h-4 text-[var(--accent)]" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Timezone */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="w-5 h-5 text-purple-400" />
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Timezone</h2>
        </div>
        <select
          value={settings.timezone}
          onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
          className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
        >
          {timezones.map((tz) => (
            <option key={tz.value} value={tz.value}>
              {tz.label}
            </option>
          ))}
        </select>
        <p className="text-xs text-[var(--foreground-muted)] mt-2">
          Current time: {new Date().toLocaleTimeString('en-US', { timeZone: settings.timezone })}
        </p>
      </div>

      {/* Date & Time Format */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6 space-y-6">
        <div className="flex items-center gap-2">
          <Calendar className="w-5 h-5 text-amber-400" />
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Date & Time Format</h2>
        </div>

        {/* Date Format */}
        <div>
          <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-2">Date Format</label>
          <div className="grid grid-cols-2 gap-3">
            {dateFormats.map((format) => {
              const isSelected = settings.dateFormat === format.value;
              return (
                <button
                  key={format.value}
                  onClick={() => setSettings({ ...settings, dateFormat: format.value })}
                  className={`p-3 rounded-lg border-2 text-left transition-all ${
                    isSelected
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                      : 'border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]'
                  }`}
                >
                  <p className={`font-medium ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}`}>
                    {format.label}
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)]">{format.example}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Time Format */}
        <div>
          <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-2">Time Format</label>
          <div className="grid grid-cols-2 gap-3">
            {timeFormats.map((format) => {
              const isSelected = settings.timeFormat === format.value;
              return (
                <button
                  key={format.value}
                  onClick={() => setSettings({ ...settings, timeFormat: format.value })}
                  className={`p-3 rounded-lg border-2 text-left transition-all ${
                    isSelected
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                      : 'border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]'
                  }`}
                >
                  <p className={`font-medium ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}`}>
                    {format.label}
                  </p>
                  <p className="text-xs text-[var(--foreground-muted)]">{format.example}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* First Day of Week */}
        <div>
          <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-2">First Day of Week</label>
          <div className="grid grid-cols-2 gap-3">
            {[
              { value: 'monday', label: 'Monday' },
              { value: 'sunday', label: 'Sunday' },
            ].map((day) => {
              const isSelected = settings.firstDayOfWeek === day.value;
              return (
                <button
                  key={day.value}
                  onClick={() => setSettings({ ...settings, firstDayOfWeek: day.value })}
                  className={`p-3 rounded-lg border-2 text-center transition-all ${
                    isSelected
                      ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                      : 'border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]'
                  }`}
                >
                  <p className={`font-medium ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}`}>
                    {day.label}
                  </p>
                </button>
              );
            })}
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
