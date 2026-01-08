'use client';

import React, { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, FolderKanban, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { logger } from '@/lib/logger';
import { useEnhancedAnalytics } from '@/lib/enhanced-analytics';

export default function ProjectsPage() {
  const router = useRouter();
  const pageLoadStartTime = useRef<number>(performance.now());
  const { trackPageView, trackUserInteraction, trackPerformance, trackEvent } = useEnhancedAnalytics();

  useEffect(() => {
    const loadTime = performance.now() - pageLoadStartTime.current;
    
    logger.componentMount('ProjectsPage', {
      component: 'ProjectsPage',
      action: 'mount',
      metadata: { loadTime: Math.round(loadTime) },
    });
    
    trackPageView('/knowledge/projects', 'Projects');
    trackPerformance({ loadTime });
    trackEvent('knowledge_projects_view', 'navigation', 'projects');

    return () => {
      logger.componentUnmount('ProjectsPage', {
        component: 'ProjectsPage',
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
              logger.userAction('back_to_our_journey', undefined, undefined, {
                component: 'ProjectsPage',
                action: 'back_navigation',
              });
              trackUserInteraction('click', 'back_button', 'projects');
              trackEvent('knowledge_back_click', 'navigation', 'projects');
              router.push('/knowledge/our-journey');
            }}
            className="flex items-center gap-2 text-sm text-[var(--foreground-muted)] hover:text-[var(--foreground)] mb-4 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Our Journey
          </button>
          <h1 className="text-3xl font-bold text-[var(--foreground)]">Projects</h1>
          <p className="text-[var(--foreground-muted)] mt-2 max-w-2xl">
            Discover our ongoing and completed projects. See how we've helped businesses establish and grow in Indonesia.
          </p>
        </div>
      </div>

      {/* Projects List */}
      <div className="space-y-6">
        {/* Project Card */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-6 hover:border-[var(--accent)]/30 transition-all">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-12 h-12 rounded-lg bg-[var(--accent)]/20 flex items-center justify-center">
                  <FolderKanban className="w-6 h-6 text-[var(--accent)]" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-[var(--foreground)]">Kutuh Villa Project</h3>
                  <p className="text-sm text-[var(--foreground-muted)]">Villa Development Project</p>
                </div>
              </div>
              <p className="text-[var(--foreground-muted)] mb-4">
                Complete project documentation for the Kutuh Villa development, including planning, 
                permits, and execution details.
              </p>
              <Button
                onClick={() => {
                  window.open('https://drive.google.com/uc?export=download&id=1eQUL2NudkDVNdpvPsaV8Owo5-G1CfpWt', '_blank');
                  
                  logger.userAction('project_download', undefined, 'kutuh-villa', {
                    component: 'ProjectsPage',
                    action: 'download',
                    metadata: { source: 'google_drive', fileId: '1eQUL2NudkDVNdpvPsaV8Owo5-G1CfpWt' },
                  });
                  
                  trackUserInteraction('download', 'project_pdf', 'kutuh-villa');
                  trackEvent('project_download', 'knowledge', 'kutuh-villa');
                }}
                variant="outline"
                className="gap-2 border-[var(--accent)]/30 text-[var(--accent)] hover:bg-[var(--accent)]/10"
              >
                <Download className="w-4 h-4" />
                Download Project PDF
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

