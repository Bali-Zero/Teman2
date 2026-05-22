"use client";

import { useEffect, useRef } from "react";
import { useInboxStore } from "@/lib/store";
import type { WaMessage } from "@/types/wa-message";

const STREAM_URL = "/api/v1/wa-dashboard/stream";
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30_000;

/**
 * Connects to the backend SSE stream and pushes incoming wa_message events
 * into the Zustand inbox store. Uses native EventSource (browser handles
 * Last-Event-ID header automatically on reconnect — devils-advocate v3 fix #11).
 */
export function useWaSse() {
  const setStatus = useInboxStore((s) => s.setStreamStatus);
  const pushMessage = useInboxStore((s) => s.pushMessage);
  const incrementError = useInboxStore((s) => s.incrementError);
  const esRef = useRef<EventSource | null>(null);
  const reconnectMsRef = useRef(RECONNECT_BASE_MS);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      setStatus("connecting");
      const es = new EventSource(STREAM_URL, { withCredentials: true });
      esRef.current = es;

      es.addEventListener("open", () => {
        setStatus("open");
        reconnectMsRef.current = RECONNECT_BASE_MS;
      });

      es.addEventListener("wa_message", (ev: MessageEvent<string>) => {
        try {
          const msg = JSON.parse(ev.data) as WaMessage;
          pushMessage(msg);
        } catch {
          incrementError();
        }
      });

      es.addEventListener("keepalive", () => {
        // No-op — just confirms the socket is alive.
      });

      es.addEventListener("error", () => {
        setStatus("error");
        incrementError();
        es.close();
        esRef.current = null;
        // Exponential backoff with jitter
        const delay = Math.min(
          reconnectMsRef.current + Math.random() * 500,
          RECONNECT_MAX_MS,
        );
        reconnectMsRef.current = Math.min(
          reconnectMsRef.current * 2,
          RECONNECT_MAX_MS,
        );
        timerRef.current = setTimeout(connect, delay);
      });
    };

    connect();

    return () => {
      cancelled = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      setStatus("closed");
    };
  }, [setStatus, pushMessage, incrementError]);
}
