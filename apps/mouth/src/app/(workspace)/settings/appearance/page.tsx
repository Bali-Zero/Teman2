'use client';

import React, { useState, useEffect } from 'react';
import { Palette, Sun, Moon, Monitor, Check, ArrowLeft, Save } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

type Theme = 'light' | 'dark' | 'system';
type AccentColor = 'cyan' | 'purple' | 'blue' | 'green' | 'amber' | 'pink';

const themes: { id: Theme; label: string; icon: typeof Sun }[] = [
  { id: 'light', label: 'Light', icon: Sun },
  { id: 'dark', label: 'Dark', icon: Moon },
  { id: 'system', label: 'System', icon: Monitor },
];

const accentColors: { id: AccentColor; label: string; color: string }[] = [
  { id: 'cyan', label: 'Cyan', color: '#22D3EE' },
  { id: 'purple', label: 'Purple', color: '#A78BFA' },
  { id: 'blue', label: 'Blue', color: '#60A5FA' },
  { id: 'green', label: 'Green', color: '#34D399' },
  { id: 'amber', label: 'Amber', color: '#FBBF24' },
  { id: 'pink', label: 'Pink', color: '#F472B6' },
];

export default function AppearanceSettingsPage() {
  const router = useRouter();
  const [isSaving, setIsSaving] = useState(false);
  const [selectedTheme, setSelectedTheme] = useState<Theme>('dark');
  const [selectedAccent, setSelectedAccent] = useState<AccentColor>('cyan');
  const [compactMode, setCompactMode] = useState(false);
  const [animationsEnabled, setAnimationsEnabled] = useState(true);

  useEffect(() => {
    // Load saved preferences
    const savedTheme = localStorage.getItem('theme') as Theme;
    const savedAccent = localStorage.getItem('accentColor') as AccentColor;
    const savedCompact = localStorage.getItem('compactMode') === 'true';
    const savedAnimations = localStorage.getItem('animations') !== 'false';

    if (savedTheme) setSelectedTheme(savedTheme);
    if (savedAccent) setSelectedAccent(savedAccent);
    setCompactMode(savedCompact);
    setAnimationsEnabled(savedAnimations);
  }, []);

  const handleSave = async () => {
    setIsSaving(true);

    // Save to localStorage
    localStorage.setItem('theme', selectedTheme);
    localStorage.setItem('accentColor', selectedAccent);
    localStorage.setItem('compactMode', String(compactMode));
    localStorage.setItem('animations', String(animationsEnabled));

    // Apply theme changes
    if (selectedTheme === 'dark') {
      document.documentElement.classList.add('dark');
    } else if (selectedTheme === 'light') {
      document.documentElement.classList.remove('dark');
    }

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
            <Palette className="w-6 h-6 text-pink-400" />
            Appearance Settings
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Customize the look and feel of Zantara
          </p>
        </div>
      </div>

      {/* Theme Selection */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Theme</h2>
        <div className="grid grid-cols-3 gap-3">
          {themes.map((theme) => {
            const Icon = theme.icon;
            const isSelected = selectedTheme === theme.id;
            return (
              <button
                key={theme.id}
                onClick={() => setSelectedTheme(theme.id)}
                className={`relative p-4 rounded-xl border-2 transition-all ${
                  isSelected
                    ? 'border-[var(--accent)] bg-[var(--accent)]/10'
                    : 'border-[var(--border)] bg-[var(--background)] hover:border-[var(--border-hover)]'
                }`}
              >
                <Icon className={`w-8 h-8 mx-auto mb-2 ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--foreground-muted)]'}`} />
                <p className={`text-sm font-medium ${isSelected ? 'text-[var(--accent)]' : 'text-[var(--foreground)]'}`}>
                  {theme.label}
                </p>
                {isSelected && (
                  <div className="absolute top-2 right-2">
                    <Check className="w-4 h-4 text-[var(--accent)]" />
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Accent Color */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Accent Color</h2>
        <div className="grid grid-cols-6 gap-3">
          {accentColors.map((accent) => {
            const isSelected = selectedAccent === accent.id;
            return (
              <button
                key={accent.id}
                onClick={() => setSelectedAccent(accent.id)}
                className={`relative w-full aspect-square rounded-xl border-2 transition-all ${
                  isSelected ? 'border-white scale-110' : 'border-transparent hover:scale-105'
                }`}
                style={{ backgroundColor: accent.color }}
                title={accent.label}
              >
                {isSelected && (
                  <Check className="w-5 h-5 text-white absolute inset-0 m-auto" />
                )}
              </button>
            );
          })}
        </div>
        <p className="text-xs text-[var(--foreground-muted)] mt-3">
          Selected: <span style={{ color: accentColors.find(a => a.id === selectedAccent)?.color }}>{accentColors.find(a => a.id === selectedAccent)?.label}</span>
        </p>
      </div>

      {/* Display Options */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Display Options</h2>

        {/* Compact Mode */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]">
          <div>
            <p className="font-medium text-[var(--foreground)]">Compact Mode</p>
            <p className="text-sm text-[var(--foreground-muted)]">Reduce spacing and padding</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={compactMode}
              onChange={() => setCompactMode(!compactMode)}
            />
            <div className="w-11 h-6 bg-[var(--background-secondary)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent)]"></div>
          </label>
        </div>

        {/* Animations */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]">
          <div>
            <p className="font-medium text-[var(--foreground)]">Animations</p>
            <p className="text-sm text-[var(--foreground-muted)]">Enable smooth transitions and effects</p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={animationsEnabled}
              onChange={() => setAnimationsEnabled(!animationsEnabled)}
            />
            <div className="w-11 h-6 bg-[var(--background-secondary)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent)]"></div>
          </label>
        </div>
      </div>

      {/* Preview */}
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
        <h3 className="text-sm font-medium text-[var(--foreground-muted)] mb-3">Preview</h3>
        <div className="p-4 rounded-lg bg-[var(--background)] border border-[var(--border)]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full" style={{ backgroundColor: accentColors.find(a => a.id === selectedAccent)?.color }}></div>
            <div>
              <p className="font-medium text-[var(--foreground)]">Sample Card</p>
              <p className="text-sm text-[var(--foreground-muted)]">This is how elements will look</p>
            </div>
          </div>
          <button
            className="px-4 py-2 rounded-lg text-white text-sm font-medium"
            style={{ backgroundColor: accentColors.find(a => a.id === selectedAccent)?.color }}
          >
            Sample Button
          </button>
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
