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
      title:
        "Company Registration Bali 2026 | PT PMA, Business License Indonesia | Bali Zero",
      description:
        "Register your company in Bali — PT PMA setup, business license Indonesia, KBLI classification, NIB & OSS permits. Transparent pricing from IDR 20M. 5000+ businesses established.",
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

  // NOTE: JSON-LD schemas are now injected in the <head> by the root layout
  // (apps/mouth/src/app/layout.tsx) to ensure they are detected by Schema.org Validator

  return (
    <>
      <div className="min-h-screen bg-[#051C2C]">
        {/* Breadcrumb */}
        <div className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-4">
            <nav className="flex items-center gap-2 text-sm">
              <Link
                href="/services"
                className="text-white/50 hover:text-white transition-colors"
              >
                Services
              </Link>
              <ChevronRight className="w-4 h-4 text-white/30" />
              <span className="text-white">{service.name}</span>
            </nav>
          </div>
        </div>

        {/* Hero */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-12 lg:py-16">
            <Link
              href="/services"
              className="inline-flex items-center gap-2 text-white/50 hover:text-white text-sm mb-6 transition-colors"
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
                  >
                    <IconComponent className={`w-8 h-8 ${service.iconColor}`} />
                  </div>
                  <div>
                    <h1 className="font-serif text-3xl lg:text-4xl text-white mb-2">
                      {service.name}
                    </h1>
                    <p className="text-white/60 text-lg">{service.tagline}</p>

                    {/* AI Summary Block - Semantic Data Extraction */}
                    <dl
                      className="sr-only"
                      itemScope
                      itemType={`https://schema.org/${serviceType}`}
                    >
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

                <p className="text-white/70 text-lg leading-relaxed mb-8">
                  {service.description}
                </p>

                {/* Key Info */}
                <div className="grid grid-cols-3 gap-4 mb-8">
                  <div className="bg-[#0a2540] rounded-lg p-4">
                    <Clock className="w-5 h-5 text-[#2251ff] mb-2" />
                    <p className="text-white/40 text-xs uppercase tracking-wider">
                      Timeline
                    </p>
                    <p className="text-white font-medium">{service.timeline}</p>
                  </div>
                  <div className="bg-[#0a2540] rounded-lg p-4">
                    <FileText className="w-5 h-5 text-[#2251ff] mb-2" />
                    <p className="text-white/40 text-xs uppercase tracking-wider">
                      Documents
                    </p>
                    <p className="text-white font-medium">
                      {service.documentsRequired}
                    </p>
                  </div>
                  <div className="bg-[#0a2540] rounded-lg p-4">
                    <AlertCircle className="w-5 h-5 text-[#2251ff] mb-2" />
                    <p className="text-white/40 text-xs uppercase tracking-wider">
                      Validity
                    </p>
                    <p className="text-white font-medium">{service.validity}</p>
                  </div>
                </div>
              </div>

              {/* Sidebar - CTA */}
              <div className="lg:col-span-1">
                <div className="sticky top-24 bg-gradient-to-br from-[#e85c41] to-[#d14832] rounded-xl p-6">
                  {/* BALI ZERO Logo */}
                  <div className="flex justify-center mb-4">
                    <Image
                      src="/assets/logo/balizero-logo.png"
                      alt="Bali Zero"
                      width={52}
                      height={52}
                      className="rounded-full border-2 border-white/30"
                    />
                  </div>
                  <h3 className="text-white font-medium mb-2">
                    Free Consultation
                  </h3>
                  <p className="text-white/80 text-sm mb-4">
                    Get expert advice on your specific situation
                  </p>
                  <Link
                    href="https://wa.me/6285904369574"
                    target="_blank"
                    className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg bg-white text-[#e85c41] font-medium hover:bg-white/90 transition-colors mb-3"
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
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2 className="font-serif text-2xl text-white mb-8">
              What's Included
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {service.included.map((item, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 bg-[#0a2540] rounded-lg p-4"
                >
                  <Check className="w-5 h-5 text-[#22c55e]" />
                  <span className="text-white/80">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Requirements */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2 className="font-serif text-2xl text-white mb-8">
              Requirements
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div>
                <h3 className="text-white font-medium mb-4">
                  Documents Needed
                </h3>
                <ul className="space-y-3">
                  {service.requirements.documents.map((doc, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-white/70 text-sm"
                    >
                      <FileText className="w-4 h-4 text-[#2251ff] mt-0.5 flex-shrink-0" />
                      {doc}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h3 className="text-white font-medium mb-4">Eligibility</h3>
                <ul className="space-y-3">
                  {service.requirements.eligibility.map((req, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-white/70 text-sm"
                    >
                      <Check className="w-4 h-4 text-[#22c55e] mt-0.5 flex-shrink-0" />
                      {req}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ */}
        <section className="border-b border-white/10">
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2 className="font-serif text-2xl text-white mb-8">
              Frequently Asked Questions
            </h2>

            <div className="space-y-4">
              {service.faqs.map((faq, i) => (
                <details key={i} className="group bg-[#0a2540] rounded-lg">
                  <summary className="flex items-center justify-between cursor-pointer p-6 text-white font-medium">
                    {faq.question}
                    <ChevronRight className="w-5 h-5 text-white/40 group-open:rotate-90 transition-transform" />
                  </summary>
                  <div className="px-6 pb-6 text-white/70">{faq.answer}</div>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Other Services */}
        <section>
          <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
            <h2 className="font-serif text-2xl text-white mb-8">
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
                      <div className="rounded-xl border border-white/10 bg-[#0a2540] p-6 hover:border-[#2251ff]/50 transition-all">
                        <div
                          className={`w-12 h-12 rounded-lg ${svc.bgColor} flex items-center justify-center mb-4`}
                        >
                          <SvcIcon className={`w-6 h-6 ${svc.iconColor}`} />
                        </div>
                        <h3 className="text-white font-medium mb-2 group-hover:text-[#2251ff] transition-colors">
                          {svc.name}
                        </h3>
                        <p className="text-white/50 text-sm">{svc.tagline}</p>
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
