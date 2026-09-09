"use client";

import { useState } from "react";
import styles from "./service-sections.module.css";

type PriceState = { status: "idle" | "loading" | "unavailable" } | { status: "ready"; price: string; verifiedOn: string | null };

export function ServicePrice({ serviceKey, name }: { serviceKey: string; name: string }) {
  const [state, setState] = useState<PriceState>({ status: "idle" });
  async function checkPrice() {
    setState({ status: "loading" });
    try {
      const response = await fetch(`/api/service-price?key=${encodeURIComponent(serviceKey)}`, {
        cache: "no-store", credentials: "omit", signal: AbortSignal.timeout(8000),
      });
      const result = await response.json();
      if (!response.ok || !result.available || typeof result.price !== "string") throw new Error("Unavailable");
      setState({ status: "ready", price: result.price, verifiedOn: result.verifiedOn ?? null });
    } catch {
      setState({ status: "unavailable" });
    }
  }
  return <div className={styles.price}>
    {state.status !== "ready" && <button type="button" disabled={state.status === "loading"} aria-label={`Check current price for ${name}`} onClick={checkPrice}>
      {state.status === "loading" ? "Checking…" : state.status === "unavailable" ? "Try price again" : "Check current price"}
    </button>}
    <span role="status">
      {state.status === "ready" && <><strong>{state.price}</strong>{state.verifiedOn && <small>Verified <time dateTime={state.verifiedOn}>{state.verifiedOn}</time></small>}</>}
      {state.status === "unavailable" && <small>Price unavailable. Request a quote.</small>}
    </span>
  </div>;
}
