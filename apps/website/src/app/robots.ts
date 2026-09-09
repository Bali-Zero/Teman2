import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const configuredOrigin = process.env.WEBSITE_PUBLIC_ORIGIN;
  if (!configuredOrigin) {
    return { rules: { userAgent: "*", disallow: "/" } };
  }

  const origin = configuredOrigin.replace(/\/+$/, "");
  return {
    rules: {
      userAgent: "*",
      allow: [
        "/",
        "/_next/static/",
        "/_next/image",
        "/llms.txt",
        "/llms-full.txt",
        "/llms-id.txt",
      ],
      disallow: [
        "/api/",
        "/_next/",
        "/*?tag=",
        "/*&tag=",
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
        "/portal/login",
        "/portal/login-upgraded",
        "/legacy/",
        "/visa-oracle/unlock",
      ],
    },
    sitemap: `${origin}/sitemap.xml`,
  };
}
