'use client';

import React, { useState, useEffect } from 'react';
import { User, Mail, Phone, MapPin, Building, Save, ArrowLeft } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { UserProfile } from '@/types';

export default function ProfileSettingsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    location: '',
    department: '',
  });

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const data = await api.getProfile();
        setProfile(data);
        setFormData({
          name: data.name || '',
          email: data.email || '',
          phone: '',
          location: '',
          department: data.team || '',
        });
      } catch (err) {
        console.error('Failed to load profile:', err);
      } finally {
        setIsLoading(false);
      }
    };
    loadProfile();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    // In a real app, this would call an API endpoint
    setTimeout(() => {
      setIsSaving(false);
      // Show success message (could use toast)
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
            <User className="w-6 h-6 text-blue-400" />
            Profile Settings
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Manage your personal information
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
          <p className="text-sm text-[var(--foreground-muted)]">Loading profile...</p>
        </div>
      ) : (
        <>
          {/* Profile Picture Section */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Profile Picture</h2>
            <div className="flex items-center gap-4">
              <div className="w-20 h-20 rounded-full bg-[var(--background)] flex items-center justify-center border-2 border-[var(--border)]">
                <User className="w-10 h-10 text-[var(--foreground-muted)]" />
              </div>
              <div className="space-y-2">
                <Button variant="outline" size="sm">Change Photo</Button>
                <p className="text-xs text-[var(--foreground-muted)]">JPG, PNG max 2MB</p>
              </div>
            </div>
          </div>

          {/* Personal Information */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6 space-y-4">
            <h2 className="text-lg font-semibold text-[var(--foreground)]">Personal Information</h2>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  <User className="w-4 h-4 inline mr-2" />
                  Full Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  <Mail className="w-4 h-4 inline mr-2" />
                  Email Address
                </label>
                <input
                  type="email"
                  value={formData.email}
                  disabled
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground-muted)] cursor-not-allowed"
                />
                <p className="text-xs text-[var(--foreground-muted)] mt-1">Email cannot be changed</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  <Phone className="w-4 h-4 inline mr-2" />
                  Phone Number
                </label>
                <input
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  placeholder="+62 xxx xxxx xxxx"
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  <MapPin className="w-4 h-4 inline mr-2" />
                  Location
                </label>
                <input
                  type="text"
                  value={formData.location}
                  onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                  placeholder="Bali, Indonesia"
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  <Building className="w-4 h-4 inline mr-2" />
                  Department / Team
                </label>
                <input
                  type="text"
                  value={formData.department}
                  disabled
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground-muted)] cursor-not-allowed"
                />
              </div>
            </div>
          </div>

          {/* Account Info */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
            <h2 className="text-lg font-semibold text-[var(--foreground)] mb-4">Account Information</h2>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--foreground-muted)]">User ID</span>
                <span className="text-[var(--foreground)] font-mono">{profile?.id || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--foreground-muted)]">Role</span>
                <span className="text-[var(--foreground)]">{profile?.role || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--foreground-muted)]">Account Status</span>
                <span className="text-green-500">Active</span>
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
        </>
      )}
    </div>
  );
}
