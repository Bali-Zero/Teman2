'use client';

import { PrimeNexusProvider, usePrimeNexus } from '@/contexts/PrimeNexusContext';
import PrimeMap3D from '@/components/maps/PrimeMap3D';
import { ModeSwitcher } from './ModeSwitcher';
import { InvestmentAnalysisPanel } from './InvestmentAnalysisPanel';
import { ClientMarkerLayer } from './ClientMarkerLayer';
import { CRMPanel } from './CRMPanel';
import { ComplianceOverlay } from './ComplianceOverlay';

/**
 * PrimeNexusLayout — Progressive enhancement wrapper around PrimeMap3D.
 *
 * Sprint 3 approach: adds mode switcher + investment analysis panel
 * WITHOUT rewriting PrimeMap3D. The original component continues to work
 * as-is; this layout overlays the new PRIME NEXUS features on top.
 *
 * Sprint 4 will add CRM/INTEL mode panels here.
 */
function PrimeNexusInner() {
  const { mode } = usePrimeNexus();

  return (
    <div className="h-screen bg-black overflow-hidden relative">
      {/* Original PrimeMap3D — unchanged, handles all map + sidebar logic */}
      <PrimeMap3D />

      {/* Headless intelligence data fetcher — active in CRM/INTEL mode */}
      <ClientMarkerLayer />

      {/* Mode Switcher — floating top-right */}
      <div className="absolute top-4 right-4 z-30">
        <ModeSwitcher />
      </div>

      {/* Investment Analysis Panel — floating bottom-left, only in INVEST mode */}
      {mode === 'invest' && (
        <div className="absolute bottom-4 left-4 z-30 w-80 max-h-[60vh] overflow-y-auto rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl">
          <InvestmentAnalysisPanel />
        </div>
      )}

      {/* CRM Mode — Sprint 4 */}
      {mode === 'crm' && (
        <div className="absolute bottom-4 left-4 z-30">
          <CRMPanel />
        </div>
      )}

      {/* Intel Mode — Sprint 4 */}
      {mode === 'intel' && (
        <div className="absolute bottom-4 left-4 z-30">
          <ComplianceOverlay />
        </div>
      )}
    </div>
  );
}

export default function PrimeNexusLayout() {
  return (
    <PrimeNexusProvider>
      <PrimeNexusInner />
    </PrimeNexusProvider>
  );
}
