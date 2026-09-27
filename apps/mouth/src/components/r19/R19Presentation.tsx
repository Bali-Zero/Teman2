"use client";

import { createContext, useContext, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { isR19Route } from "./routePolicy";
import { R19_VARS } from "./presentation";
import styles from "./R19Presentation.module.css";

const R19Context = createContext(false);
export const useR19 = () => useContext(R19Context);

/** Full homepage owns its original scoped layout and typography. */
export function R19HomeProvider({ children }: { children: ReactNode }) {
  return <R19Context.Provider value={true}>{children}</R19Context.Provider>;
}

/**
 * Presentation only: server-rendered children retain their data and metadata.
 * `force` opts a subtree in regardless of `routePolicy` — the 404 boundaries
 * need it: an unmatched pathname (e.g. a typo'd single segment) never
 * satisfies `isR19Route`, so without `force` a not-found page would render
 * with the pre-R19 dark theme instead of this app's current design.
 */
export function R19Presentation({
  children,
  force,
}: {
  children: ReactNode;
  force?: boolean;
}) {
  const pathname = usePathname();
  const active = force || isR19Route(pathname);
  return (
    <R19Context.Provider value={active}>
      {active && (
        <>
          <link
            rel="preload"
            href="/fonts/fraunces-r19-latin.woff2"
            as="font"
            type="font/woff2"
            crossOrigin="anonymous"
            fetchPriority="low"
          />
          <link
            rel="preload"
            href="/fonts/manrope-r19-latin.woff2"
            as="font"
            type="font/woff2"
            crossOrigin="anonymous"
            fetchPriority="low"
          />
        </>
      )}
      <div
        data-presentation={active ? "r19" : undefined}
        className={active ? styles.root : undefined}
        style={active ? R19_VARS : undefined}
      >
        {children}
      </div>
    </R19Context.Provider>
  );
}
