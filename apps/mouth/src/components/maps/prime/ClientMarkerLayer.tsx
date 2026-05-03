'use client';

import { useEffect } from 'react';
import { usePrimeNexus } from '@/contexts/PrimeNexusContext';

/**
 * ClientMarkerLayer — fetches intelligence data when in CRM or INTEL mode.
 *
 * This is a headless layer component: it triggers `fetchIntelligence` when
 * bounds are set and mode is crm/intel, and exposes the loaded data via context.
 * Visual rendering is handled by CRMPanel and ComplianceOverlay respectively.
 */
export function ClientMarkerLayer() {
  const { mode, bounds, fetchIntelligence } = usePrimeNexus();

  useEffect(() => {
    if ((mode === 'crm' || mode === 'intel') && bounds) {
      fetchIntelligence(bounds);
    }
  }, [mode, bounds, fetchIntelligence]);

  // Headless — no DOM output
  return null;
}

/**
 * IntelligenceFeatureCount — inline badge showing count of loaded features.
 * Used inside panels to display "N results in viewport".
 */
export function IntelligenceFeatureCount() {
  const { intelligenceData, isLoadingIntelligence } = usePrimeNexus();

  if (isLoadingIntelligence) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-slate-400">
        <span className="w-3 h-3 border border-slate-500 border-t-[#d4845a] rounded-full animate-spin" />
        Loading...
      </span>
    );
  }

  const count = intelligenceData?.features?.length ?? 0;
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-accent-warm/20 text-accent-warm">
      {count} {count === 1 ? 'result' : 'results'}
    </span>
  );
}
