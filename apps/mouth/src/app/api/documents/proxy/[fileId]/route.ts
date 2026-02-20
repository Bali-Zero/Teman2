import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";
import { logger } from "@/lib/logger";

/**
 * Proxy authenticated Google Drive documents
 * Forwards the user's JWT token to the backend
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ fileId: string }> },
): Promise<Response> {
  const { fileId } = await params;

  if (!fileId) {
    return NextResponse.json({ error: "File ID required" }, { status: 400 });
  }

  // Get token from cookies
  const cookieStore = await cookies();
  const token = cookieStore.get("token")?.value;

  if (!token) {
    return NextResponse.json(
      { error: "Authentication required" },
      { status: 401 },
    );
  }

  const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL || "https://nuzantara-rag.fly.dev";

  try {
    // Forward request to backend with authentication
    const response = await fetch(
      `${API_BASE_URL}/api/documents/proxy/${fileId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      },
    );

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json({ error: "File not found" }, { status: 404 });
      }
      if (response.status === 401) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
      }
      // Fallback to Google Drive direct link
      return NextResponse.redirect(
        `https://drive.google.com/file/d/${fileId}/view`,
        307,
      );
    }

    // Get the document data
    const buffer = await response.arrayBuffer();
    const contentType =
      response.headers.get("content-type") || "application/octet-stream";
    const contentDisposition = response.headers.get("content-disposition");

    const headers: Record<string, string> = {
      "Content-Type": contentType,
      "Cache-Control": "private, max-age=3600",
    };

    if (contentDisposition) {
      headers["Content-Disposition"] = contentDisposition;
    }

    return new NextResponse(buffer, {
      status: 200,
      headers,
    });
  } catch (error) {
    logger.error("Document proxy error:", error as Record<string, unknown>);
    // Fallback to Google Drive
    return NextResponse.redirect(
      `https://drive.google.com/file/d/${fileId}/view`,
      307,
    );
  }
}
