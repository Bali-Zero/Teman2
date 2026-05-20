"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  MessageCircle,
  AlertTriangle,
  Image as ImageIcon,
  Mic,
  FileText,
  Paperclip,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type {
  WaMirrorMessage,
  WaMirrorMessagesResponse,
} from "@/lib/api/whatsapp/whatsapp.types";

const PRIORITY_STYLES: Record<
  string,
  { bg: string; text: string; border: string }
> = {
  HIGH: {
    bg: "bg-red-500/15",
    text: "text-red-300",
    border: "border-red-500/60",
  },
  MEDIUM: {
    bg: "bg-yellow-500/10",
    text: "text-yellow-300",
    border: "border-yellow-500/40",
  },
  LOW: {
    bg: "bg-gray-500/10",
    text: "text-gray-400",
    border: "border-gray-500/30",
  },
};

function MediaIcon({ type }: { type: string }) {
  const cls = "w-3.5 h-3.5";
  if (type.startsWith("image")) return <ImageIcon className={cls} />;
  if (type.startsWith("audio")) return <Mic className={cls} />;
  if (type.startsWith("video")) return <FileText className={cls} />;
  if (type === "text") return null;
  return <Paperclip className={cls} />;
}

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("it-IT", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function WaTimelineTab({
  clientId,
  practiceId,
}: {
  clientId?: number;
  practiceId?: number;
}) {
  const [messages, setMessages] = useState<WaMirrorMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (clientId == null && practiceId == null) {
        setMessages([]);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res: WaMirrorMessagesResponse =
          await api.whatsapp.getMirrorMessages({
            clientId,
            practiceId,
            limit: 50,
            offset: 0,
          });
        if (cancelled) return;
        setMessages(res.items);
        setOffset(res.items.length);
        setHasMore(res.items.length >= res.limit);
      } catch (e) {
        logger.error("WaTimelineTab load failed: " + String(e));
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [clientId, practiceId]);

  async function loadMore() {
    if (loading || !hasMore) return;
    setLoading(true);
    try {
      const res = await api.whatsapp.getMirrorMessages({
        clientId,
        practiceId,
        limit: 50,
        offset,
      });
      setMessages((prev) => [...prev, ...res.items]);
      setOffset(offset + res.items.length);
      setHasMore(res.items.length >= res.limit);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  const stats = useMemo(() => {
    const total = messages.length;
    const inbound = messages.filter((m) => m.direction === "inbound").length;
    const high = messages.filter(
      (m) => m.attention_priority === "HIGH" && !m.attention_resolved,
    ).length;
    return { total, inbound, outbound: total - inbound, high };
  }, [messages]);

  if (loading && messages.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading WhatsApp timeline…
      </div>
    );
  }

  if (error && messages.length === 0) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
        <div className="flex items-center gap-2 font-medium">
          <AlertTriangle className="w-4 h-4" /> Failed to load wa-mirror
          messages
        </div>
        <div className="mt-1 text-xs opacity-80">{error}</div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-900/40 p-8 text-center text-sm text-gray-400">
        <MessageCircle className="w-6 h-6 mx-auto mb-2 opacity-50" />
        No WhatsApp mirror conversation linked to this{" "}
        {practiceId ? "practice" : "client"} yet.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 text-xs text-gray-400">
        <span>
          <strong className="text-gray-200">{stats.total}</strong> messages
        </span>
        <span>
          <span className="text-green-300">{stats.inbound}</span> in /{" "}
          <span className="text-sky-300">{stats.outbound}</span> out
        </span>
        {stats.high > 0 && (
          <span className="text-red-300">
            <AlertTriangle className="inline w-3 h-3 mr-1" />
            {stats.high} HIGH unresolved
          </span>
        )}
      </div>

      <div className="space-y-2">
        {messages.map((m) => {
          const isIn = m.direction === "inbound";
          const prio = m.attention_priority;
          const prioStyle = prio ? PRIORITY_STYLES[prio] : null;
          return (
            <div
              key={m.id}
              className={`flex ${isIn ? "justify-start" : "justify-end"}`}
            >
              <div
                className={`max-w-[78%] rounded-lg border p-3 text-sm ${
                  isIn
                    ? "bg-gray-800/60 border-gray-700"
                    : "bg-emerald-900/30 border-emerald-700/40"
                }`}
              >
                <div className="flex items-center gap-2 mb-1 text-[10px] text-gray-400">
                  <span className="font-mono">
                    {formatDateTime(m.message_date)}
                  </span>
                  {!isIn && m.team_member_phone && (
                    <span className="text-sky-300">
                      ← {m.team_member_phone}
                    </span>
                  )}
                  {isIn && m.counterpart_phone && (
                    <span className="text-green-300">
                      {m.counterpart_phone} →
                    </span>
                  )}
                  {prio && prioStyle && (
                    <span
                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${prioStyle.bg} ${prioStyle.text} ${prioStyle.border} ${
                        m.attention_resolved ? "line-through opacity-50" : ""
                      }`}
                      title={(m.attention_reason || []).join(", ")}
                    >
                      {prio}
                      {m.attention_resolved && (
                        <CheckCircle2 className="inline w-2.5 h-2.5 ml-1" />
                      )}
                    </span>
                  )}
                </div>

                {m.has_media && (
                  <div className="flex items-center gap-1 text-[10px] text-yellow-300 mb-1">
                    <MediaIcon type={m.media_type} />
                    <span className="font-mono">{m.media_type}</span>
                    {m.has_ocr && (
                      <span className="text-emerald-300 ml-1">[OCR]</span>
                    )}
                  </div>
                )}

                {m.body && (
                  <div className="whitespace-pre-wrap break-words text-gray-100">
                    {m.body}
                    {m.body_truncated && (
                      <span className="text-gray-500 ml-1">…(truncated)</span>
                    )}
                  </div>
                )}

                {prio &&
                  m.attention_reason &&
                  m.attention_reason.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.attention_reason
                        .filter((r) => !r.startsWith("ollama_"))
                        .slice(0, 5)
                        .map((r) => (
                          <span
                            key={r}
                            className="px-1.5 py-0.5 rounded bg-black/30 text-[9px] font-mono text-gray-300 border border-gray-700"
                          >
                            {r}
                          </span>
                        ))}
                    </div>
                  )}
              </div>
            </div>
          );
        })}
      </div>

      {hasMore && (
        <div className="text-center pt-2">
          <button
            onClick={loadMore}
            disabled={loading}
            className="px-4 py-1.5 text-xs rounded border border-gray-700 bg-gray-800/50 hover:bg-gray-800 text-gray-300 disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="inline w-3 h-3 animate-spin mr-1" />
                Loading…
              </>
            ) : (
              `Load older messages (${offset} shown)`
            )}
          </button>
        </div>
      )}
    </div>
  );
}
