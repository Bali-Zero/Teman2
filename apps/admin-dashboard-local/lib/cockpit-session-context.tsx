"use client";

import { createContext, useContext } from "react";

interface CockpitSessionContextValue {
  authorization: string;
  relock: () => void;
}

const CockpitSessionContext = createContext<CockpitSessionContextValue | null>(
  null,
);

export function CockpitSessionProvider({
  token,
  relock,
  children,
}: {
  token: string;
  relock: () => void;
  children: React.ReactNode;
}) {
  return (
    <CockpitSessionContext.Provider
      value={{ authorization: `Bearer ${token}`, relock }}
    >
      {children}
    </CockpitSessionContext.Provider>
  );
}

export function useCockpitSession(): CockpitSessionContextValue {
  const session = useContext(CockpitSessionContext);
  if (!session) {
    throw new Error("cockpit session context is unavailable");
  }
  return session;
}
