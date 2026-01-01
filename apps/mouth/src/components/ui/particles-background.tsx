'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Particles, { initParticlesEngine } from '@tsparticles/react';
import { loadSlim } from '@tsparticles/slim';
import type { ISourceOptions } from '@tsparticles/engine';

interface ParticlesBackgroundProps {
  className?: string;
  variant?: 'default' | 'connections' | 'snow' | 'stars';
  color?: string;
  quantity?: number;
}

/**
 * ParticlesBackground - Animated particle background
 *
 * Usage:
 * <ParticlesBackground variant="connections" />
 *
 * Place it as the first child of a relative-positioned container
 */
export function ParticlesBackground({
  className = '',
  variant = 'default',
  color = '#6366f1',
  quantity = 50,
}: ParticlesBackgroundProps) {
  const [init, setInit] = useState(false);

  useEffect(() => {
    initParticlesEngine(async (engine) => {
      await loadSlim(engine);
    }).then(() => {
      setInit(true);
    });
  }, []);

  const options: ISourceOptions = useMemo(() => {
    const baseOptions: ISourceOptions = {
      fullScreen: false,
      background: {
        color: {
          value: 'transparent',
        },
      },
      fpsLimit: 60,
      particles: {
        color: {
          value: color,
        },
        move: {
          enable: true,
          speed: 1,
          direction: 'none',
          random: true,
          straight: false,
          outModes: {
            default: 'out',
          },
        },
        number: {
          value: quantity,
          density: {
            enable: true,
          },
        },
        opacity: {
          value: { min: 0.1, max: 0.5 },
          animation: {
            enable: true,
            speed: 0.5,
            sync: false,
          },
        },
        size: {
          value: { min: 1, max: 3 },
        },
      },
      detectRetina: true,
    };

    // Variant-specific options
    if (variant === 'connections') {
      baseOptions.particles!.links = {
        enable: true,
        distance: 150,
        color: color,
        opacity: 0.2,
        width: 1,
      };
      baseOptions.interactivity = {
        events: {
          onHover: {
            enable: true,
            mode: 'grab',
          },
        },
        modes: {
          grab: {
            distance: 200,
            links: {
              opacity: 0.5,
            },
          },
        },
      };
    }

    if (variant === 'snow') {
      baseOptions.particles!.move = {
        enable: true,
        speed: 2,
        direction: 'bottom',
        straight: false,
        outModes: { default: 'out' },
      };
      baseOptions.particles!.wobble = {
        enable: true,
        distance: 10,
        speed: 10,
      };
    }

    if (variant === 'stars') {
      baseOptions.particles!.twinkle = {
        particles: {
          enable: true,
          frequency: 0.05,
          opacity: 1,
        },
      };
      baseOptions.particles!.move!.speed = 0.2;
    }

    return baseOptions;
  }, [variant, color, quantity]);

  if (!init) return null;

  return (
    <Particles
      id={`particles-${variant}`}
      className={`absolute inset-0 -z-10 ${className}`}
      options={options}
    />
  );
}

export default ParticlesBackground;
