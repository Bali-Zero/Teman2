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

/** Presentation only: server-rendered children retain their data and metadata. */
export function R19Presentation({ children }: { children: ReactNode }) {
  const active = isR19Route(usePathname());
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
