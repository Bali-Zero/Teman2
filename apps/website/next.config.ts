import path from "node:path";
import type { NextConfig } from "next";
const config: NextConfig = {
  distDir: process.env.WEBSITE_BUILD_DIR || ".next",
  typescript: { tsconfigPath: process.env.WEBSITE_TSCONFIG || "tsconfig.json" },
  poweredByHeader: false,
  // KBLI imports the existing guarded engine and traces its immutable data.
  outputFileTracingRoot: path.resolve(__dirname, "../.."),
  outputFileTracingIncludes: {
    "/sitemap.xml": [
      "../mouth/src/content/articles/**/*.mdx",
      "../mouth/data/kbli-dataset-version.json",
      "../mouth/data/KBLI_2025_FINAL_CLEAN.json",
      "../mouth/data/kbli-gold-all.json",
      "../mouth/data/kbli-risk-disputes.json",
      "../mouth/data/kbli-perpres-slice-disclosures.json",
      "../mouth/data/perpres-locators.json",
      "../../data/kbli-filiera/pma-editorial-certifications.json",
    ],
    "/\\[category\\]/\\[slug\\]": ["../mouth/src/content/articles/**/*.mdx"],
    "/kbli{,/**,-explorer}": [
      "./data/*.json",
      "../mouth/data/KBLI_2025_FINAL_CLEAN.json",
      "../mouth/data/kbli-gold-all.json",
      "../mouth/data/kbli-risk-disputes.json",
      "../mouth/data/kbli-perpres-slice-disclosures.json",
      "../mouth/data/perpres-locators.json",
      "../../data/kbli-filiera/pma-editorial-certifications.json",
    ],
    "/api/kbli/search": [
      "./data/*.json",
      "../mouth/data/KBLI_2025_FINAL_CLEAN.json",
      "../mouth/data/kbli-gold-all.json",
      "../mouth/data/kbli-risk-disputes.json",
      "../mouth/data/kbli-perpres-slice-disclosures.json",
      "../mouth/data/perpres-locators.json",
      "../../data/kbli-filiera/pma-editorial-certifications.json",
    ],
  },
  async redirects() {
    // Source: apps/mouth/next.config.ts. Keep one article segment, not an
    // arbitrary catch-all; unsupported product operations must remain 404.
    const categories = [
      ["immigration", "visas"],
      ["tax-legal", "taxes"],
      ["tax", "taxes"],
      ["lifestyle", "living"],
      ["tech", "trends"],
      ["bali_news", "living"],
      ["digital-nomad", "living"],
    ];
    const exact = [
      ["/v2", "/"],
      ["/v2/news", "/news"],
      ["/insights", "/"],
      ["/insights/news", "/news"],
      ["/visa/second-home-e33", "/visa/second-home"],
      ["/tax-for-freelancers-indonesia-2026", "/taxes/freelancer-tax-guide"],
      [
        "/id/tax-for-freelancers-indonesia-2026",
        "/taxes/freelancer-tax-guide?lang=id",
      ],
      [
        "/it/tax-for-freelancers-indonesia-2026",
        "/taxes/freelancer-tax-guide?lang=it",
      ],
      // The legacy config points at these locale-prefix URLs, but its App
      // Router uses ?lang=. Bridge only these evidenced destinations.
      ["/id/taxes/freelancer-tax-guide", "/taxes/freelancer-tax-guide?lang=id"],
      ["/it/taxes/freelancer-tax-guide", "/taxes/freelancer-tax-guide?lang=it"],
      [
        "/id/insights/pbb-property-tax-indonesia",
        "/taxes/pbb-property-tax-indonesia",
      ],
      [
        "/immigration/e33f-spouse-dependent-kitas-guide",
        "/visas/e31b-spouse-dependent-kitas-guide",
      ],
      [
        "/visas/e33f-spouse-dependent-kitas-guide",
        "/visas/e31b-spouse-dependent-kitas-guide",
      ],
      [
        "/immigration/e33e-child-dependent-kitas-guide",
        "/visas/e31e-child-dependent-kitas-guide",
      ],
      [
        "/visas/e33e-child-dependent-kitas-guide",
        "/visas/e31e-child-dependent-kitas-guide",
      ],
    ];
    return [
      ...exact.map(([source, destination]) => ({
        source,
        destination,
        permanent: false,
      })),
      ...[
        ...categories,
        ...["visas", "business", "taxes", "property", "living", "trends"].map(
          (category) => [category, category],
        ),
      ].flatMap(([source, destination]) => [
        {
          source: `/insights/${source}`,
          destination: `/${destination}`,
          permanent: false,
        },
        {
          source: `/insights/${source}/:slug([a-z0-9][a-z0-9-]{0,199})`,
          destination: `/${destination}/:slug`,
          permanent: false,
        },
      ]),
      ...categories.flatMap(([source, destination]) => [
        {
          source: `/${source}`,
          destination: `/${destination}`,
          permanent: false,
        },
        {
          source: `/${source}/:slug([a-z0-9][a-z0-9-]{0,199})`,
          destination: `/${destination}/:slug`,
          permanent: false,
        },
      ]),
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
        ],
      },
    ];
  },
};
export default config;
