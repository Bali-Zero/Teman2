'use client';

import React, { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, FolderKanban, Briefcase } from 'lucide-react';
import { logger } from '@/lib/logger';
import { useEnhancedAnalytics } from '@/lib/enhanced-analytics';

export default function OurJourneyPage() {
  const router = useRouter();
  const pageLoadStartTime = useRef<number>(performance.now());
  const { trackPageView, trackUserInteraction, trackPerformance, trackEvent } = useEnhancedAnalytics();

  useEffect(() => {
    const loadTime = performance.now() - pageLoadStartTime.current;
    
    logger.componentMount('OurJourneyPage', {
      component: 'OurJourneyPage',
      action: 'mount',
      metadata: { loadTime: Math.round(loadTime) },
    });
    
    trackPageView('/knowledge/our-journey', 'Our Journey');
    trackPerformance({ loadTime });
    trackEvent('knowledge_our_journey_view', 'navigation', 'our_journey');

    return () => {
      logger.componentUnmount('OurJourneyPage', {
        component: 'OurJourneyPage',
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
                component: 'OurJourneyPage',
                action: 'back_navigation',
              });
              trackUserInteraction('click', 'back_button', 'our_journey');
              trackEvent('knowledge_back_click', 'navigation', 'our_journey');
              router.push('/knowledge');
            }}
            className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] mb-4 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Knowledge Base
          </button>
          <h1 className="text-3xl font-bold text-[var(--foreground)]">Our Journey</h1>
          <p className="text-[var(--foreground-muted)] mt-2 max-w-2xl">
            Explore our projects and cases to see our journey and milestones.
          </p>
        </div>
      </div>

      {/* Two Main Buttons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Projects Button */}
        <button
          onClick={() => {
            logger.userAction('projects_button_click', undefined, undefined, {
              component: 'OurJourneyPage',
              action: 'projects_navigation',
              metadata: { destination: '/knowledge/projects' },
            });
            trackUserInteraction('click', 'projects_button', 'our_journey');
            trackEvent('knowledge_projects_click', 'knowledge', 'projects');
            router.push('/knowledge/projects');
          }}
          className="group p-8 rounded-xl border-2 border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/5 to-purple-500/5 hover:border-[var(--accent)]/50 hover:shadow-lg hover:shadow-[var(--accent)]/10 transition-all duration-300 text-left"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-xl bg-[var(--accent)]/20 flex items-center justify-center group-hover:bg-[var(--accent)]/30 transition-colors">
              <FolderKanban className="w-8 h-8 text-[var(--accent)]" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--foreground)]">Projects</h2>
              <p className="text-sm text-[var(--foreground-muted)]">Our Projects</p>
            </div>
          </div>
          <p className="text-[var(--foreground-muted)]">
            Discover our ongoing and completed projects. See how we've helped businesses 
            establish and grow in Indonesia.
          </p>
          <div className="mt-4 flex items-center gap-2 text-[var(--accent)] group-hover:gap-3 transition-all">
            <span className="text-sm font-medium">View Projects</span>
            <ArrowLeft className="w-4 h-4 rotate-180" />
          </div>
        </button>

        {/* Cases Button */}
        <button
          onClick={() => {
            logger.userAction('cases_button_click', undefined, undefined, {
              component: 'OurJourneyPage',
              action: 'cases_navigation',
              metadata: { destination: '/cases' },
            });
            trackUserInteraction('click', 'cases_button', 'our_journey');
            trackEvent('knowledge_cases_click', 'knowledge', 'cases');
            router.push('/cases');
          }}
          className="group p-8 rounded-xl border-2 border-[var(--accent)]/30 bg-gradient-to-br from-[var(--accent)]/5 to-purple-500/5 hover:border-[var(--accent)]/50 hover:shadow-lg hover:shadow-[var(--accent)]/10 transition-all duration-300 text-left"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="w-16 h-16 rounded-xl bg-[var(--accent)]/20 flex items-center justify-center group-hover:bg-[var(--accent)]/30 transition-colors">
              <Briefcase className="w-8 h-8 text-[var(--accent)]" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--foreground)]">Cases</h2>
              <p className="text-sm text-[var(--foreground-muted)]">Client Cases</p>
            </div>
          </div>
          <p className="text-[var(--foreground-muted)]">
            Browse through our client cases and success stories. Learn from real examples 
            of businesses we've helped navigate Indonesian regulations.
          </p>
          <div className="mt-4 flex items-center gap-2 text-[var(--accent)] group-hover:gap-3 transition-all">
            <span className="text-sm font-medium">View Cases</span>
            <ArrowLeft className="w-4 h-4 rotate-180" />
          </div>
        </button>
      </div>
    </div>
  );
}

