import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import { Metadata } from "next";
import {
  ArrowLeft,
  Check,
  Clock,
  Phone,
  FileText,
  AlertCircle,
  ChevronRight,
} from "lucide-react";
import { SERVICES_DATA, type ServiceData } from "@/data/services_data";
import ServicePricing from "@/components/services/ServicePricing";
import { logger } from "@/lib/logger";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { BreadcrumbJsonLd, FAQJsonLd } from "@/components/seo";
import { RUMAH_VARS, RUMAH_CLASS } from "@/lib/theme/rumahVars";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const service = SERVICES_DATA[slug];
  if (!service) {
    return {
      title: "Service Not Found | Bali Zero",
    };
  }

  const metaOverrides: Record<
    string,
    { title: string; description: string; keywords?: string[] }
  > = {
    visa: {
      title:
        "Bali Visa Agency 2026 | KITAS, Visit & Working Visa Indonesia | Bali Zero",
      description:
        "Trusted visa agency in Bali. KITAS, KITAP, Visit Visa, Investor Visa & Working Permits handled end-to-end. 1000+ expats served. Fast processing, transparent pricing.",
      keywords: [
        "bali visa agency",
        "visa agent bali",
        "kitas bali",
        "bali immigration consultant",
        "indonesia visa service",
        "working visa bali",
        "investor kitas bali",
        "bali zero visa",
        "visto bali",
      ],
    },
    company: {
      title: "Business License in Indonesia (2026 Guide) | Bali Zero",
      description:
        "Need a business license in Indonesia? We handle PT PMA setup, OSS licensing, and NIB permits end-to-end. 5,000+ businesses registered.",
      keywords: [
        "company registration bali",
        "business license indonesia",
        "indonesia business license",
        "pt pma bali",
        "business establishment services",
        "license holder in indonesia",
        "bali company setup",
      ],
    },
    tax: {
      title:
        "Indonesia Tax Compliance 2026 | NPWP, Tax Filing & Advisory | Bali Zero",
      description:
        "Navigate Indonesia's tax system with expert guidance. NPWP registration, annual tax filing, tax planning for expats & businesses. Compliant, transparent, hassle-free.",
      keywords: [
        "indonesia tax compliance",
        "npwp registration bali",
        "expat tax indonesia",
        "indonesia tax filing",
        "bali tax advisor",
      ],
    },
    property: {
      title:
        "Bali Property Services 2026 | Legal Due Diligence & Investment | Bali Zero",
      description:
        "Secure property in Bali with legal clarity. Due diligence, land certificates, foreign ownership structures & investment advisory. Protect your investment with expert guidance.",
      keywords: [
        "bali property investment",
        "property due diligence bali",
        "foreign property ownership indonesia",
        "bali land certificate",
      ],
    },
  };

  const override = metaOverrides[slug];
  if (override) {
    return {
      title: override.title,
      description: override.description,
      keywords: override.keywords || ["bali zero", "bali services", slug],
      alternates: {
        canonical: `https://balizero.com/services/${slug}`,
      },
    };
  }

  return {
    title: `${service.name} Bali 2026 | Cost & Requirements | Bali Zero`,
    description: service.tagline,
  };
}

export default async function ServiceDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const service = SERVICES_DATA[slug];

  if (!service) {
    notFound();
  }

  // Structured logging for SEO monitoring
  // Wrapped in try-catch to prevent SSR errors from breaking page render
  try {
    logger.info(`Service Page View: ${slug}`, {
      component: "ServiceDetailPage",
      action: "page_view",
      metadata: {
        service: slug,
        userAgent: "server-side",
        timestamp: new Date().toISOString(),
      },
    });
  } catch {
    // Silently fail logging in production to prevent page crashes
    // Logger errors should not break page rendering
  }

  const IconComponent = service.icon;
  const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

  // Determine service type for semantic HTML microdata
  const serviceType =
    slug === "visa" ? "GovernmentService" : "ProfessionalService";

  const breadcrumbItems = [
    { name: "Home", url: "https://balizero.com" },
    { name: "Services", url: "https://balizero.com/services" },
    { name: service.name, url: `https://balizero.com/services/${slug}` },
  ];

  return (
    <>
      {/* Server-side JSON-LD — included in static HTML for Googlebot */}
      <BreadcrumbJsonLd items={breadcrumbItems} />
      {service.faqs?.length > 0 && <FAQJsonLd items={service.faqs} />}
      {/* R19 skin, scoped per-page via RUMAH_VARS/RUMAH_CLASS (semantic
          re-map layer, shared infra — see rumahVars.ts). NavShell + Footer
          stay untouched (they read --nav-bg / --footer-bg, not
          --surface-base). Body below reads R19 tokens directly, no
          hardcoded hex/Tailwind palette utilities. */}
      <div
        className={`min-h-screen ${RUMAH_CLASS}`}
        style={{
          ...RUMAH_VARS,
          background: "var(--surface-base)",
          color: "var(--text-primary)",
        }}
      >
        {/* Breadcrumb */}
        <div style={{ borderBottom: "1px solid var(--border-subtle)" }}>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-4">
            <nav className="flex items-center gap-2 text-sm">
              <Link
                href="/services"
                className="hover:text-[var(--r19-copper)] transition-colors"
                style={{ color: "var(--text-secondary)" }}
              >
                Services
              </Link>
              <ChevronRight
                className="w-4 h-4"
                style={{ color: "var(--text-tertiary)" }}
              />
              <span style={{ color: "var(--text-primary)" }}>
                {service.name}
              </span>
            </nav>
          </div>
        </div>

        {/* Hero */}
        <section style={{ borderBottom: "1px solid var(--border-subtle)" }}>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-12 lg:py-16">
            <Link
              href="/services"
              className="inline-flex items-center gap-2 hover:text-[var(--r19-copper)] text-sm mb-6 transition-colors"
              style={{ color: "var(--text-secondary)" }}
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Services
            </Link>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
              {/* Main Content */}
              <div className="lg:col-span-2">
                <div className="flex items-start gap-4 mb-6">
                  <div
                    className={`w-16 h-16 rounded-xl ${service.bgColor} flex items-center justify-center flex-shrink-0`}
                    style={{ border: "1px solid var(--border-subtle)" }}
                  >
                    <IconComponent className={`w-8 h-8 ${service.iconColor}`} />
                  </div>
                  <div>
                    <h1
                      className="tracking-tight mb-2"
                      style={{
                        fontFamily: "var(--font-serif)",
                        fontWeight: 500,
                        fontSize: "clamp(28px, 3.4vw, 38px)",
                        lineHeight: 1.1,
                        color: "var(--text-primary)",
                      }}
                    >
                      {service.name}
                    </h1>
                    <p
                      className="text-lg"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {service.tagline}
                    </p>

                    {/* AI Summary Block - Semantic Data Extraction */}
                    <dl
                      className="sr-only"
                      itemScope
                      itemType={`https://schema.org/${serviceType}`}
                    >
                      <dt>Name</dt>
                      <dd itemProp="name">{service.name}</dd>
                      <dt>Image</dt>
                      <dd itemProp="image">
                        {baseUrl}/static/balizero-logo-clean.png
                      </dd>
                      <dt>Service Type</dt>
                      <dd itemProp="serviceType">{service.name}</dd>
                      <dt>Processing Time</dt>
                      <dd itemProp="hoursAvailable">{service.timeline}</dd>
                      <dt>Documents Required</dt>
                      <dd itemProp="documentation">
                        {service.documentsRequired}
                      </dd>
                      <dt>Validity Period</dt>
                      <dd itemProp="validity">{service.validity}</dd>
                      <dt>Service Provider</dt>
                      <dd
                        itemProp="provider"
                        itemScope
                        itemType="https://schema.org/Organization"
                      >
                        <span itemProp="name">Bali Zero</span>
                      </dd>
                      <dt>Area Served</dt>
                      <dd itemProp="areaServed">Indonesia</dd>
                    </dl>
                  </div>
                </div>

                <p
                  className="text-lg leading-relaxed mb-8"
                  style={{ color: "var(--text-secondary)" }}
                >
                  {service.description}
                </p>

                {/* Key Info */}
                <div className="grid grid-cols-3 gap-4 mb-8">
                  {[
                    { Icon: Clock, label: "Timeline", value: service.timeline },
                    {
                      Icon: FileText,
                      label: "Documents",
                      value: service.documentsRequired,
                    },
                    {
                      Icon: AlertCircle,
                      label: "Validity",
                      value: service.validity,
                    },
                  ].map(({ Icon, label, value }) => (
                    <div
                      key={label}
                      className="rounded-lg p-4"
                      style={{
                        background: "var(--r19-surface)",
                        border: "1px solid var(--border-subtle)",
                      }}
                    >
                      <Icon
                        className="w-5 h-5 mb-2"
                        style={{ color: "var(--r19-copper)" }}
                      />
                      <p
                        className="text-xs uppercase tracking-wider"
                        style={{ color: "var(--text-tertiary)" }}
                      >
                        {label}
                      </p>
                      <p
                        className="font-medium"
                        style={{ color: "var(--text-primary)" }}
                      >
                        {value}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Sidebar - CTA */}
              <div className="lg:col-span-1">
                <div
                  className="sticky top-24 rounded-xl p-6"
                  style={{
                    background: "var(--r19-surface)",
                    border: "1px solid var(--r19-line)",
                  }}
                >
                  {/* BALI ZERO Logo */}
                  <div className="flex justify-center mb-4">
                    <Image
                      src="/assets/logo/balizero-logo.png"
                      alt="Bali Zero"
                      width={52}
                      height={52}
                      className="rounded-full"
                      style={{ border: "2px solid var(--border-subtle)" }}
                    />
                  </div>
                  <h3
                    className="font-medium mb-2"
                    style={{ color: "var(--text-primary)" }}
                  >
                    Free Consultation
                  </h3>
                  <p
                    className="text-sm mb-4"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    Get expert advice on your specific situation
                  </p>
                  <Link
                    href={buildWhatsAppLink("home")}
                    target="_blank"
                    className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg font-medium transition-colors mb-3"
                    style={{
                      background: "var(--r19-copper)",
                      color: "var(--r19-cta-ink, #fff)",
                    }}
                  >
                    <Phone className="w-4 h-4" />
                    WhatsApp Us
                  </Link>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing Table - Client Component for Interactivity */}
        {/* Exclude icon (React component) from serialization - it cannot be passed to Client Components */}
        <ServicePricing
          service={
            {
              name: service.name,
              slug: service.slug,
              tagline: service.tagline,
              description: service.description,
              bgColor: service.bgColor,
              iconColor: service.iconColor,
              timeline: service.timeline,
              documentsRequired: service.documentsRequired,
              validity: service.validity,
              packages: service.packages,
              included: service.included,
              requirements: service.requirements,
              faqs: service.faqs,
            } as Omit<ServiceData, "icon">
          }
          slug={slug}
        />

        {/* What's Included */}
        <section style={{ borderBottom: "1px solid var(--border-subtle)" }}>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2
              className="tracking-tight mb-8"
              style={{
                fontFamily: "var(--font-serif)",
                fontWeight: 500,
                fontSize: "clamp(22px, 2.2vw, 28px)",
                color: "var(--text-primary)",
              }}
            >
              What's Included
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {service.included.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 rounded-lg p-4"
                  style={{
                    background: "var(--r19-surface)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  <Check
                    className="w-5 h-5 shrink-0"
                    style={{ color: "var(--r19-copper)" }}
                  />
                  <span style={{ color: "var(--text-secondary)" }}>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Requirements */}
        <section style={{ borderBottom: "1px solid var(--border-subtle)" }}>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2
              className="tracking-tight mb-8"
              style={{
                fontFamily: "var(--font-serif)",
                fontWeight: 500,
                fontSize: "clamp(22px, 2.2vw, 28px)",
                color: "var(--text-primary)",
              }}
            >
              Requirements
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <h3
                  className="font-medium mb-4"
                  style={{ color: "var(--text-primary)" }}
                >
                  Documents Needed
                </h3>
                <ul className="space-y-3">
                  {service.requirements.documents.map((doc, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      <FileText
                        className="w-4 h-4 mt-0.5 flex-shrink-0"
                        style={{ color: "var(--r19-copper)" }}
                      />
                      {doc}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3
                  className="font-medium mb-4"
                  style={{ color: "var(--text-primary)" }}
                >
                  Eligibility
                </h3>
                <ul className="space-y-3">
                  {service.requirements.eligibility.map((req, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      <Check
                        className="w-4 h-4 mt-0.5 flex-shrink-0"
                        style={{ color: "var(--r19-copper)" }}
                      />
                      {req}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section style={{ borderBottom: "1px solid var(--border-subtle)" }}>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2
              className="tracking-tight mb-8"
              style={{
                fontFamily: "var(--font-serif)",
                fontWeight: 500,
                fontSize: "clamp(22px, 2.2vw, 28px)",
                color: "var(--text-primary)",
              }}
            >
              Frequently Asked Questions
            </h2>

            <div className="space-y-4">
              {service.faqs.map((faq, i) => (
                <details
                  key={i}
                  className="group rounded-lg"
                  style={{
                    background: "var(--r19-surface)",
                    border: "1px solid var(--border-subtle)",
                  }}
                >
                  <summary
                    className="flex items-center justify-between cursor-pointer p-6 font-medium"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {faq.question}
                    <ChevronRight
                      className="w-5 h-5 group-open:rotate-90 transition-transform"
                      style={{ color: "var(--text-tertiary)" }}
                    />
                  </summary>
                  <div
                    className="px-6 pb-6"
                    style={{ color: "var(--text-secondary)" }}
                  >
                    {faq.answer}
                  </div>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Other Services */}
        <section>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2
              className="tracking-tight mb-8"
              style={{
                fontFamily: "var(--font-serif)",
                fontWeight: 500,
                fontSize: "clamp(22px, 2.2vw, 28px)",
                color: "var(--text-primary)",
              }}
            >
              Other Services
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {Object.entries(SERVICES_DATA)
                .filter(([key]) => key !== slug)
                .slice(0, 3)
                .map(([key, svc]) => {
                  const SvcIcon = svc.icon;
                  return (
                    <Link key={key} href={`/services/${key}`} className="group">
                      <div
                        className="rounded-xl p-6 transition-all hover:border-[var(--r19-copper)]"
                        style={{
                          background: "var(--r19-surface)",
                          border: "1px solid var(--border-subtle)",
                        }}
                      >
                        <div
                          className={`w-12 h-12 rounded-lg ${svc.bgColor} flex items-center justify-center mb-4`}
                        >
                          <SvcIcon className={`w-6 h-6 ${svc.iconColor}`} />
                        </div>
                        <h3
                          className="font-medium mb-2 group-hover:text-[var(--r19-copper)] transition-colors"
                          style={{ color: "var(--text-primary)" }}
                        >
                          {svc.name}
                        </h3>
                        <p
                          className="text-sm"
                          style={{ color: "var(--text-tertiary)" }}
                        >
                          {svc.tagline}
                        </p>
                      </div>
                    </Link>
                  );
                })}
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
