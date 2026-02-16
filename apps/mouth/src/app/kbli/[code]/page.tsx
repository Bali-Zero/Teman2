import type { Metadata } from "next";
import KBLICodePageClient from "./client-page";

/**
 * KBLI Code Landing Page (SEO-optimized)
 *
 * Dynamic route: /kbli/[code]
 * Example: /kbli/56101 → Restaurant business classification
 *
 * SEO Features:
 * - Static metadata with KBLI code in title
 * - Client-side data fetching for reliability
 * - Mobile-optimized content
 *
 * Data source: Backend API endpoint GET /api/v1/kbli-notebook/inspect/{code}
 */

/**
 * Generate metadata for SEO
 * Using static metadata since we're doing client-side rendering
 */
export async function generateMetadata({
  params,
}: {
  params: { code: string };
}): Promise<Metadata> {
  const code = params.code;

  return {
    title: `KBLI ${code} - Indonesia Business Classification | Bali Zero`,
    description: `Complete guide to KBLI ${code} business classification code. Requirements, licenses, capital, and PMA status for business setup in Indonesia.`,
    keywords: [
      `kbli ${code}`,
      "kbli indonesia",
      "business classification",
      "pt pma",
      "company setup indonesia",
      "indonesia business code",
    ],
    openGraph: {
      title: `KBLI ${code} - Indonesia Business Classification`,
      description: `Complete information about KBLI ${code} business classification code in Indonesia.`,
      type: "article",
      url: `https://balizero.com/kbli/${code}`,
    },
    twitter: {
      card: "summary_large_image",
      title: `KBLI ${code} - Indonesia Business Classification`,
      description: `Complete information about KBLI ${code} business classification code in Indonesia.`,
    },
  };
}

// All UI logic moved to client-page.tsx for client-side rendering

export default function KBLICodePage({ params }: { params: { code: string } }) {
  // Use client-side rendering for reliable data fetching
  return <KBLICodePageClient code={params.code} />;
}
