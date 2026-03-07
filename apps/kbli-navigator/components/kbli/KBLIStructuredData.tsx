import type { KBLICode } from "@/lib/kbli-types";

export function KBLICodeJsonLd({ code }: { code: KBLICode }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    name: `KBLI ${code.code} — ${code.titleEn}`,
    headline: `KBLI ${code.code}: ${code.titleEn} — Indonesian Business Code Guide`,
    description: code.description.slice(0, 200),
    author: {
      "@type": "Organization",
      name: "Bali Zero",
      url: "https://balizero.com",
    },
    publisher: {
      "@type": "Organization",
      name: "Bali Zero",
      url: "https://balizero.com",
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `https://balizero.com/kbli/${code.code}`,
    },
    about: {
      "@type": "GovernmentService",
      name: `KBLI ${code.code}`,
      description: code.titleEn,
      serviceType: "Business Classification",
      provider: {
        "@type": "GovernmentOrganization",
        name: "Badan Pusat Statistik (BPS)",
        url: "https://bps.go.id",
      },
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

export function KBLIBreadcrumbJsonLd({
  items,
}: {
  items: { name: string; url: string }[];
}) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: item.url,
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
