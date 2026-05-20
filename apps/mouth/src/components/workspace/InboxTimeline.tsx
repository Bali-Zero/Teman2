"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  inboxApi,
  type InboxChannel,
  type InboxItem,
} from "@/lib/api/workspace/inbox.api";

const AUTO_REFRESH_MS = 5000;

const CHANNELS: Array<{ value: InboxChannel | ""; label: string }> = [
  { value: "", label: "Tutti i canali" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "telegram", label: "Telegram" },
  { value: "instagram", label: "Instagram" },
  { value: "web", label: "Web chat" },
  { value: "email", label: "Email" },
];

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function InboxTimeline() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [channel, setChannel] = useState<InboxChannel | "">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshAt, setLastRefreshAt] = useState<Date | null>(null);
  const inFlightRef = useRef(false);

  const fetchFeed = useCallback(
    async (currentChannel: InboxChannel | "", showLoading: boolean) => {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      if (showLoading) setLoading(true);
      try {
        const res = await inboxApi.feed({
          channel: currentChannel || undefined,
          limit: 100,
        });
        setItems(res.items);
        setError(null);
        setLastRefreshAt(new Date());
      } catch (err) {
        setError(String(err));
      } finally {
        if (showLoading) setLoading(false);
        inFlightRef.current = false;
      }
    },
    [],
  );

  useEffect(() => {
    void fetchFeed(channel, true);
    const tick = () => {
      if (document.visibilityState === "visible") {
        void fetchFeed(channel, false);
      }
    };
    const interval = window.setInterval(tick, AUTO_REFRESH_MS);
    const onVisibility = () => {
      if (document.visibilityState === "visible")
        void fetchFeed(channel, false);
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [channel, fetchFeed]);

  const groups = useMemo(() => {
    const map = new Map<string, InboxItem[]>();
    for (const it of items) {
      const day = it.created_at ? it.created_at.slice(0, 10) : "—";
      const bucket = map.get(day) ?? [];
      bucket.push(it);
      map.set(day, bucket);
    }
    return Array.from(map.entries()).sort(([a], [b]) => (a < b ? 1 : -1));
  }, [items]);

  return (
    <section
      aria-label="Omnichannel inbox"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-4, 16px)",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3, 12px)",
          borderBottom: "1px solid var(--color-border-subtle, #e5e7eb)",
          paddingBottom: "var(--space-3, 12px)",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "var(--font-size-xl, 20px)" }}>
          Inbox
        </h1>
        <span
          aria-live="polite"
          style={{
            fontSize: "var(--font-size-sm, 12px)",
            color: "var(--color-text-secondary, #6b7280)",
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <span
            aria-hidden
            style={{
              width: 8,
              height: 8,
              borderRadius: 4,
              background: error
                ? "var(--color-danger, #dc2626)"
                : "var(--color-success, #16a34a)",
              display: "inline-block",
            }}
          />
          Auto-refresh 5s
          {lastRefreshAt
            ? ` · last ${lastRefreshAt.toLocaleTimeString(undefined, {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}`
            : ""}
        </span>
        <label
          style={{
            marginLeft: "auto",
            display: "flex",
            gap: 8,
            alignItems: "center",
          }}
        >
          <span style={{ color: "var(--color-text-secondary, #6b7280)" }}>
            Canale
          </span>
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value as InboxChannel | "")}
            style={{
              padding: "6px 10px",
              borderRadius: 6,
              border: "1px solid var(--color-border-subtle, #e5e7eb)",
              background: "var(--color-surface, #fff)",
            }}
          >
            {CHANNELS.map((c) => (
              <option key={c.value || "all"} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </header>

      {loading ? (
        <p>Caricamento…</p>
      ) : error ? (
        <p role="alert" style={{ color: "var(--color-danger, #dc2626)" }}>
          Errore: {error}
        </p>
      ) : items.length === 0 ? (
        <p style={{ color: "var(--color-text-secondary, #6b7280)" }}>
          Nessun messaggio.
        </p>
      ) : (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-4, 16px)",
          }}
        >
          {groups.map(([day, bucket]) => (
            <section key={day} aria-label={day}>
              <h2
                style={{
                  fontSize: "var(--font-size-sm, 12px)",
                  textTransform: "uppercase",
                  color: "var(--color-text-secondary, #6b7280)",
                  letterSpacing: "0.05em",
                  margin: "0 0 8px",
                }}
              >
                {day}
              </h2>
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {bucket.map((it) => (
                  <li
                    key={it.id}
                    style={{
                      padding: "var(--space-3, 12px)",
                      borderBottom:
                        "1px solid var(--color-border-subtle, #e5e7eb)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 4,
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        color: "var(--color-text-secondary, #6b7280)",
                        fontSize: "var(--font-size-sm, 12px)",
                      }}
                    >
                      <span
                        style={{ textTransform: "uppercase", fontWeight: 600 }}
                      >
                        {it.channel}
                      </span>
                      <span>·</span>
                      <span>{formatTime(it.created_at)}</span>
                      <span>·</span>
                      <span>{it.client_name ?? "senza cliente"}</span>
                    </div>
                    <p style={{ margin: 0 }}>
                      <span aria-hidden style={{ marginRight: 6 }}>
                        {it.direction === "inbound" ? "→" : "←"}
                      </span>
                      {it.content}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </section>
  );
}
