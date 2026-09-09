import { servicePriceIdentities } from "../../../content/service-price-identities";

const officialPriceEndpoint = "https://nuzantara-rag.fly.dev/api/pricing/service";
const scalarIdr = /^(?:\d+|\d{1,3}(?:\.\d{3})+)\s+IDR$/i;
const headers = { "Cache-Control": "no-store" };

export async function GET(request: Request) {
  const key = new URL(request.url).searchParams.get("key");
  const identity = Object.values(servicePriceIdentities).find((entry) => entry.key === key);
  if (!identity) return Response.json({ available: false }, { status: 404, headers });

  try {
    const url = new URL(officialPriceEndpoint);
    url.searchParams.set("key", identity.key);
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "omit",
      signal: AbortSignal.timeout(6000),
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error("Price unavailable");
    const entry: unknown = await response.json();
    if (!entry || typeof entry !== "object") throw new Error("Invalid price response");
    const row = entry as Record<string, unknown>;
    if (row.key !== identity.key || row.category !== identity.category || typeof row.price !== "string" || !scalarIdr.test(row.price.trim())) {
      throw new Error("Price identity or amount unavailable");
    }
    const verifiedOn = typeof row.verified_on === "string" && /^\d{4}-\d{2}-\d{2}$/.test(row.verified_on) && !Number.isNaN(Date.parse(row.verified_on)) ? row.verified_on : null;
    return Response.json({ available: true, price: row.price.trim(), verifiedOn }, { headers });
  } catch {
    return Response.json({ available: false }, { status: 503, headers });
  }
}
