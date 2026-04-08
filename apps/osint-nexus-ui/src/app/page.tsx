'use client';

import { OrbitalMap } from '@/components/map/OrbitalMap';
import { ProvincialMap } from '@/components/map/ProvincialMap';
import { AuthorityOverlay } from '@/components/map/AuthorityOverlay';
import { TopBar } from '@/components/hud/TopBar';
import { StatusBar } from '@/components/hud/StatusBar';
import { LevelContext, useLevelReducer } from '@/hooks/useLevel';

export default function Home() {
  const levelCtx = useLevelReducer();
  const { level } = levelCtx.state;

  return (
    <LevelContext.Provider value={levelCtx}>
      <div className="relative w-screen h-screen overflow-hidden bg-[var(--sg-base)]">
        <TopBar />
        <OrbitalMap />
        {(level === 'provincial' || level === 'authority') && <ProvincialMap />}
        {level === 'authority' && <AuthorityOverlay />}
        <StatusBar />
      </div>
    </LevelContext.Provider>
  );
}
