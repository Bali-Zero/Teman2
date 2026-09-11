import type { MetadataRoute } from "next";
import { publicOrigin } from "../lib/public-origin";

export default function robots(): MetadataRoute.Robots {
  const origin = publicOrigin();
  if (!origin) {
    return { rules: { userAgent: "*", disallow: "/" } };
  }

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
