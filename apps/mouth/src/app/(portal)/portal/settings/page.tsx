'use client';

import React, { useState, useEffect } from 'react';
import {
  Settings,
  Bell,
  Globe,
  Clock,
  User,
  Mail,
  Phone,
  Save,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { PortalPreferences, PortalProfile } from '@/lib/api/portal/portal.types';

export default function SettingsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [showSaved, setShowSaved] = useState(false);
  const [preferences, setPreferences] = useState<PortalPreferences>({
    emailNotifications: true,
    whatsappNotifications: true,
    language: 'en',
    timezone: 'Asia/Jakarta',
  });
  const [profile, setProfile] = useState<PortalProfile | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const [profileData, prefsData] = await Promise.all([
          api.portal.getProfile(),
          api.portal.getPreferences(),
        ]);

        setProfile(profileData);
        setPreferences(prefsData);
      } catch (err) {
        console.error('Failed to load settings:', err);
        setError('Unable to load settings. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await api.portal.updatePreferences(preferences);
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 3000);
    } catch (err) {
      console.error('Failed to save settings:', err);
      setError('Failed to save settings. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-[#1A1D24] rounded w-64"></div>
        <div className="h-48 bg-[#1A1D24] rounded-xl"></div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-lg font-medium text-[#E6E7EB] mb-2">Unable to load settings</h2>
        <p className="text-[#9AA0AE] mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-[#4FD1C5] text-[#0B0E13] font-medium rounded-lg hover:bg-[#38B2AC] transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-2xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-[#E6E7EB]">Settings</h1>
        <p className="text-[#9AA0AE] mt-1">Manage your account preferences</p>
      </div>

      {/* Success Message */}
      {showSaved && (
        <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          <p className="text-emerald-400">Settings saved successfully!</p>
        </div>
      )}

      {/* Profile Section */}
      <div className="bg-[#1A1D24] rounded-xl border border-white/5 overflow-hidden">
        <div className="p-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <User className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="font-semibold text-[#E6E7EB]">Profile Information</h2>
              <p className="text-sm text-[#9AA0AE]">Your personal details (read-only)</p>
            </div>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-[#9AA0AE] mb-1">Full Name</label>
              <p className="font-medium text-[#E6E7EB]">{profile?.fullName || '-'}</p>
            </div>
            <div>
              <label className="block text-sm text-[#9AA0AE] mb-1">Email</label>
              <p className="font-medium text-[#E6E7EB]">{profile?.email || '-'}</p>
            </div>
            <div>
              <label className="block text-sm text-[#9AA0AE] mb-1">Phone</label>
              <p className="font-medium text-[#E6E7EB]">{profile?.phone || '-'}</p>
            </div>
            <div>
              <label className="block text-sm text-[#9AA0AE] mb-1">Nationality</label>
              <p className="font-medium text-[#E6E7EB]">{profile?.nationality || '-'}</p>
            </div>
          </div>
          <p className="text-sm text-[#9AA0AE] pt-2">
            To update your profile information, please contact our team.
          </p>
        </div>
      </div>

      {/* Notifications Section */}
      <div className="bg-[#1A1D24] rounded-xl border border-white/5 overflow-hidden">
        <div className="p-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg">
              <Bell className="w-5 h-5 text-amber-400" />
            </div>
            <div>
              <h2 className="font-semibold text-[#E6E7EB]">Notifications</h2>
              <p className="text-sm text-[#9AA0AE]">How you want to receive updates</p>
            </div>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mail className="w-5 h-5 text-[#9AA0AE]" />
              <div>
                <p className="font-medium text-[#E6E7EB]">Email Notifications</p>
                <p className="text-sm text-[#9AA0AE]">Receive updates via email</p>
              </div>
            </div>
            <button
              onClick={() => setPreferences((p) => ({ ...p, emailNotifications: !p.emailNotifications }))}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                preferences.emailNotifications ? 'bg-[#4FD1C5]' : 'bg-[#2a2a2a]'
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                  preferences.emailNotifications ? 'left-7' : 'left-1'
                }`}
              />
            </button>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Phone className="w-5 h-5 text-[#9AA0AE]" />
              <div>
                <p className="font-medium text-[#E6E7EB]">WhatsApp Notifications</p>
                <p className="text-sm text-[#9AA0AE]">Receive updates via WhatsApp</p>
              </div>
            </div>
            <button
              onClick={() => setPreferences((p) => ({ ...p, whatsappNotifications: !p.whatsappNotifications }))}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                preferences.whatsappNotifications ? 'bg-[#4FD1C5]' : 'bg-[#2a2a2a]'
              }`}
            >
              <div
                className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                  preferences.whatsappNotifications ? 'left-7' : 'left-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Preferences Section */}
      <div className="bg-[#1A1D24] rounded-xl border border-white/5 overflow-hidden">
        <div className="p-6 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-violet-500/10 rounded-lg">
              <Settings className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <h2 className="font-semibold text-[#E6E7EB]">Preferences</h2>
              <p className="text-sm text-[#9AA0AE]">Language and regional settings</p>
            </div>
          </div>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="flex items-center gap-2 text-sm text-[#9AA0AE] mb-2">
              <Globe className="w-4 h-4" />
              Language
            </label>
            <select
              value={preferences.language}
              onChange={(e) => setPreferences((p) => ({ ...p, language: e.target.value }))}
              className="w-full px-4 py-2 bg-[#2a2a2a] border border-white/10 rounded-lg text-[#E6E7EB] focus:outline-none focus:ring-2 focus:ring-[#4FD1C5]"
            >
              <option value="en">English</option>
              <option value="id">Bahasa Indonesia</option>
            </select>
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm text-[#9AA0AE] mb-2">
              <Clock className="w-4 h-4" />
              Timezone
            </label>
            <select
              value={preferences.timezone}
              onChange={(e) => setPreferences((p) => ({ ...p, timezone: e.target.value }))}
              className="w-full px-4 py-2 bg-[#2a2a2a] border border-white/10 rounded-lg text-[#E6E7EB] focus:outline-none focus:ring-2 focus:ring-[#4FD1C5]"
            >
              <option value="Asia/Jakarta">Jakarta (WIB, UTC+7)</option>
              <option value="Asia/Makassar">Bali (WITA, UTC+8)</option>
              <option value="Asia/Jayapura">Papua (WIT, UTC+9)</option>
              <option value="Asia/Singapore">Singapore (SGT, UTC+8)</option>
              <option value="Australia/Sydney">Sydney (AEST, UTC+10/11)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className={`flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-colors ${
            isSaving
              ? 'bg-[#1A1D24] text-[#9AA0AE] cursor-not-allowed'
              : 'bg-[#4FD1C5] text-[#0B0E13] hover:bg-[#38B2AC]'
          }`}
        >
          {isSaving ? (
            <>
              <div className="w-4 h-4 border-2 border-[#9AA0AE] border-t-transparent rounded-full animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Save Changes
            </>
          )}
        </button>
      </div>
    </div>
  );
}
