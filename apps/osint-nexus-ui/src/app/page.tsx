'use client';

import { useState, useRef, useEffect } from 'react';
import { OrbitalMap } from '@/components/map/OrbitalMap';
import { ProvincialMap } from '@/components/map/ProvincialMap';
import { AuthorityOverlay } from '@/components/map/AuthorityOverlay';
import { TopBar } from '@/components/hud/TopBar';
import { StatusBar } from '@/components/hud/StatusBar';
import { LevelContext, useLevelReducer } from '@/hooks/useLevel';

export default function Home() {
  const levelCtx = useLevelReducer();
  const { level } = levelCtx.state;

  const [transitioning, setTransitioning] = useState(false);
  const prevLevel = useRef(levelCtx.state.level);

  useEffect(() => {
    const curr = levelCtx.state.level;
    if (prevLevel.current !== curr) {
      setTransitioning(true);
      const duration = prevLevel.current === 'orbital' ? 1800 : 1200;
      setTimeout(() => setTransitioning(false), duration);
      prevLevel.current = curr;
    }
  }, [levelCtx.state.level]);

  return (
    <LevelContext.Provider value={levelCtx}>
      <div className={`relative w-screen h-screen overflow-hidden bg-[var(--sg-base)] ${transitioning ? 'transition-dive' : ''}`}>
        <TopBar />
        <OrbitalMap />
        {(level === 'provincial' || level === 'authority') && <ProvincialMap />}
        {level === 'authority' && <AuthorityOverlay />}
        <StatusBar />
      </div>
    </LevelContext.Provider>
  );
}
