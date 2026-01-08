'use client';

import React, { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Building2, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { logger } from '@/lib/logger';
import { useEnhancedAnalytics } from '@/lib/enhanced-analytics';

export default function CompanyLicensesPage() {
  const router = useRouter();
  const pageLoadStartTime = useRef<number>(performance.now());
  const { trackPageView, trackUserInteraction, trackPerformance, trackEvent } = useEnhancedAnalytics();

  useEffect(() => {
    const loadTime = performance.now() - pageLoadStartTime.current;
    
    logger.componentMount('CompanyLicensesPage', {
      component: 'CompanyLicensesPage',
      action: 'mount',
      metadata: { loadTime: Math.round(loadTime) },
    });
    
    trackPageView('/knowledge/company-licenses', 'Company & Licenses');
    trackPerformance({ loadTime });
    trackEvent('knowledge_company_licenses_view', 'navigation', 'company_licenses');

    return () => {
      logger.componentUnmount('CompanyLicensesPage', {
        component: 'CompanyLicensesPage',
        action: 'unmount',
      });
    };
  }, []);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => {
              logger.userAction('back_to_knowledge', undefined, undefined, {
                component: 'CompanyLicensesPage',
                action: 'back_navigation',
              });
              trackUserInteraction('click', 'back_button', 'company_licenses');
              trackEvent('knowledge_back_click', 'navigation', 'company_licenses');
              router.push('/knowledge');
            }}
            className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] mb-4 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Knowledge Base
          </button>
          <h1 className="text-3xl font-bold text-[var(--foreground)]">Company & Licenses</h1>
          <p className="text-[var(--foreground-muted)] mt-2 max-w-2xl">
            Choose between Company setup guides (KBLI blueprints) or Business Licenses information.
          </p>
        </div>
      </div>

      {/* Two Main Buttons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Company Button */}
        <button
          onClick={() => {
            logger.userAction('company_button_click', undefined, undefined, {
              component: 'CompanyLicensesPage',
              action: 'company_navigation',
              metadata: { destination: '/knowledge/blueprints' },
            });
            trackUserInteraction('click', 'company_button', 'company_licenses');
            trackEvent('knowledge_company_click', 'knowledge', 'company_blueprints');
            router.push('/knowledge/blueprints');
          }}
          className="group p-8 rounded-xl border-2 border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/5 to-purple-500/5 hover:border-[var(--accent)]/50 hover:shadow-lg hover:shadow-[var(--accent)]/10 transition-all duration-300 text-left"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-xl bg-[var(--accent)]/20 flex items-center justify-center group-hover:bg-[var(--accent)]/30 transition-colors">
              <Building2 className="w-8 h-8 text-[var(--accent)]" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--foreground)]">Company</h2>
              <p className="text-sm text-[var(--foreground-muted)]">KBLI Blueprints</p>
            </div>
          </div>
          <p className="text-[var(--foreground-muted)]">
            Comprehensive KBLI business classification blueprints based on PP 28/2025. 
            Download guides for starting your business in Indonesia.
          </p>
          <div className="mt-4 flex items-center gap-2 text-[var(--accent)] group-hover:gap-3 transition-all">
            <span className="text-sm font-medium">View KBLI Blueprints</span>
            <ArrowLeft className="w-4 h-4 rotate-180" />
          </div>
        </button>

        {/* Licenses Button */}
        <button
          onClick={() => {
            logger.userAction('licenses_button_click', undefined, undefined, {
              component: 'CompanyLicensesPage',
              action: 'licenses_navigation',
              metadata: { destination: '/knowledge/licenses' },
            });
            trackUserInteraction('click', 'licenses_button', 'company_licenses');
            trackEvent('knowledge_licenses_click', 'knowledge', 'business_licenses');
            router.push('/knowledge/licenses');
          }}
          className="group p-8 rounded-xl border-2 border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/5 to-purple-500/5 hover:border-[var(--accent)]/50 hover:shadow-lg hover:shadow-[var(--accent)]/10 transition-all duration-300 text-left"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-xl bg-[var(--accent)]/20 flex items-center justify-center group-hover:bg-[var(--accent)]/30 transition-colors">
              <FileText className="w-8 h-8 text-[var(--accent)]" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--foreground)]">Licenses</h2>
              <p className="text-sm text-[var(--foreground-muted)]">Business Licenses</p>
            </div>
          </div>
          <p className="text-[var(--foreground-muted)]">
            Essential licenses for F&B and food businesses in Indonesia. SLHS, NPBBKC (alcohol),
            Halal certification, and more - with Bali Zero 2026 prices.
          </p>
          <div className="mt-4 flex items-center gap-2 text-[var(--accent)] group-hover:gap-3 transition-all">
            <span className="text-sm font-medium">View Licenses Guide</span>
            <ArrowLeft className="w-4 h-4 rotate-180" />
          </div>
        </button>
      </div>
    </div>
  );
}

