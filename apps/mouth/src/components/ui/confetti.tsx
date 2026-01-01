'use client';

import React, { useState, useEffect, useCallback } from 'react';
import ReactConfetti from 'react-confetti';

interface ConfettiProps {
  active: boolean;
  duration?: number;
  onComplete?: () => void;
}

/**
 * Confetti celebration component
 * Shows confetti explosion when active is true
 *
 * Usage:
 * const [showConfetti, setShowConfetti] = useState(false);
 * <Confetti active={showConfetti} onComplete={() => setShowConfetti(false)} />
 *
 * // Trigger: setShowConfetti(true)
 */
export function Confetti({ active, duration = 3000, onComplete }: ConfettiProps) {
  const [isActive, setIsActive] = useState(false);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    // Get window dimensions
    const updateDimensions = () => {
      setDimensions({
        width: window.innerWidth,
        height: window.innerHeight,
      });
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  useEffect(() => {
    if (active) {
      setIsActive(true);
      const timer = setTimeout(() => {
        setIsActive(false);
        onComplete?.();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [active, duration, onComplete]);

  if (!isActive) return null;

  return (
    <ReactConfetti
      width={dimensions.width}
      height={dimensions.height}
      recycle={false}
      numberOfPieces={300}
      gravity={0.3}
      colors={[
        '#6366f1', // accent (indigo)
        '#22c55e', // success (green)
        '#f59e0b', // warning (amber)
        '#3b82f6', // info (blue)
        '#ec4899', // pink
        '#8b5cf6', // purple
      ]}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: 9999,
        pointerEvents: 'none',
      }}
    />
  );
}

/**
 * Hook to trigger confetti
 *
 * Usage:
 * const { triggerConfetti, ConfettiComponent } = useConfetti();
 *
 * // In JSX: {ConfettiComponent}
 * // To trigger: triggerConfetti()
 */
export function useConfetti() {
  const [active, setActive] = useState(false);

  const triggerConfetti = useCallback(() => {
    setActive(true);
  }, []);

  const handleComplete = useCallback(() => {
    setActive(false);
  }, []);

  const ConfettiComponent = (
    <Confetti active={active} onComplete={handleComplete} />
  );

  return { triggerConfetti, ConfettiComponent, isActive: active };
}

export default Confetti;
