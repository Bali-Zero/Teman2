import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

/**
 * Dynamic OG Image Generator
 *
 * Endpoint: /api/og
 * Query params:
 * - title: Article title (required)
 * - category: Article category (optional, default: "Insights")
 *
 * Example:
 * /api/og?title=How to Get KITAS in Bali&category=Immigration
 *
 * Returns: 1200x630 image for social media sharing
 *
 * Design:
 * - Dark background (#09090b)
 * - Category badge (top)
 * - Title (large, bold)
 * - Bali Zero branding (bottom)
 */

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get("title") || "Bali Zero";
  const category = searchParams.get("category") || "Insights";

  return new ImageResponse(
    <div
      style={{
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        justifyContent: "flex-end",
        backgroundColor: "#09090b",
        padding: "60px",
      }}
    >
      {/* Category badge */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          marginBottom: "20px",
        }}
      >
        <span
          style={{
            backgroundColor: "rgba(245, 158, 11, 0.15)",
            color: "#f59e0b",
            padding: "8px 20px",
            borderRadius: "8px",
            fontSize: "24px",
            fontWeight: 600,
          }}
        >
          {category.toUpperCase()}
        </span>
      </div>

      {/* Title */}
      <h1
        style={{
          fontSize: title.length > 60 ? "48px" : "56px",
          fontWeight: 700,
          color: "white",
          lineHeight: 1.2,
          marginBottom: "40px",
          maxWidth: "900px",
        }}
      >
        {title}
      </h1>

      {/* Branding bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          width: "100%",
        }}
      >
        <span
          style={{
            fontSize: "28px",
            fontWeight: 700,
            color: "#f59e0b",
          }}
        >
          BALI ZERO
        </span>
        <span
          style={{
            fontSize: "20px",
            color: "#71717a",
          }}
        >
          balizero.com
        </span>
      </div>
    </div>,
    {
      width: 1200,
      height: 630,
    },
  );
}
