"use client";

import { useEffect, useState } from "react";

interface AvatarWithFallbackProps {
  /** Image URL. When falsy OR it fails to load (404/network), `fallback` renders instead. */
  src: string | null | undefined;
  alt: string;
  /** className applied to the rendered <img>. */
  className?: string;
  /**
   * What to show when there is no usable image (no src, or the src 404s).
   * Render a same-sized initials/icon placeholder here so the layout never shifts.
   */
  fallback: React.ReactNode;
}

/**
 * Renders an avatar image that degrades GRACEFULLY: if `src` is empty or the
 * image errors at load time (e.g. a team photo path drifted from .png to .jpg —
 * superscar: the 2026-06-15 cutover), it swaps to `fallback` instead of showing
 * the browser's broken-image glyph.
 *
 * A plain <img onError> is not enough on its own because we must STOP rendering
 * the broken <img> entirely; this component tracks the error in state and flips.
 */
export function AvatarWithFallback({
  src,
  alt,
  className,
  fallback,
}: AvatarWithFallbackProps) {
  const [errored, setErrored] = useState(false);

  // Reset the error flag if the src changes (e.g. reassignment to another member).
  useEffect(() => {
    setErrored(false);
  }, [src]);

  if (!src || errored) {
    return <>{fallback}</>;
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setErrored(true)}
    />
  );
}
