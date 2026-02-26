import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/dashboard",
          "/clients",
          "/chat",
          "/settings",
          "/analytics",
          "/intelligence",
          "/whatsapp",
          "/email",
          "/documents",
          "/knowledge",
          "/cases",
          "/omnichannel",
          "/admin",
          "/login",
          "/api/",
          "/_next/",
        ],
      },
    ],
    sitemap: "https://balizero.com/sitemap.xml",
  };
}
