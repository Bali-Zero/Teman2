import type { MetadataRoute } from "next";
import { getAllCodes, getSections } from "@/lib/kbli-data";

const BASE_URL = "https://balizero.com/kbli-navigator";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  const staticPages: MetadataRoute.Sitemap = [
    {
      url: `${BASE_URL}`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/kbli`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/kbli/search`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/kbli/sectors`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/knowledge`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.8,
    },
  ];

  const sectorPages: MetadataRoute.Sitemap = getSections()
    .filter((s) => s.codeCount > 0)
    .map((s) => ({
      url: `${BASE_URL}/kbli/sectors/${s.id}`,
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    }));

  const codePages: MetadataRoute.Sitemap = getAllCodes().map((c) => ({
    url: `${BASE_URL}/kbli/${c.code}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: c.tier === "gold" ? 0.8 : 0.5,
  }));

  return [...staticPages, ...sectorPages, ...codePages];
}
