import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/stories/", "/editions/"],
      disallow: ["/research", "/operations", "/api/"],
    },
    host: "https://bali-zero-magazine.antonellosiano.chatgpt.site",
  };
}
