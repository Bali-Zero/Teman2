"use client";

import { Suspense } from "react";
import dynamic from "next/dynamic";
import {
  PrimeNexusProvider,
  usePrimeNexus,
} from "@/contexts/PrimeNexusContext";
import { PrimeMapSkeleton } from "./PrimeMapSkeleton";
import { PrimeUrlStateBridge } from "./PrimeUrlStateBridge";
import { PrimeLayerLegend } from "./PrimeLayerLegend";
import { PrimeCompareDrawer } from "./PrimeCompareDrawer";
import { ModeSwitcher } from "./ModeSwitcher";
import { ClientMarkerLayer } from "./ClientMarkerLayer";

// PF3a — dynamic split: PrimeMap3D (~1,179 LOC) + maps3d loader out of initial bundle
const PrimeMap3D = dynamic(() => import("@/components/maps/PrimeMap3D"), {
  ssr: false,
  loading: () => <PrimeMapSkeleton />,
});

// Code-split mode panels — only loaded when their mode is active
const InvestmentAnalysisPanel = dynamic(
  () =>
    import("./InvestmentAnalysisPanel").then((m) => ({
      default: m.InvestmentAnalysisPanel,
    })),
  { ssr: false },
);
const CRMPanel = dynamic(
  () => import("./CRMPanel").then((m) => ({ default: m.CRMPanel })),
  {
    ssr: false,
  },
);
const ComplianceOverlay = dynamic(
  () =>
    import("./ComplianceOverlay").then((m) => ({
      default: m.ComplianceOverlay,
    })),
  { ssr: false },
);
const TemporalPanel = dynamic(
  () => import("./TemporalPanel").then((m) => ({ default: m.TemporalPanel })),
  { ssr: false },
);
const RegulationPanel = dynamic(
  () =>
    import("./RegulationPanel").then((m) => ({ default: m.RegulationPanel })),
  { ssr: false },
);
const PortfolioPanel = dynamic(
  () => import("./PortfolioPanel").then((m) => ({ default: m.PortfolioPanel })),
  { ssr: false },
);

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
  const { mode, analysis } = usePrimeNexus();

  return (
    <div className="h-screen bg-black overflow-hidden relative">
      {/* PF3a — headless URL ↔ context sync */}
      <PrimeUrlStateBridge />

      {/* Original PrimeMap3D — unchanged, handles all map + sidebar logic */}
      <PrimeMap3D />

      {/* Headless intelligence data fetcher — active in CRM/INTEL mode */}
      <ClientMarkerLayer />

      {/* PF3a — interactive layer legend (top-left) */}
      <PrimeLayerLegend />

      {/* PF3a — compare drawer (top-right, hidden when empty) */}
      <PrimeCompareDrawer />

      {/* Mode Switcher — floating top-right */}
      <div className="absolute top-4 right-4 z-30">
        <ModeSwitcher />
      </div>

      {/* Investment Analysis Panel — floating bottom-left, only in INVEST mode */}
      {mode === "invest" && (
        <div className="absolute bottom-4 left-4 z-30 w-80 max-h-[60vh] overflow-y-auto rounded-2xl bg-black/90 backdrop-blur-xl border border-white/10 shadow-2xl">
          <InvestmentAnalysisPanel />
        </div>
      )}

      {/* CRM Mode — Sprint 4 */}
      {mode === "crm" && (
        <div className="absolute bottom-4 left-4 z-30">
          <CRMPanel />
        </div>
      )}

      {/* Intel Mode — Regulation feed + Compliance overlay */}
      {mode === "intel" && (
        <div className="absolute bottom-4 left-4 z-30 flex gap-3">
          <RegulationPanel />
          <ComplianceOverlay />
        </div>
      )}

      {/* Temporal Mode */}
      {mode === "temporal" && (
        <div className="absolute bottom-4 left-4 z-30">
          <TemporalPanel
            zoneCode={
              analysis?.zone?.zone_code ? String(analysis.zone.zone_code) : null
            }
          />
        </div>
      )}

      {/* Portfolio Mode */}
      {mode === "portfolio" && (
        <div className="absolute bottom-4 left-4 z-30">
          <PortfolioPanel clientId={null} />
        </div>
      )}
    </div>
  );
}

import type { PrimeMode } from "@/contexts/PrimeNexusContext";

export interface PrimeNexusLayoutProps {
  initialMode?: PrimeMode;
}

export default function PrimeNexusLayout({
  initialMode,
}: PrimeNexusLayoutProps = {}) {
  return (
    <PrimeNexusProvider initialMode={initialMode}>
      <Suspense fallback={<PrimeMapSkeleton />}>
        <PrimeNexusInner />
      </Suspense>
    </PrimeNexusProvider>
  );
}
