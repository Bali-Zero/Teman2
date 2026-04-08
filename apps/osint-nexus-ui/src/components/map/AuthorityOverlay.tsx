'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { useLevel } from '@/hooks/useLevel';
import { useNeo4j } from '@/hooks/useNeo4j';
import type { OfficialDetail } from '@/lib/types';
import { formatRupiah } from '@/lib/format';
import { ObsidianPanel } from '@/components/ui/ObsidianPanel';
import { NeuralWeb } from '@/components/graph/NeuralWeb';
import { AssetECG } from '@/components/timeline/AssetECG';
import { DeltaBar } from '@/components/timeline/DeltaBar';
import { PropertyCards, VehicleCards } from '@/components/timeline/PropertyCard';

export function AuthorityOverlay() {
  const { state } = useLevel();
  const { data: officialDetail } = useNeo4j<OfficialDetail>(
    state.selectedOfficial
      ? `/api/graph/official/${encodeURIComponent(state.selectedOfficial)}`
      : null
  );

  const latestYear = officialDetail?.lhkpn_years[officialDetail.lhkpn_years.length - 1];
  const latestAssets = latestYear ? officialDetail?.assets_by_year[latestYear] : null;

  return (
    <div className="absolute inset-0 z-25">
      <NeuralWeb />

      <AnimatePresence>
      {officialDetail && state.selectedOfficial && (
        <motion.div
          key="official-detail"
          initial={{ x: 420, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 420, opacity: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="absolute right-4 top-16 bottom-12"
          style={{ width: 400, zIndex: 35 }}
        >
          <ObsidianPanel className="h-full overflow-y-auto p-5">
            <div className="mb-5">
              <div className="font-[family-name:var(--font-display)] text-[16px] font-semibold text-[var(--sg-text-primary)]">
                {officialDetail.profile.name}
              </div>
              <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-secondary)] mt-1">
                {officialDetail.profile.jabatan}
              </div>
              {officialDetail.profile.nip && (
                <div className="font-[family-name:var(--font-mono)] text-[10px] text-[var(--sg-text-ghost)] mt-0.5">
                  NIP: {officialDetail.profile.nip}
                </div>
              )}
            </div>

            {officialDetail.lhkpn_years.length > 0 && (
              <div className="mb-6">
                <AssetECG detail={officialDetail} />
              </div>
            )}

            {officialDetail.delta.length > 0 && (
              <div className="mb-6">
                <DeltaBar deltas={officialDetail.delta} />
              </div>
            )}

            {latestAssets && (
              <>
                <div className="mb-6">
                  <PropertyCards properties={latestAssets.properties} />
                </div>

                <div className="mb-6">
                  <VehicleCards vehicles={latestAssets.vehicles} />
                </div>

                {latestAssets.cash > 0 && (
                  <div className="mb-4">
                    <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-1">
                      CASH & EQUIVALENTS
                    </div>
                    <div className="font-[family-name:var(--font-mono)] text-[14px] text-[var(--sg-copper)]">
                      {formatRupiah(latestAssets.cash)}
                    </div>
                  </div>
                )}

                <div className="pt-4 border-t border-[var(--sg-border)]">
                  <div className="font-[family-name:var(--font-display)] text-[13px] font-semibold tracking-[0.12em] uppercase text-[var(--sg-text-secondary)] mb-1">
                    TOTAL DECLARED ({latestYear})
                  </div>
                  <div className="font-[family-name:var(--font-mono)] text-[18px] text-[var(--sg-copper)]">
                    {formatRupiah(latestAssets.total)}
                  </div>
                </div>
              </>
            )}

            {officialDetail.lhkpn_years.length === 0 && (
              <div className="text-center py-8">
                <div className="font-[family-name:var(--font-mono)] text-[11px] text-[var(--sg-text-ghost)]">
                  NO LHKPN DATA AVAILABLE
                </div>
              </div>
            )}
          </ObsidianPanel>
        </motion.div>
      )}
      </AnimatePresence>
    </div>
  );
}
