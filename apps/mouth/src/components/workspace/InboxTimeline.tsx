"use client";

import { useEffect, useMemo, useState } from "react";
import {
  inboxApi,
  type InboxChannel,
  type InboxItem,
} from "@/lib/api/workspace/inbox.api";

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

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    inboxApi
      .feed({ channel: channel || undefined, limit: 100 })
      .then((res) => {
        if (!cancelled) setItems(res.items);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [channel]);

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
        <h1 style={{ margin: 0, fontSize: "var(--font-size-xl, 20px)" }}>Inbox</h1>
        <label style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ color: "var(--color-text-secondary, #6b7280)" }}>Canale</span>
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
        <p style={{ color: "var(--color-text-secondary, #6b7280)" }}>Nessun messaggio.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4, 16px)" }}>
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
                      borderBottom: "1px solid var(--color-border-subtle, #e5e7eb)",
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
                      <span style={{ textTransform: "uppercase", fontWeight: 600 }}>
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
