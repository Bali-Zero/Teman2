import { NextResponse } from "next/server";
import { getAllArticles } from "@/lib/blog/articles";
import homepageLayout from "@/content/homepage-layout.json";

/**
 * GET /api/blog/homepage-hero
 * Returns the 5 hero articles as configured in homepage-layout.json
 * Mirrors exactly what balizero.com shows in its hero collage
 */
export async function GET() {
  try {
    const slugOrder = [
      homepageLayout.hero_main,
      homepageLayout.hero_2,
      homepageLayout.hero_3,
      homepageLayout.hero_4,
      homepageLayout.hero_5,
      (homepageLayout as Record<string, string>).hero_6,
      (homepageLayout as Record<string, string>).hero_7,
    ].filter(Boolean);

    // Fetch all articles (cached, revalidates every 60s)
    const { articles } = await getAllArticles({ limit: 200 });

    const toHeroItem = (a: (typeof articles)[0]) => ({
      slug: a.slug,
      title: a.title,
      category: a.category,
      cover_image: a.coverImage || null,
      href: `https://balizero.com/articles/${a.category}/${a.slug}`,
    });

    // Pin configured slugs first (in order), then fill remaining slots with
    // the most recent articles that have a cover image, up to 7 total.
    const pinned = slugOrder
      .map((slug) => articles.find((a) => a.slug === slug))
      .filter(Boolean) as (typeof articles)[0][];

    const pinnedSlugs = new Set(pinned.map((a) => a.slug));

    const pinnedWithImage = pinned.filter((a) => a.coverImage);

    const fillers = articles
      .filter((a) => a.coverImage && !pinnedSlugs.has(a.slug))
      .slice(0, 4 - pinnedWithImage.length);

    const heroArticles = [...pinnedWithImage, ...fillers]
      .slice(0, 4)
      .map(toHeroItem);

    return NextResponse.json(
      { articles: heroArticles },
      {
        headers: {
          "Cache-Control": "public, s-maxage=60, stale-while-revalidate=300",
        },
      },
    );
  } catch {
    return NextResponse.json({ articles: [] }, { status: 200 });
  }
}
