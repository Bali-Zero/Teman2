"use client";

/**
 * SafeHydrate Component
 *
 * Prevents hydration mismatch errors
 */

import { useEffect, useState, ReactNode } from "react";

interface SafeHydrateProps {
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Only render children after hydration is complete
 */
export function SafeHydrate({ children, fallback = null }: SafeHydrateProps) {
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  if (!isHydrated) {
    return fallback;
  }

  return children;
}

/**
 * Render different content on server vs client
 */
export function ClientOnly({ children, fallback = null }: SafeHydrateProps) {
  return <SafeHydrate children={children} fallback={fallback} />;
}

/**
 * Render different content on server vs client with explicit server content
 */
export function ServerClientSplit({
  serverContent,
  clientContent,
}: {
  serverContent: ReactNode;
  clientContent: ReactNode;
}) {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  return isClient ? clientContent : serverContent;
}
