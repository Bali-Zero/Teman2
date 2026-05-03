"use client";

import { useEffect, useRef } from "react";

interface HomepageStaticContentProps {
  html: string;
}

/**
 * Client component that mounts raw HTML after hydration.
 * Avoids React #418 hydration mismatch caused by dangerouslySetInnerHTML
 * with interactive onclick attributes in Server Components.
 */
export function HomepageStaticContent({ html }: HomepageStaticContentProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (ref.current) {
      ref.current.innerHTML = html;
    }
  }, [html]);

  return <div ref={ref} suppressHydrationWarning />;
}
