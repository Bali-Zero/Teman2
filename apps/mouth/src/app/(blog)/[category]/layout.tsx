import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ArticleCategory } from "@/lib/blog/types";
import { CATEGORY_SEO } from "@/lib/blog/category-seo";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ category: string }>;
}): Promise<Metadata> {
  const { category } = await params;
  if (!Object.prototype.hasOwnProperty.call(CATEGORY_SEO, category)) {
    // This branch used to title-case whatever was in the URL and describe it as
    // a subject we cover: /zzz-nonsense became "Zzz-nonsense Insights — Expert
    // guides and insights about zzz-nonsense in Indonesia and Bali", served 200.
    // That is machine-generated SEO junk for arbitrary input, on an unbounded
    // number of URLs. The layout now 404s these (see the default export); this
    // metadata is what a crawler sees in the meantime, so it must not invite
    // indexing.
    return {
      title: "Page not found",
      robots: { index: false, follow: false },
    };
  }

  const seo = CATEGORY_SEO[category as ArticleCategory];
  const categoryUrl = `${baseUrl}/${category}`;

  return {
    title: seo.title,
    description: seo.description,
    openGraph: {
      type: "website",
      locale: "en_US",
      url: categoryUrl,
      title: `${seo.title} | Bali Zero`,
      description: seo.description,
      siteName: "Bali Zero",
      images: [
        {
          url: `${baseUrl}/static/og-image.jpg`,
          width: 1200,
          height: 630,
          alt: seo.title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${seo.title} | Bali Zero`,
      description: seo.description,
      creator: "@balizero",
    },
    alternates: {
      canonical: categoryUrl,
    },
  };
}

/**
 * `[category]` sits inside the `(blog)` route group, and a route group adds
 * nothing to the URL — so this segment is top-level `/:something` and matches
 * EVERY unmatched single-segment path on every domain the project serves.
 * Without a guard, `/zzz-nonsense`, `/cases`, `/id` and any typo all rendered
 * the category page with an empty article list and returned HTTP **200**: a
 * soft-404, which search engines treat as a real page and index.
 *
 * Anything outside the allow-list now 404s properly, rendering
 * `(blog)/not-found.tsx`. Deliberately an allow-list and not a deny-list: the
 * set of valid categories is closed and known, while the set of junk paths is
 * infinite.
 *
 * Verified before choosing to 404 rather than carve out exceptions: the sitemap
 * advertises 16 single-segment URLs and none is a locale root; no page emits any
 * hreflang; no component navigates to a locale-prefixed path (switching is
 * client-side). So `/id` and `/it` — which used to render "Id Insights" — are
 * linked from nowhere, and a 404 is strictly better than inventing a page.
 * Path-based locales are a separate, tracked change; when they land they get
 * real route segments, which take precedence over this dynamic one.
 */
export default async function CategoryLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ category: string }>;
}) {
  const { category } = await params;
  if (!Object.prototype.hasOwnProperty.call(CATEGORY_SEO, category)) {
    notFound();
  }
  return children;
}
