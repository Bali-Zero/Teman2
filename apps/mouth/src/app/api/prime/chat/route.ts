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
