'use client';

import React, { useState, useEffect } from 'react';
import { Sparkles, CheckCircle2, XCircle, Activity, Users, FolderKanban } from 'lucide-react';
import { api } from '@/lib/api';
import type { AutoCRMStats } from '@/lib/api/crm/crm.types';

export default function AutoCRMSettingsPage() {
  const [stats, setStats] = useState<AutoCRMStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadStats = async () => {
      try {
        setIsLoading(true);
        const data = await api.crm.getAutoCRMStats(30);
        setStats(data);
      } catch (err) {
        console.error('Failed to load AUTO CRM stats:', err);
      } finally {
        setIsLoading(false);
      }
    };

    loadStats();
  }, []);

  const successRate = stats && stats.total_extractions > 0
    ? Math.round((stats.successful_extractions / stats.total_extractions) * 100)
    : 0;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-purple-400" />
          AUTO CRM Settings
        </h1>
        <p className="text-sm text-[var(--foreground-muted)] mt-2">
          AI-powered automatic extraction and population of CRM data from conversations
        </p>
      </div>

      {/* Status Card */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[var(--foreground)]">System Status</h2>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-sm text-[var(--foreground-muted)]">Active</span>
          </div>
        </div>
        <p className="text-sm text-[var(--foreground-muted)]">
          AUTO CRM is automatically processing all chat conversations to extract client information,
          practice intents, sentiment, and action items.
        </p>
      </div>

      {/* Statistics */}
      {isLoading ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
          <div className="text-sm text-[var(--foreground-muted)]">Loading statistics...</div>
        </div>
      ) : stats ? (
        <div className="space-y-6">
          {/* Overview Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-cyan-500" />
                <span className="text-sm font-medium text-[var(--foreground-muted)]">Total Extractions</span>
              </div>
              <div className="text-2xl font-bold text-[var(--foreground)]">{stats.total_extractions}</div>
            </div>

            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-4 h-4 text-green-500" />
                <span className="text-sm font-medium text-[var(--foreground-muted)]">Success Rate</span>
              </div>
              <div className={`text-2xl font-bold ${successRate >= 80 ? 'text-green-500' : successRate >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>
                {successRate}%
              </div>
            </div>

            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <span className="text-sm font-medium text-[var(--foreground-muted)]">Avg Confidence</span>
              </div>
              <div className={`text-2xl font-bold ${stats.extraction_confidence_avg && stats.extraction_confidence_avg >= 0.7 ? 'text-green-500' : stats.extraction_confidence_avg && stats.extraction_confidence_avg >= 0.5 ? 'text-yellow-500' : 'text-red-500'}`}>
                {stats.extraction_confidence_avg ? Math.round(stats.extraction_confidence_avg * 100) : 'N/A'}%
              </div>
            </div>
          </div>

          {/* Created Items */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Users className="w-4 h-4 text-blue-500" />
                <span className="text-sm font-medium text-[var(--foreground-muted)]">Clients Created</span>
              </div>
              <div className="text-2xl font-bold text-green-500">{stats.clients_created}</div>
              <div className="text-xs text-[var(--foreground-muted)] mt-1">
                {stats.clients_updated} updated
              </div>
            </div>

            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <FolderKanban className="w-4 h-4 text-orange-500" />
                <span className="text-sm font-medium text-[var(--foreground-muted)]">Practices Created</span>
              </div>
              <div className="text-2xl font-bold text-green-500">{stats.practices_created}</div>
            </div>

            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
              <div className="flex items-center gap-2 mb-2">
                <XCircle className="w-4 h-4 text-red-500" />
                <span className="text-sm font-medium text-[var(--foreground-muted)]">Failed Extractions</span>
              </div>
              <div className="text-2xl font-bold text-red-500">{stats.failed_extractions}</div>
            </div>
          </div>

          {/* Recent Activity */}
          <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
            <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">Recent Activity (Last 30 Days)</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="text-sm text-[var(--foreground-muted)] mb-2">Last 24 Hours</div>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Extractions:</span>
                    <span className="text-[var(--foreground)] font-medium">{stats.last_24h.extractions}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Clients:</span>
                    <span className="text-[var(--foreground)] font-medium">{stats.last_24h.clients}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Practices:</span>
                    <span className="text-[var(--foreground)] font-medium">{stats.last_24h.practices}</span>
                  </div>
                </div>
              </div>
              <div>
                <div className="text-sm text-[var(--foreground-muted)] mb-2">Last 7 Days</div>
                <div className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Extractions:</span>
                    <span className="text-[var(--foreground)] font-medium">{stats.last_7d.extractions}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Clients:</span>
                    <span className="text-[var(--foreground)] font-medium">{stats.last_7d.clients}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--foreground-muted)]">Practices:</span>
                    <span className="text-[var(--foreground)] font-medium">{stats.last_7d.practices}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Top Practice Types */}
          {stats.top_practice_types.length > 0 && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
              <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">Top Practice Types Extracted</h3>
              <div className="space-y-2">
                {stats.top_practice_types.map((type) => (
                  <div key={type.code} className="flex items-center justify-between p-3 rounded bg-[var(--background)]">
                    <span className="text-sm text-[var(--foreground)]">{type.name}</span>
                    <span className="text-sm font-medium text-[var(--foreground-muted)]">{type.count} extracted</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Information */}
          <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
            <h3 className="text-lg font-semibold text-[var(--foreground)] mb-3">How AUTO CRM Works</h3>
            <div className="space-y-2 text-sm text-[var(--foreground-muted)]">
              <p>
                <strong className="text-[var(--foreground)]">AI-Powered Extraction:</strong> When conversations are saved,
                AUTO CRM automatically extracts:
              </p>
              <ul className="list-disc list-inside ml-4 space-y-1">
                <li><strong>Client Info:</strong> Name, email, phone, nationality</li>
                <li><strong>Practice Intent:</strong> Service type (KITAS, PT PMA, Visa, etc.), urgency, details</li>
                <li><strong>Sentiment:</strong> Emotional tone of the conversation</li>
                <li><strong>Action Items:</strong> Next steps identified from the conversation</li>
              </ul>
              <p className="mt-3">
                <strong className="text-[var(--foreground)]">Automatic Actions:</strong> Based on extracted data,
                AUTO CRM automatically:
              </p>
              <ul className="list-disc list-inside ml-4 space-y-1">
                <li>Creates or updates client records</li>
                <li>Creates practice inquiries when service intent is detected</li>
                <li>Logs interactions with full conversation content</li>
              </ul>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
          <div className="text-sm text-[var(--foreground-muted)]">No statistics available yet.</div>
        </div>
      )}
    </div>
  );
}





