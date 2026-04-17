"use client";
import { useEffect } from "react";
import {
  getOrCreateSessionId,
  attachToServerSession,
} from "@balizero/core/auth";

type FunnelSlug = "visa" | "kbli" | "tax" | "property" | "home";

export function SessionInit({ funnel }: { funnel: FunnelSlug }) {
  useEffect(() => {
    getOrCreateSessionId();
    void attachToServerSession({ funnel });
  }, [funnel]);
  return null;
}
