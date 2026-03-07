import { NextResponse } from "next/server";

/**
 * Web Vitals Analytics Endpoint
 * Receives Core Web Vitals metrics from client-side monitoring
 */

interface VitalMetric {
  name: string;
  value: number;
  rating: "good" | "needs-improvement" | "poor";
  delta?: number;
  id: string;
  navigationType?: string;
  page: string;
}

export async function POST(request: Request) {
  try {
    const metric: VitalMetric = await request.json();

    // Log metric (in production, send to analytics service)
    console.log("[Web Vitals]", {
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      page: metric.page,
      timestamp: new Date().toISOString(),
    });

    // Here you could send to:
    // - Google Analytics 4
    // - Vercel Analytics
    // - Custom analytics endpoint
    // - Log aggregation service

    // Example: Alert on poor performance
    if (metric.rating === "poor") {
      console.warn(
        `[Web Vitals Alert] Poor ${metric.name} on ${metric.page}: ${metric.value}`,
      );
      // Could trigger alert to monitoring service
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("[Web Vitals] Failed to process metric:", error);
    return NextResponse.json(
      { error: "Failed to process metric" },
      { status: 400 },
    );
  }
}
