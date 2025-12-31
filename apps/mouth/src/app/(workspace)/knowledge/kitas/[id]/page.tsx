'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft,
  Clock,
  DollarSign,
  FileCheck,
  Star,
  Shield,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Lightbulb,
  ListOrdered,
  Wallet,
  Timer,
  RefreshCw,
  Sparkles,
  Share2,
  Printer,
  Download,
  Calendar,
  BadgeCheck,
  Ban,
  Activity,
  Gift,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { VisaType } from '@/lib/api/knowledge/visa.types';

// =============================================================================
// Helper Functions
// =============================================================================

function getDifficultyColor(difficulty: string | undefined): string {
  switch (difficulty) {
    case 'very_low':
      return 'text-emerald-400 bg-emerald-400/10 border-emerald-400/30';
    case 'low':
      return 'text-green-400 bg-green-400/10 border-green-400/30';
    case 'medium':
      return 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30';
    case 'high':
      return 'text-orange-400 bg-orange-400/10 border-orange-400/30';
    case 'very_high':
      return 'text-red-400 bg-red-400/10 border-red-400/30';
    default:
      return 'text-gray-400 bg-gray-400/10 border-gray-400/30';
  }
}

function getDifficultyLabel(difficulty: string | undefined): string {
  switch (difficulty) {
    case 'very_low':
      return 'Very Easy';
    case 'low':
      return 'Easy';
    case 'medium':
      return 'Medium';
    case 'high':
      return 'Difficult';
    case 'very_high':
      return 'Very Difficult';
    default:
      return 'Unknown';
  }
}

function getCategoryColor(category: string): string {
  switch (category) {
    case 'KITAS':
      return 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30';
    case 'KITAP':
      return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
    case 'Tourist':
      return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
    case 'Business':
      return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    default:
      return 'bg-gray-500/20 text-gray-300 border-gray-500/30';
  }
}

// =============================================================================
// Section Component
// =============================================================================

interface SectionProps {
  title: string;
  icon: React.ReactNode;
  iconBg: string;
  children: React.ReactNode;
}

function Section({ title, icon, iconBg, children }: SectionProps) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden">
      <div className="p-4 border-b border-[var(--border)] flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center`}>
          {icon}
        </div>
        <h2 className="text-lg font-semibold text-[var(--foreground)]">{title}</h2>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

// =============================================================================
// List Item Component
// =============================================================================

interface ListItemProps {
  text: string;
  icon: React.ReactNode;
  iconColor: string;
  index?: number;
}

function ListItem({ text, icon, iconColor, index }: ListItemProps) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-xl bg-[var(--background)]/50 hover:bg-[var(--background)]/80 transition-colors">
      <div className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${iconColor}`}>
        {index !== undefined ? (
          <span className="text-xs font-bold">{index}</span>
        ) : (
          icon
        )}
      </div>
      <span className="text-sm text-[var(--foreground-secondary)] leading-relaxed">{text}</span>
    </div>
  );
}

// =============================================================================
// Info Card Component
// =============================================================================

interface InfoCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  iconBg: string;
  subValue?: string;
}

function InfoCard({ label, value, icon, iconBg, subValue }: InfoCardProps) {
  return (
    <div className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center flex-shrink-0`}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs text-[var(--foreground-muted)] mb-1">{label}</p>
          <p className="text-base font-semibold text-[var(--foreground)] truncate">{value}</p>
          {subValue && (
            <p className="text-xs text-[var(--foreground-muted)] mt-1">{subValue}</p>
          )}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Page Component
// =============================================================================

export default function VisaDetailPage() {
  const router = useRouter();
  const params = useParams();
  const visaId = params.id as string;

  const [visa, setVisa] = useState<VisaType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (visaId) {
      loadVisa();
    }
  }, [visaId]);

  const loadVisa = async () => {
    try {
      setIsLoading(true);
      const response = await api.get<VisaType>(`/api/knowledge/visa/${visaId}`);
      setVisa(response);
      setError(null);
    } catch (err) {
      console.error('Failed to load visa:', err);
      setError('Visa not found or failed to load.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleShare = async () => {
    if (navigator.share && visa) {
      try {
        await navigator.share({
          title: visa.name,
          text: `Check out the ${visa.name} visa information from Bali Zero`,
          url: window.location.href,
        });
      } catch (err) {
        // User cancelled or error
      }
    } else {
      // Fallback: copy to clipboard
      navigator.clipboard.writeText(window.location.href);
      alert('Link copied to clipboard!');
    }
  };

  const handlePrint = () => {
    window.print();
  };

  // Loading State
  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-[var(--background-secondary)] rounded" />
        <div className="h-64 bg-[var(--background-secondary)] rounded-2xl" />
        <div className="grid md:grid-cols-2 gap-4">
          <div className="h-48 bg-[var(--background-secondary)] rounded-2xl" />
          <div className="h-48 bg-[var(--background-secondary)] rounded-2xl" />
        </div>
      </div>
    );
  }

  // Error State
  if (error || !visa) {
    return (
      <div className="p-12 rounded-2xl bg-[var(--background-secondary)] border border-[var(--border)] text-center">
        <AlertTriangle className="w-16 h-16 text-red-400 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-[var(--foreground)] mb-2">Visa Not Found</h2>
        <p className="text-[var(--foreground-muted)] mb-6">{error || 'The requested visa could not be found.'}</p>
        <Button onClick={() => router.push('/knowledge/kitas')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Visa List
        </Button>
      </div>
    );
  }

  const isRecommended = visa.metadata?.bali_zero_recommended;
  const isNew = visa.metadata?.new_visa;
  const difficulty = visa.metadata?.difficulty;

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      {/* Back Button */}
      <button
        onClick={() => router.push('/knowledge/kitas')}
        className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to KITAS & Visa Guide
      </button>

      {/* Header Card */}
      <div className="relative overflow-hidden rounded-2xl border border-[var(--border)] bg-gradient-to-br from-[var(--background-secondary)] to-[var(--background-elevated)]">
        {/* Badges */}
        <div className="absolute top-6 right-6 flex items-center gap-2">
          {isRecommended && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 text-white text-xs font-semibold shadow-lg">
              <Star className="w-3.5 h-3.5 fill-current" />
              Recommended
            </div>
          )}
          {isNew && (
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 text-white text-xs font-semibold shadow-lg">
              <Sparkles className="w-3.5 h-3.5" />
              New
            </div>
          )}
        </div>

        <div className="p-8">
          {/* Category & Difficulty */}
          <div className="flex items-center gap-3 mb-4">
            <span className={`px-3 py-1.5 text-sm font-medium rounded-full border ${getCategoryColor(visa.category)}`}>
              {visa.category}
            </span>
            {difficulty && (
              <span className={`px-3 py-1.5 text-sm font-medium rounded-full border ${getDifficultyColor(difficulty)}`}>
                {getDifficultyLabel(difficulty)}
              </span>
            )}
            {visa.renewable && (
              <span className="px-3 py-1.5 text-sm font-medium rounded-full border bg-blue-500/10 text-blue-300 border-blue-500/30">
                <RefreshCw className="w-3.5 h-3.5 inline mr-1" />
                Renewable
              </span>
            )}
          </div>

          {/* Title */}
          <h1 className="text-3xl md:text-4xl font-bold text-[var(--foreground)] mb-2">
            {visa.name}
          </h1>
          <p className="text-lg text-[var(--foreground-muted)] font-mono mb-6">
            Code: {visa.code}
          </p>

          {/* Quick Info Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <InfoCard
              label="Duration"
              value={visa.duration || 'Varies'}
              icon={<Clock className="w-5 h-5 text-[var(--accent)]" />}
              iconBg="bg-[var(--accent)]/10"
              subValue={visa.extensions || undefined}
            />
            <InfoCard
              label="Processing Time"
              value={visa.processing_time_normal || 'Varies'}
              icon={<Timer className="w-5 h-5 text-blue-400" />}
              iconBg="bg-blue-500/10"
              subValue={visa.processing_time_express ? `Express: ${visa.processing_time_express}` : undefined}
            />
            <InfoCard
              label="Bali Zero Price"
              value={visa.cost_visa || 'Contact us'}
              icon={<Wallet className="w-5 h-5 text-emerald-400" />}
              iconBg="bg-emerald-500/10"
              subValue={visa.cost_extension ? `Extension: ${visa.cost_extension}` : undefined}
            />
            <InfoCard
              label="Maximum Stay"
              value={visa.total_stay || 'Varies'}
              icon={<Calendar className="w-5 h-5 text-purple-400" />}
              iconBg="bg-purple-500/10"
            />
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 mt-6 pt-6 border-t border-[var(--border)]">
            <Button
              onClick={() => router.push('/chat')}
              className="gap-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white"
            >
              <Sparkles className="w-4 h-4" />
              Ask Zantara AI
            </Button>
            <Button variant="outline" onClick={handleShare} className="gap-2">
              <Share2 className="w-4 h-4" />
              Share
            </Button>
            <Button variant="outline" onClick={handlePrint} className="gap-2">
              <Printer className="w-4 h-4" />
              Print
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Requirements */}
        <Section
          title="Requirements"
          icon={<FileCheck className="w-5 h-5 text-[var(--accent)]" />}
          iconBg="bg-[var(--accent)]/10"
        >
          <div className="space-y-2">
            {visa.requirements.map((req, idx) => (
              <ListItem
                key={idx}
                text={req}
                icon={<BadgeCheck className="w-3.5 h-3.5" />}
                iconColor="bg-[var(--accent)]/20 text-[var(--accent)]"
              />
            ))}
          </div>
        </Section>

        {/* Benefits */}
        <Section
          title="Benefits"
          icon={<Gift className="w-5 h-5 text-emerald-400" />}
          iconBg="bg-emerald-500/10"
        >
          <div className="space-y-2">
            {visa.benefits.map((benefit, idx) => (
              <ListItem
                key={idx}
                text={benefit}
                icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                iconColor="bg-emerald-500/20 text-emerald-400"
              />
            ))}
          </div>
        </Section>

        {/* Allowed Activities */}
        <Section
          title="Allowed Activities"
          icon={<Activity className="w-5 h-5 text-blue-400" />}
          iconBg="bg-blue-500/10"
        >
          <div className="space-y-2">
            {visa.allowed_activities.map((activity, idx) => (
              <ListItem
                key={idx}
                text={activity}
                icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                iconColor="bg-blue-500/20 text-blue-400"
              />
            ))}
          </div>
        </Section>

        {/* Restrictions */}
        <Section
          title="Restrictions"
          icon={<Ban className="w-5 h-5 text-red-400" />}
          iconBg="bg-red-500/10"
        >
          <div className="space-y-2">
            {visa.restrictions.map((restriction, idx) => (
              <ListItem
                key={idx}
                text={restriction}
                icon={<XCircle className="w-3.5 h-3.5" />}
                iconColor="bg-red-500/20 text-red-400"
              />
            ))}
          </div>
        </Section>
      </div>

      {/* Process Steps - Full Width */}
      <Section
        title="Application Process"
        icon={<ListOrdered className="w-5 h-5 text-purple-400" />}
        iconBg="bg-purple-500/10"
      >
        <div className="space-y-3">
          {visa.process_steps.map((step, idx) => (
            <ListItem
              key={idx}
              text={step.replace(/^\d+\.\s*/, '')}
              icon={<span className="text-xs font-bold">{idx + 1}</span>}
              iconColor="bg-purple-500/20 text-purple-400"
              index={idx + 1}
            />
          ))}
        </div>
      </Section>

      {/* Tips & Advice - Full Width */}
      <Section
        title="Tips & Advice from Bali Zero"
        icon={<Lightbulb className="w-5 h-5 text-amber-400" />}
        iconBg="bg-amber-500/10"
      >
        <div className="space-y-3">
          {visa.tips.map((tip, idx) => (
            <ListItem
              key={idx}
              text={tip}
              icon={<Lightbulb className="w-3.5 h-3.5" />}
              iconColor="bg-amber-500/20 text-amber-400"
            />
          ))}
        </div>
      </Section>

      {/* Cost Details */}
      {visa.cost_details && Object.keys(visa.cost_details).length > 0 && (
        <Section
          title="Cost Breakdown"
          icon={<DollarSign className="w-5 h-5 text-emerald-400" />}
          iconBg="bg-emerald-500/10"
        >
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(visa.cost_details).map(([key, value]) => (
              <div key={key} className="p-4 rounded-xl bg-[var(--background)]/50 border border-[var(--border)]">
                <p className="text-xs text-[var(--foreground-muted)] mb-1">
                  {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </p>
                <p className="text-lg font-semibold text-[var(--foreground)]">{value}</p>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* CTA */}
      <div className="p-8 rounded-2xl bg-gradient-to-r from-[var(--accent)]/10 to-purple-500/10 border border-[var(--accent)]/20">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div>
            <h3 className="text-xl font-bold text-[var(--foreground)] mb-2">
              Ready to Apply for {visa.name}?
            </h3>
            <p className="text-[var(--foreground-secondary)]">
              Let Bali Zero handle your visa application. 98% success rate, transparent pricing.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={() => router.push('/chat')}
              className="gap-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white"
            >
              <Sparkles className="w-4 h-4" />
              Start Application
            </Button>
            <Button
              variant="outline"
              onClick={() => window.open('https://wa.me/6281234567890?text=Hi%20Bali%20Zero%2C%20I%20want%20to%20apply%20for%20' + encodeURIComponent(visa.name), '_blank')}
              className="gap-2"
            >
              WhatsApp Us
            </Button>
          </div>
        </div>
      </div>

      {/* Last Updated */}
      {visa.last_updated && (
        <p className="text-xs text-[var(--foreground-muted)] text-center">
          Last updated: {new Date(visa.last_updated).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
          })}
        </p>
      )}
    </div>
  );
}
