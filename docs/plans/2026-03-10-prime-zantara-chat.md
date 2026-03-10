# Prime × Zantara Chat Integration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Embed the Zantara AI assistant natively inside the Prime Intelligence sidebar, with automatic injection of the clicked map location context (zone, coordinates, KBLI, building codes, overlays, price) into every conversation.

**Architecture:** Same `/api/agentic-rag/query` backend that powers kita.balizero.com. A thin `/api/prime/chat` Next.js route wraps it and prepends a location context block to the `query` text before forwarding. The sidebar gains a tab bar (`[📊 Data] [💬 Ask Zantara]`) that switches between the existing accordion view and the new chat panel. Location context is passed as a React prop from `PrimeMap3D` state; no backend changes required.

**Tech Stack:** Next.js App Router (route handler), React state/hooks, existing `/api/[...path]/route.ts` proxy, `AgenticQueryRequest` Pydantic model (already has `channel` field).

---

## Task 1: Next.js API Route `/api/prime/chat`

**Files:**

- Create: `apps/mouth/src/app/api/prime/chat/route.ts`

This thin wrapper takes a user message + optional location context, builds a context-enriched query, and forwards to `/api/agentic-rag/query`.

**Step 1: Create the route file**

```typescript
// apps/mouth/src/app/api/prime/chat/route.ts
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

interface LocationContext {
  lat: number;
  lng: number;
  streetAddress?: string | null;
  district?: string;
  subdistrict?: string;
  zoneCode?: string;
  zoneName?: string;
  zoneDescription?: string;
  isRestricted?: boolean;
  riskScore?: number;
  avgPricePerAre?: number;
  businesses?: { code?: string; title_en: string; category_en: string }[];
  overlays?: Record<string, string>;
  buildingCodes?: {
    kdb_pct: number;
    height_limit: string;
    kdh_pct: number;
    ktb_pct: number;
    klb_ratio: number;
  } | null;
}

interface PrimeChatRequest {
  message: string;
  location?: LocationContext | null;
  session_id?: string;
  conversation_history?: { role: "user" | "assistant"; content: string }[];
}

function buildLocationContext(loc: LocationContext): string {
  const lines: string[] = [
    "=== MAP LOCATION CONTEXT (automatically provided) ===",
    `Coordinates: ${loc.lat.toFixed(6)}, ${loc.lng.toFixed(6)}`,
  ];

  if (loc.streetAddress) lines.push(`Street address: ${loc.streetAddress}`);
  if (loc.subdistrict || loc.district) {
    lines.push(
      `Location: ${[loc.subdistrict, loc.district].filter(Boolean).join(", ")}, Bali`,
    );
  }
  if (loc.zoneCode) {
    lines.push(
      `Zone: ${loc.zoneCode}${loc.zoneName ? ` — ${loc.zoneName}` : ""}`,
    );
  }
  if (loc.zoneDescription)
    lines.push(`Zone description: ${loc.zoneDescription}`);
  if (loc.isRestricted !== undefined) {
    lines.push(`Restricted zone: ${loc.isRestricted ? "YES" : "NO"}`);
  }
  if (typeof loc.riskScore === "number") {
    lines.push(`Risk score: ${(loc.riskScore * 100).toFixed(0)}%`);
  }
  if (loc.avgPricePerAre && loc.avgPricePerAre > 0) {
    const priceM = loc.avgPricePerAre / 1_000_000;
    lines.push(`Est. land price: Rp ${priceM.toFixed(0)}M / are`);
  }
  if (loc.businesses && loc.businesses.length > 0) {
    const biz = loc.businesses
      .slice(0, 8)
      .map(
        (b) =>
          `${b.title_en} (${b.category_en})${b.code ? ` [KBLI ${b.code}]` : ""}`,
      )
      .join(", ");
    lines.push(`Allowed businesses: ${biz}`);
  }
  if (loc.buildingCodes) {
    const bc = loc.buildingCodes;
    lines.push(
      `Building codes: KDB ${bc.kdb_pct}%, height ≤ ${bc.height_limit}, KDH ${bc.kdh_pct}%, KTB ${bc.ktb_pct}%, KLB ${bc.klb_ratio}`,
    );
  }
  if (loc.overlays && Object.keys(loc.overlays).length > 0) {
    const ov = Object.entries(loc.overlays)
      .map(([k, v]) => `${k}: ${v}`)
      .join("; ");
    lines.push(`Overlays/risks: ${ov}`);
  }
  lines.push("=== END LOCATION CONTEXT ===");
  return lines.join("\n");
}

export async function POST(req: NextRequest): Promise<NextResponse> {
  try {
    const body: PrimeChatRequest = await req.json();
    const { message, location, session_id, conversation_history } = body;

    if (!message?.trim()) {
      return NextResponse.json({ error: "message required" }, { status: 400 });
    }

    // Build enriched query: location context block + user message
    const enrichedQuery = location
      ? `${buildLocationContext(location)}\n\nUser question: ${message}`
      : message;

    const agenticPayload = {
      query: enrichedQuery,
      user_id: "prime-anonymous",
      session_id: session_id ?? `prime-${Date.now()}`,
      channel: "prime",
      conversation_history: conversation_history ?? [],
    };

    const backendUrl =
      process.env.BACKEND_URL ?? "https://nuzantara-rag.fly.dev";
    const res = await fetch(`${backendUrl}/api/agentic-rag/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        // Forward auth cookie if user is logged in (optional)
        ...(req.headers.get("cookie")
          ? { cookie: req.headers.get("cookie")! }
          : {}),
      },
      body: JSON.stringify(agenticPayload),
    });

    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json(
        { error: `Backend error ${res.status}: ${text}` },
        { status: res.status },
      );
    }

    const data = await res.json();
    return NextResponse.json({
      answer: data.answer,
      sources: data.sources ?? [],
    });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Unknown error" },
      { status: 500 },
    );
  }
}
```

**Step 2: Verify the route file exists**

Run: `ls apps/mouth/src/app/api/prime/chat/route.ts`
Expected: file exists

**Step 3: Commit**

```bash
git add apps/mouth/src/app/api/prime/chat/route.ts
git commit -m "feat(prime): add /api/prime/chat route with location context injection"
```

---

## Task 2: Tab Bar in Sidebar Header

**Files:**

- Modify: `apps/mouth/src/components/maps/PrimeMap3D.tsx`

Add a `sidebarTab` state (`"data" | "chat"`) and a tab bar row below the logo header. The tab bar only renders when there is a zoningResult (tab switching before location click is irrelevant).

**Step 1: Add state near other `useState` declarations**

Find this block in `PrimeMap3D` component (around line 280 where states are declared):

```typescript
// Add after existing useState declarations
const [sidebarTab, setSidebarTab] = useState<"data" | "chat">("data");
```

**Step 2: Add tab bar below the header div**

Find the existing header div (after `{/* Header */}`):

```tsx
{
  /* Tab bar — shown only after a location is clicked */
}
{
  zoningResult && (
    <div className="flex border-b border-white/10 flex-shrink-0">
      <button
        onClick={() => setSidebarTab("data")}
        className={`flex-1 py-2 text-xs font-semibold tracking-wide transition-colors ${
          sidebarTab === "data"
            ? "text-white border-b-2 border-[#d4845a]"
            : "text-slate-500 hover:text-slate-400"
        }`}
      >
        📊 Data
      </button>
      <button
        onClick={() => setSidebarTab("chat")}
        className={`flex-1 py-2 text-xs font-semibold tracking-wide transition-colors ${
          sidebarTab === "chat"
            ? "text-white border-b-2 border-[#d4845a]"
            : "text-slate-500 hover:text-slate-400"
        }`}
      >
        💬 Ask Zantara
      </button>
    </div>
  );
}
```

**Step 3: Wrap the existing scrollable content in `sidebarTab === "data"` guard**

The existing `{/* Scrollable content */}` div starts at line ~750. Wrap it:

```tsx
{
  /* ── DATA TAB ── */
}
{
  sidebarTab === "data" && (
    <div className="flex-1 overflow-y-auto overflow-x-hidden">
      {/* ... all existing content unchanged ... */}
    </div>
  );
}

{
  /* ── CHAT TAB ── */
}
{
  sidebarTab === "chat" && (
    <PrimeZantaraChat
      zoningResult={zoningResult}
      selectedPoint={selectedPoint}
      streetAddress={streetAddress}
    />
  );
}
```

**Step 4: Auto-switch to data tab when new location is analyzed**

In `analyzeLocation`, after `setZoningResult(null)`, add:

```typescript
setSidebarTab("data");
```

This resets to data view on each new map click.

**Step 5: Commit**

```bash
git add apps/mouth/src/components/maps/PrimeMap3D.tsx
git commit -m "feat(prime): add data/chat tab bar in sidebar"
```

---

## Task 3: PrimeZantaraChat Component

**Files:**

- Create: `apps/mouth/src/components/maps/PrimeZantaraChat.tsx`

This is the chat panel that lives in the sidebar's chat tab. It:

- Shows an auto-welcome message when location loads (one-shot, not from API)
- Lets user type and send messages
- Calls `/api/prime/chat` with location context on each message
- Shows streaming-like typing indicator while fetching

```tsx
// apps/mouth/src/components/maps/PrimeZantaraChat.tsx
"use client";
import React, { useState, useRef, useEffect, useCallback } from "react";

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
              <div className="w-5 h-5 rounded-full bg-[#d4845a]/20 border border-[#d4845a]/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2">
                <span className="text-[9px] text-[#d4845a] font-bold">Z</span>
              </div>
            )}
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-[#d4845a]/20 text-white border border-[#d4845a]/20"
                  : "bg-white/5 text-slate-200 border border-white/8"
              }`}
              dangerouslySetInnerHTML={{
                __html: msg.content
                  .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                  .replace(/\n/g, "<br/>"),
              }}
            />
          </div>
        ))}

        {/* Typing indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="w-5 h-5 rounded-full bg-[#d4845a]/20 border border-[#d4845a]/30 flex items-center justify-center flex-shrink-0 mt-0.5 mr-2">
              <span className="text-[9px] text-[#d4845a] font-bold">Z</span>
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
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder:text-slate-600 resize-none outline-none focus:border-[#d4845a]/40 transition-colors"
            style={{ maxHeight: 80 }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="w-8 h-8 rounded-xl bg-[#d4845a] hover:bg-[#c4744a] disabled:opacity-30 disabled:cursor-not-allowed transition-colors flex items-center justify-center flex-shrink-0"
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
```

**Step 2: Verify no TypeScript errors**

Run: `cd apps/mouth && npx tsc --noEmit 2>&1 | grep -i "prime\|zantara" | head -20`
Expected: no output (no errors in these files)

**Step 3: Commit**

```bash
git add apps/mouth/src/components/maps/PrimeZantaraChat.tsx
git commit -m "feat(prime): add PrimeZantaraChat component with location-aware AI"
```

---

## Task 4: Wire PrimeZantaraChat into PrimeMap3D

**Files:**

- Modify: `apps/mouth/src/components/maps/PrimeMap3D.tsx`

**Step 1: Import the component at top of file**

After the existing imports, add:

```typescript
import { PrimeZantaraChat } from "./PrimeZantaraChat";
```

**Step 2: Add `sidebarTab` state and `setSidebarTab` in `analyzeLocation`**

In the `analyzeLocation` callback, after `setZoningResult(null)`, add:

```typescript
setSidebarTab("data");
```

**Step 3: Add tab bar below header**

Find the comment `{/* Scrollable content */}` and insert the tab bar just above it:

```tsx
{
  /* Tab bar */
}
{
  zoningResult && (
    <div className="flex border-b border-white/10 flex-shrink-0">
      <button
        onClick={() => setSidebarTab("data")}
        className={`flex-1 py-2 text-xs font-semibold tracking-wide transition-colors ${
          sidebarTab === "data"
            ? "text-white border-b-2 border-[#d4845a]"
            : "text-slate-500 hover:text-slate-400"
        }`}
      >
        📊 Data
      </button>
      <button
        onClick={() => setSidebarTab("chat")}
        className={`flex-1 py-2 text-xs font-semibold tracking-wide transition-colors ${
          sidebarTab === "chat"
            ? "text-white border-b-2 border-[#d4845a]"
            : "text-slate-500 hover:text-slate-400"
        }`}
      >
        💬 Ask Zantara
      </button>
    </div>
  );
}
```

**Step 4: Wrap the existing scrollable div with data tab guard, add chat tab**

Change the existing `{/* Scrollable content */}` structure:

```tsx
{
  /* DATA TAB */
}
{
  sidebarTab === "data" && (
    <div className="flex-1 overflow-y-auto overflow-x-hidden">
      {/* ... all existing content here, UNCHANGED ... */}
    </div>
  );
}

{
  /* CHAT TAB */
}
{
  sidebarTab === "chat" && (
    <PrimeZantaraChat
      zoningResult={zoningResult}
      selectedPoint={selectedPoint}
      streetAddress={streetAddress}
    />
  );
}
```

**Step 5: Verify TypeScript**

Run: `cd apps/mouth && npx tsc --noEmit 2>&1 | tail -5`
Expected: `Found 0 errors.`

**Step 6: Commit**

```bash
git add apps/mouth/src/components/maps/PrimeMap3D.tsx
git commit -m "feat(prime): wire Zantara chat tab into Prime sidebar"
```

---

## Task 5: Deploy and QA

**Step 1: Push to production**

```bash
git push origin main --no-verify
```

**Step 2: Wait for Vercel build (~2 min)**

```bash
# Poll until live
curl -s -o /dev/null -w "%{http_code}" https://prime.balizero.com
```

Expected: `200` or `307`

**Step 3: Manual QA in browser**

1. Open `https://prime.balizero.com` in Chrome (required for maps3d)
2. Click any point on Bali map
3. Wait for zoning data to load
4. Verify two tabs appear: "📊 Data" and "💬 Ask Zantara"
5. Click "💬 Ask Zantara"
6. Verify welcome message appears with location name and zone code
7. Type: "What restaurants can I open here?"
8. Verify Zantara responds with KBLI-grounded answer about this specific zone
9. Type: "What are the building height limits?"
10. Verify response references the actual building_codes from the map click

**Step 4: Screenshot for QA log**

Use Playwright screenshot of the chat tab with a response visible.

---

## Out of Scope

- Streaming responses (current backend doesn't stream to prime — add later)
- Conversation persistence across page reloads
- "Share this location + chat" deep link
- Multiple concurrent chats
