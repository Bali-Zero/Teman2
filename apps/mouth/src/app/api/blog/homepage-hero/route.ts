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

    const heroArticles = slugOrder.map((slug) => {
      const found = articles.find((a) => a.slug === slug);
      if (!found) return null;
      return {
        slug: found.slug,
        title: found.title,
        category: found.category,
        cover_image: found.coverImage || null,
        href: `https://balizero.com/articles/${found.category}/${found.slug}`,
      };
    });

    return NextResponse.json(
      { articles: heroArticles.filter(Boolean) },
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
