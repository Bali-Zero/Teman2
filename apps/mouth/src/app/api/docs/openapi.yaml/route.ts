import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

/**
 * Serve OpenAPI YAML spec
 * Endpoint: GET /api/docs/openapi.yaml
 */
export async function GET() {
  const filePath = path.join(process.cwd(), "src/lib/api/openapi.yaml");

  try {
    const content = fs.readFileSync(filePath, "utf-8");

    return new NextResponse(content, {
      status: 200,
      headers: {
        "Content-Type": "application/yaml",
        "Cache-Control": "public, max-age=3600", // Cache for 1 hour
      },
    });
  } catch (error) {
    return NextResponse.json(
      { error: "OpenAPI spec not found" },
      { status: 404 },
    );
  }
}
