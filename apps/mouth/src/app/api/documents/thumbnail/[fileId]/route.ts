import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

/**
 * Proxy authenticated Google Drive thumbnails
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
      `${API_BASE_URL}/api/documents/thumbnail/${fileId}`,
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
      // For other errors, try fallback to public Google Drive URL
      return NextResponse.redirect(
        `https://drive.google.com/thumbnail?id=${fileId}&sz=w800`,
        307,
      );
    }

    // Get the image data
    const imageBuffer = await response.arrayBuffer();
    const contentType = response.headers.get("content-type") || "image/jpeg";

    return new NextResponse(imageBuffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "private, max-age=3600",
      },
    });
  } catch (error) {
    logger.error("Thumbnail proxy error:", error);
    // Fallback to public Google Drive URL
    return NextResponse.redirect(
      `https://drive.google.com/thumbnail?id=${fileId}&sz=w800`,
      307,
    );
  }
}
