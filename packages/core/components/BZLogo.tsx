/**
 * BZLogo — Unified logo component for the Bali Zero ecosystem.
 *
 * Replaces 29 ad-hoc <Image> imports scattered across apps/mouth with a single
 * source of truth. Supports all 6 logo variants currently in use.
 *
 * Usage:
 *   import { BZLogo } from '@bali-zero/core/components/BZLogo';
 *
 *   <BZLogo variant="clean" size={48} />           // Default clean logo
 *   <BZLogo variant="red" size={72} priority />    // Red variant, priority loading
 *   <BZLogo variant="lotus" size={32} />           // Zantara lotus
 *
 * Assets live in apps/mouth/public/assets/logo/. The component accepts a
 * `basePath` prop for non-mouth consumers (e.g. war-room, admin-dashboard)
 * that mirror the logo files into their own public directories.
 *
 * Last updated: 2026-04-11
 */

import React from 'react';

export type BZLogoVariant =
  | 'clean'     // balizero-logo-clean.png — default, transparent bg
  | 'red'       // balizero-3-red.png — red accent version
  | 'full'      // balizero-logo.png — full logo with wordmark
  | 'highres'   // balizero-logo-512.png — 512px high-resolution
  | 'map'       // balizeromap.svg — map icon (for Prime)
  | 'lotus'     // zantara-lotus.png — Zantara AI lotus avatar
  | 'zantara';  // logo_zan.png — Zantara workspace logo

export interface BZLogoProps {
  /**
   * Which logo asset to render.
   * Default: 'clean' (balizero-logo-clean.png)
   */
  variant?: BZLogoVariant;

  /**
   * Rendered size in pixels (both width and height — logos are square).
   * Default: 48
   */
  size?: number;

  /**
   * Accessible alt text.
   * Default: 'Bali Zero' (or 'Zantara' for zantara/lotus variants)
   */
  alt?: string;

  /**
   * CSS class name for additional styling.
   */
  className?: string;

  /**
   * Base path prefix for the logo asset.
   * Default: '/assets/logo' (apps/mouth convention).
   * Override only when consuming from a non-mouth app.
   */
  basePath?: string;

  /**
   * Preload this logo (for hero/above-fold usage).
   * Default: false
   */
  priority?: boolean;

  /**
   * Lazy loading strategy.
   * Default: 'lazy' (unless priority=true)
   */
  loading?: 'lazy' | 'eager';

  /**
   * Inline style override (use sparingly — prefer className).
   */
  style?: React.CSSProperties;

  /**
   * Click handler (for interactive logos, e.g. "return home").
   */
  onClick?: () => void;
}

const VARIANT_TO_FILENAME: Record<BZLogoVariant, string> = {
  clean: 'balizero-logo-clean.png',
  red: 'balizero-3-red.png',
  full: 'balizero-logo.png',
  highres: 'balizero-logo-512.png',
  map: 'balizeromap.svg',
  lotus: 'zantara-lotus.png',
  zantara: 'logo_zan.png',
};

const VARIANT_TO_DEFAULT_ALT: Record<BZLogoVariant, string> = {
  clean: 'Bali Zero',
  red: 'Bali Zero',
  full: 'Bali Zero',
  highres: 'Bali Zero',
  map: 'Bali Zero Map',
  lotus: 'Zantara',
  zantara: 'Zantara',
};

/**
 * Bali Zero unified logo component.
 *
 * Uses a plain <img> tag (not next/image) for maximum portability across apps.
 * Individual apps that want next/image optimization can wrap this component
 * or create a thin adapter — the contract stays the same.
 */
export function BZLogo({
  variant = 'clean',
  size = 48,
  alt,
  className,
  basePath = '/assets/logo',
  priority = false,
  loading,
  style,
  onClick,
}: BZLogoProps) {
  const filename = VARIANT_TO_FILENAME[variant];
  const src = `${basePath}/${filename}`;
  const resolvedAlt = alt ?? VARIANT_TO_DEFAULT_ALT[variant];
  const resolvedLoading = loading ?? (priority ? 'eager' : 'lazy');

  return (
    <img
      src={src}
      alt={resolvedAlt}
      width={size}
      height={size}
      loading={resolvedLoading}
      decoding={priority ? 'sync' : 'async'}
      fetchPriority={priority ? 'high' : 'auto'}
      className={className}
      style={{
        display: 'inline-block',
        objectFit: 'contain',
        ...style,
      }}
      onClick={onClick}
    />
  );
}

export default BZLogo;
