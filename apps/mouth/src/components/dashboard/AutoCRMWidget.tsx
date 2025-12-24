'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Sparkles, Users, FolderKanban, TrendingUp, CheckCircle2, XCircle, Activity, Plus, UserPlus, ArrowRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { AutoCRMStats } from '@/lib/api/crm/crm.types';
import type { CreateClientParams } from '@/lib/api/crm/crm.types';

interface AutoCRMWidgetProps {
  className?: string;
}

export function AutoCRMWidget({ className }: AutoCRMWidgetProps) {
  const router = useRouter();
  const [stats, setStats] = useState<AutoCRMStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showQuickCreate, setShowQuickCreate] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [quickForm, setQuickForm] = useState<CreateClientParams>({
    full_name: '',
    email: '',
    phone: '',
    nationality: '',
  });

  useEffect(() => {
    const loadStats = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await api.crm.getAutoCRMStats(7);
        setStats(data);
      } catch (err) {
        console.error('Failed to load AUTO CRM stats:', err);
        setError('Failed to load statistics');
      } finally {
        setIsLoading(false);
      }
    };

    loadStats();
    // Refresh every 5 minutes
    const interval = setInterval(loadStats, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  const handleQuickCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!quickForm.full_name.trim()) {
      alert('Name is required');
      return;
    }

    setIsCreating(true);
    try {
      const user = await api.getProfile();
      await api.crm.createClient(quickForm, user.email);
      setQuickForm({ full_name: '', email: '', phone: '', nationality: '' });
      setShowQuickCreate(false);
      // Reload stats
      const data = await api.crm.getAutoCRMStats(7);
      setStats(data);
      // Navigate to clients page
      router.push('/clienti');
    } catch (err) {
      console.error('Failed to create client:', err);
      const message = err instanceof Error ? err.message : 'Unknown error';
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const detail = (err as any).detail;
      alert(`Failed to create client: ${detail || message}`);
    } finally {
      setIsCreating(false);
    }
  };

  if (isLoading && !stats) {
    return (
      <div className={`rounded-lg border border-white/10 bg-white/5 p-6 backdrop-blur-sm ${className || ''}`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            AUTO CRM
          </h3>
        </div>
        <div className="text-sm text-white/60">Loading statistics...</div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className={`rounded-lg border border-red-500/20 bg-red-500/10 p-6 backdrop-blur-sm ${className || ''}`}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            AUTO CRM
          </h3>
        </div>
        <div className="text-sm text-red-400">{error}</div>
      </div>
    );
  }

  if (!stats) return null;

  const successRate = stats.total_extractions > 0 
    ? Math.round((stats.successful_extractions / stats.total_extractions) * 100)
    : 0;

  return (
    <div className={`rounded-lg border border-white/10 bg-white/5 p-6 backdrop-blur-sm ${className || ''}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white/90 uppercase tracking-wider flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-purple-400" />
          AUTO CRM
        </h3>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-white/60">Active</span>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mb-4 flex gap-2">
        <Button
          size="sm"
          variant="outline"
          className="flex-1 bg-white/5 border-white/10 text-white hover:bg-white/10"
          onClick={() => router.push('/clienti/nuovo')}
        >
          <UserPlus className="w-3 h-3 mr-1" />
          New Client
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="flex-1 bg-white/5 border-white/10 text-white hover:bg-white/10"
          onClick={() => router.push('/pratiche')}
        >
          <FolderKanban className="w-3 h-3 mr-1" />
          Practices
        </Button>
      </div>

      {/* Quick Create Form */}
      {showQuickCreate && (
        <div className="mb-4 p-3 rounded bg-white/5 border border-white/10">
          <form onSubmit={handleQuickCreate} className="space-y-2">
            <input
              type="text"
              placeholder="Full Name *"
              value={quickForm.full_name}
              onChange={(e) => setQuickForm({ ...quickForm, full_name: e.target.value })}
              className="w-full px-2 py-1 text-sm rounded bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:ring-1 focus:ring-purple-400"
              required
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="email"
                placeholder="Email"
                value={quickForm.email}
                onChange={(e) => setQuickForm({ ...quickForm, email: e.target.value })}
                className="px-2 py-1 text-sm rounded bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:ring-1 focus:ring-purple-400"
              />
              <input
                type="tel"
                placeholder="Phone"
                value={quickForm.phone}
                onChange={(e) => setQuickForm({ ...quickForm, phone: e.target.value })}
                className="px-2 py-1 text-sm rounded bg-white/5 border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:ring-1 focus:ring-purple-400"
              />
            </div>
            <div className="flex gap-2">
              <Button
                type="submit"
                size="sm"
                className="flex-1 bg-purple-500 hover:bg-purple-600"
                disabled={isCreating}
              >
                {isCreating ? (
                  <>
                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="w-3 h-3 mr-1" />
                    Create
                  </>
                )}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="bg-white/5 border-white/10 text-white hover:bg-white/10"
                onClick={() => {
                  setShowQuickCreate(false);
                  setQuickForm({ full_name: '', email: '', phone: '', nationality: '' });
                }}
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {!showQuickCreate && (
        <Button
          size="sm"
          variant="ghost"
          className="w-full mb-4 bg-white/5 hover:bg-white/10 text-white"
          onClick={() => setShowQuickCreate(true)}
        >
          <Plus className="w-3 h-3 mr-1" />
          Quick Create Client
        </Button>
      )}

      <div className="space-y-4">
        {/* Success Rate */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-500" />
            <span className="text-sm text-white/80">Success Rate</span>
          </div>
          <span className={`text-sm font-medium ${successRate >= 80 ? 'text-green-400' : successRate >= 60 ? 'text-yellow-400' : 'text-red-400'}`}>
            {successRate}%
          </span>
        </div>

        {/* Total Extractions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-white/80">Total Extractions</span>
          </div>
          <span className="text-sm font-medium text-white/90">{stats.total_extractions}</span>
        </div>

        {/* Clients Created */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-4 h-4 text-blue-400" />
            <span className="text-sm text-white/80">Clients Created</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-green-400">{stats.clients_created}</span>
            {stats.clients_created > 0 && (
              <button
                onClick={() => router.push('/clienti')}
                className="text-xs text-white/60 hover:text-white/90 transition-colors"
              >
                <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Practices Created */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderKanban className="w-4 h-4 text-orange-400" />
            <span className="text-sm text-white/80">Practices Created</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-green-400">{stats.practices_created}</span>
            {stats.practices_created > 0 && (
              <button
                onClick={() => router.push('/pratiche')}
                className="text-xs text-white/60 hover:text-white/90 transition-colors"
              >
                <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
        </div>

        {/* Last 24h Activity */}
        <div className="pt-2 border-t border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">Last 24h</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="text-white/60">Extractions</div>
              <div className="text-white/90 font-medium">{stats.last_24h.extractions}</div>
            </div>
            <div>
              <div className="text-white/60">Clients</div>
              <div className="text-white/90 font-medium">{stats.last_24h.clients}</div>
            </div>
            <div>
              <div className="text-white/60">Practices</div>
              <div className="text-white/90 font-medium">{stats.last_24h.practices}</div>
            </div>
          </div>
        </div>

        {/* Confidence Score */}
        {stats.extraction_confidence_avg !== null && (
          <div className="flex items-center justify-between pt-2 border-t border-white/10">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              <span className="text-sm text-white/80">Avg Confidence</span>
            </div>
            <span className={`text-sm font-medium ${stats.extraction_confidence_avg >= 0.7 ? 'text-green-400' : stats.extraction_confidence_avg >= 0.5 ? 'text-yellow-400' : 'text-red-400'}`}>
              {Math.round(stats.extraction_confidence_avg * 100)}%
            </span>
          </div>
        )}

        {/* Recent Extractions */}
        {stats.recent_extractions.length > 0 && (
          <div className="pt-2 border-t border-white/10">
            <div className="text-xs font-semibold text-white/70 uppercase tracking-wider mb-2">
              Recent Extractions
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {stats.recent_extractions.slice(0, 3).map((extraction) => (
                <div
                  key={extraction.id}
                  className="text-xs p-2 rounded bg-white/5 hover:bg-white/10 cursor-pointer transition-colors"
                  onClick={() => {
                    if (extraction.client_id) {
                      router.push(`/clienti/${extraction.client_id}`);
                    } else if (extraction.practice_id) {
                      router.push(`/pratiche/${extraction.practice_id}`);
                    }
                  }}
                >
                  <div className="text-white/90 truncate">
                    {extraction.client_name || extraction.summary || 'Extraction'}
                  </div>
                  {extraction.practice_type_code && (
                    <div className="text-white/60 text-[10px] mt-0.5">
                      {extraction.practice_type_code}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Quick Links */}
        <div className="pt-2 border-t border-white/10">
          <div className="flex gap-2">
            <button
              onClick={() => router.push('/clienti')}
              className="flex-1 text-xs px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-white/80 hover:text-white transition-colors"
            >
              View All Clients
            </button>
            <button
              onClick={() => router.push('/pratiche')}
              className="flex-1 text-xs px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-white/80 hover:text-white transition-colors"
            >
              View Practices
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
