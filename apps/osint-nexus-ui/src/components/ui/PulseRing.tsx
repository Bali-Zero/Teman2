'use client';

import { useState, useCallback, useEffect, useRef } from 'react';

interface PulseRingProps {
  containerRef: React.RefObject<HTMLElement | null>;
}

interface Ring {
  id: number;
  x: number;
  y: number;
}

export function PulseRing({ containerRef }: PulseRingProps) {
  const [rings, setRings] = useState<Ring[]>([]);
  const nextId = useRef(0);

  const handleClick = useCallback((e: MouseEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const id = nextId.current++;
    setRings((prev) => [...prev, { id, x, y }]);
    setTimeout(() => {
      setRings((prev) => prev.filter((r) => r.id !== id));
    }, 700);
  }, [containerRef]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    el.addEventListener('click', handleClick);
    return () => el.removeEventListener('click', handleClick);
  }, [containerRef, handleClick]);

  return (
    <>
      {rings.map((ring) => (
        <div key={ring.id} className="pointer-events-none" style={{ position: 'absolute', left: ring.x, top: ring.y, zIndex: 50 }}>
          <div
            className="absolute rounded-full border border-[var(--sg-copper)]"
            style={{
              transform: 'translate(-50%, -50%)',
              animation: 'pulse-ring-copper 400ms ease-out forwards',
            }}
          />
          <div
            className="absolute rounded-full border border-[var(--sg-periwinkle)]"
            style={{
              transform: 'translate(-50%, -50%)',
              animation: 'pulse-ring-periwinkle 600ms ease-out forwards',
            }}
          />
        </div>
      ))}
    </>
  );
}
