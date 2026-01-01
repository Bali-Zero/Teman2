'use client';

import React from 'react';
import { cn } from '@/lib/utils';

interface ShimmerButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  shimmerColor?: string;
  shimmerSize?: string;
  borderRadius?: string;
  shimmerDuration?: string;
  background?: string;
  className?: string;
}

/**
 * ShimmerButton - A button with a beautiful shimmer effect
 * Inspired by Magic UI
 *
 * Usage:
 * <ShimmerButton>Click me</ShimmerButton>
 */
export function ShimmerButton({
  children,
  shimmerColor = '#6366f1',
  shimmerSize = '0.1em',
  borderRadius = '12px',
  shimmerDuration = '2s',
  background = 'linear-gradient(110deg, #1a1a1a, 45%, #2a2a2a, 55%, #1a1a1a)',
  className,
  ...props
}: ShimmerButtonProps) {
  return (
    <button
      className={cn(
        'group relative inline-flex items-center justify-center overflow-hidden',
        'px-6 py-3 font-medium text-[var(--foreground)]',
        'transition-all duration-300 ease-out',
        'hover:scale-[1.02] active:scale-[0.98]',
        'disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100',
        className
      )}
      style={{
        borderRadius,
        background,
      }}
      {...props}
    >
      {/* Shimmer effect */}
      <span
        className="absolute inset-0 overflow-hidden"
        style={{ borderRadius }}
      >
        <span
          className="absolute inset-0 -translate-x-full animate-shimmer"
          style={{
            background: `linear-gradient(90deg, transparent, ${shimmerColor}40, transparent)`,
            animationDuration: shimmerDuration,
          }}
        />
      </span>

      {/* Border glow on hover */}
      <span
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300"
        style={{
          borderRadius,
          boxShadow: `0 0 20px ${shimmerColor}40, inset 0 0 0 1px ${shimmerColor}60`,
        }}
      />

      {/* Content */}
      <span className="relative z-10 flex items-center gap-2">
        {children}
      </span>
    </button>
  );
}

export default ShimmerButton;
