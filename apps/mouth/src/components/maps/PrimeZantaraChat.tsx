"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";
import { safeHtmlChat } from "@/lib/utils/safe-html";

interface ZoningInfo {
  status: string;
  district?: string;
  subdistrict?: string;
  zone_code?: string;
  zone_name?: string;
  zone_label_en?: string;
  zone_color_hex?: string;
  zone_description_en?: string;
  is_restricted?: boolean;
  businesses?: { code?: string; title_en: string; category_en: string }[];
  overlays?: Record<string, string>;
  building_codes?: {
    kdb_pct: number;
    height_limit: string;
    kdh_pct: number;
    ktb_pct: number;
    klb_ratio: number;
  } | null;
  risk_score?: number;
  avg_price_per_are?: number;
}

interface Coordinate {
  lat: number;
  lng: number;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
}

interface Props {
  zoningResult: ZoningInfo | null;
  selectedPoint: Coordinate | null;
  streetAddress: string | null;
}

export function PrimeZantaraChat({
  zoningResult,
  selectedPoint,
  streetAddress,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(`prime-${Date.now()}`);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const prevPointRef = useRef<string | null>(null);

  // Auto-welcome when location changes
  useEffect(() => {
    if (!zoningResult || zoningResult.status !== "found" || !selectedPoint)
      return;
    const pointKey = `${selectedPoint.lat.toFixed(5)},${selectedPoint.lng.toFixed(5)}`;
    if (prevPointRef.current === pointKey) return;
    prevPointRef.current = pointKey;

    const locationLabel =
      streetAddress ||
      [zoningResult.subdistrict, zoningResult.district]
        .filter(Boolean)
        .join(", ") ||
      `${selectedPoint.lat.toFixed(4)}, ${selectedPoint.lng.toFixed(4)}`;

    const zoneInfo = zoningResult.zone_code
      ? ` Zone **${zoningResult.zone_code}**${zoningResult.zone_label_en ? ` (${zoningResult.zone_label_en})` : ""}.`
      : "";

    const welcome = `I've loaded the zoning data for **${locationLabel}**.${zoneInfo} Ask me anything about this location — what businesses you can open, building regulations, investment risks, or visa requirements.`;

    setMessages([{ id: "welcome", role: "assistant", content: welcome }]);
  }, [zoningResult, selectedPoint, streetAddress]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const buildLocationPayload = useCallback(() => {
    if (!zoningResult || !selectedPoint) return null;
    return {
      lat: selectedPoint.lat,
      lng: selectedPoint.lng,
      streetAddress,
      district: zoningResult.district,
      subdistrict: zoningResult.subdistrict,
      zoneCode: zoningResult.zone_code,
      zoneName: zoningResult.zone_label_en ?? zoningResult.zone_name,
      zoneDescription: zoningResult.zone_description_en,
      isRestricted: zoningResult.is_restricted,
      riskScore: zoningResult.risk_score,
      avgPricePerAre: zoningResult.avg_price_per_are,
      businesses: zoningResult.businesses,
      overlays: zoningResult.overlays,
      buildingCodes: zoningResult.building_codes,
    };
  }, [zoningResult, selectedPoint, streetAddress]);

  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const history = messages
        .filter((m) => m.role !== "system" && m.id !== "welcome")
        .map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }));

      const res = await fetch("/api/prime/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          location: buildLocationPayload(),
          session_id: sessionId,
          conversation_history: history,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: data.answer ?? "No response.",
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: "assistant",
          content:
            "Sorry, I couldn't reach Zantara right now. Try again in a moment.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, messages, buildLocationPayload, sessionId]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Idle state: no location yet
  if (!zoningResult || zoningResult.status !== "found") {
    return (
      <div className="flex flex-col items-center justify-center h-full py-12 px-6 text-center">
        <div className="w-10 h-10 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-3">
          <svg
            className="w-4 h-4 text-slate-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </div>
        <p className="text-xs text-slate-500 leading-relaxed">
          Tap the map first to load
          <br />
          location data, then ask Zantara
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-5 h-5 rounded-full bg-accent-warm/20 border border-accent-warm/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2">
                <span className="text-[9px] text-accent-warm font-bold">Z</span>
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-accent-warm/20 text-white border border-accent-warm/20"
                  : "bg-white/5 text-slate-200 border border-white/8"
              }`}
              dangerouslySetInnerHTML={safeHtmlChat(
                msg.content
                  .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                  .replace(/\n/g, "<br/>"),
              )}
            />
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="w-5 h-5 rounded-full bg-accent-warm/20 border border-accent-warm/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2">
              <span className="text-[9px] text-accent-warm font-bold">Z</span>
            </div>
            <div className="bg-white/5 border border-white/8 rounded-xl px-3 py-2">
              <div className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 px-3 pb-3 border-t border-white/5 pt-2">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about this location…"
            rows={1}
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-600 resize-none outline-none focus:border-accent-warm/40 transition-colors"
            style={{ maxHeight: 80 }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="w-8 h-8 rounded-xl bg-accent-warm hover:bg-[#c4744a] disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center justify-center flex-shrink-0"
          >
            <svg
              className="w-3.5 h-3.5 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
