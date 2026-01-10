import { NextRequest, NextResponse } from 'next/server';
import { readFile } from 'fs/promises';
import path from 'path';

/**
 * Static image file handler
 *
 * This route handler takes precedence over the dynamic [category]/[slug] route
 * and serves static images from /public/images/
 */

// MIME type mapping
const MIME_TYPES: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: pathSegments } = await params;
  const imagePath = pathSegments.join('/');

  // Security: prevent directory traversal
  if (imagePath.includes('..')) {
    return new NextResponse('Forbidden', { status: 403 });
  }

  const ext = path.extname(imagePath).toLowerCase();
  const mimeType = MIME_TYPES[ext];

  if (!mimeType) {
    return new NextResponse('Not Found', { status: 404 });
  }

  try {
    // In development, read from public folder
    // In production (Vercel), files are in .next/static or served differently
    const filePath = path.join(process.cwd(), 'public', 'images', imagePath);
    const fileBuffer = await readFile(filePath);

    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        'Content-Type': mimeType,
        'Cache-Control': 'public, max-age=31536000, immutable',
      },
    });
  } catch {
    return new NextResponse('Not Found', { status: 404 });
  }
}
