import type { Metadata } from "next";
import Link from "next/link";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";

export const metadata: Metadata = {
  title: "Property Services in Bali — Leasehold, Freehold & Investment",
  description:
    "Expert property services in Bali. Leasehold advisory, freehold structuring, investment analysis. Powered by AI zoning intelligence. Trusted by 5000+ clients.",
  alternates: {
    canonical: "https://balizero.com/property",
  },
  openGraph: {
    title: "Property Services in Bali | Bali Zero",
    description:
      "Expert property advisory for foreigners in Bali. Leasehold, freehold, investment guidance with AI-powered zoning intelligence.",
    url: "https://balizero.com/property",
  },
};

const services = [
  {
    title: "Leasehold Advisory",
    icon: (
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
    points: [
      "Contract review and negotiation",
      "Due diligence on land certificates (SHM, HGB)",
      "Lease extension and renewal strategies",
      "Notaris coordination and legalization",
    ],
  },
  {
    title: "Freehold Structuring",
    icon: (
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
        <line x1="3" y1="9" x2="21" y2="9" />
        <line x1="9" y1="21" x2="9" y2="9" />
      </svg>
    ),
    points: [
      "PT PMA property holding structures",
      "Nominee arrangement compliance",
      "Land use permit (IMB/PBG) advisory",
      "Tax optimization for property ownership",
    ],
  },
  {
    title: "Investment Analysis",
    icon: (
      <svg
        width="32"
        height="32"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
    points: [
      "ROI projections for Bali property",
      "Zoning and land-use compliance check",
      "Market comparisons by area",
      "Exit strategy planning",
    ],
  },
];

export default function PropertyPage() {
  return (
    <div className="max-w-[1200px] mx-auto px-4 sm:px-6 lg:px-8">
      {/* Hero */}
      <section className="py-16 md:py-24 text-center">
        <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs text-white/60">
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          Property Services
        </div>
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight text-white mb-6">
          Property in Bali, <span className="text-accent-warm">done right</span>
        </h1>
        <p className="text-lg text-white/60 max-w-2xl mx-auto mb-8 leading-relaxed">
          Navigate Indonesia&apos;s property regulations with expert guidance.
          From leasehold contracts to PT PMA structuring, we protect your
          investment at every step.
        </p>
        <div className="flex items-center justify-center gap-4 flex-wrap">
          <a
            href={buildWhatsAppLink("property")}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-accent-warm hover:bg-[#c07348] text-white font-medium transition-colors"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            Talk to an Expert
          </a>
          <Link
            href="https://prime.balizero.com"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-white/80 font-medium transition-colors"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            Prime Zoning Maps
          </Link>
        </div>
      </section>

      {/* Services */}
      <section className="pb-16 md:pb-24">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {services.map((service) => (
            <div
              key={service.title}
              className="rounded-2xl p-6 transition-all duration-300 hover:-translate-y-0.5"
              style={{
                background: "rgba(10, 37, 64, 0.3)",
                border: "1px solid rgba(255, 255, 255, 0.06)",
                backdropFilter: "blur(12px)",
              }}
            >
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
                style={{
                  background: "rgba(212, 132, 90, 0.1)",
                  color: "#d4845a",
                }}
              >
                {service.icon}
              </div>
              <h3 className="text-lg font-semibold text-white mb-3">
                {service.title}
              </h3>
              <ul className="space-y-2">
                {service.points.map((point) => (
                  <li
                    key={point}
                    className="flex items-start gap-2 text-sm text-white/60"
                  >
                    <svg
                      className="w-4 h-4 mt-0.5 flex-shrink-0 text-accent-warm/60"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Prime Intelligence callout */}
      <section className="pb-16 md:pb-24">
        <div
          className="rounded-2xl p-8 md:p-10 text-center"
          style={{
            background:
              "linear-gradient(135deg, rgba(46, 111, 212, 0.08), rgba(212, 132, 90, 0.08))",
            border: "1px solid rgba(255, 255, 255, 0.06)",
          }}
        >
          <h2 className="text-xl md:text-2xl font-bold text-white mb-3">
            Powered by Prime Intelligence
          </h2>
          <p className="text-sm text-white/60 max-w-lg mx-auto mb-6">
            Our 3D zoning maps let you verify land-use regulations before you
            invest. Check building restrictions, zoning classifications, and
            development potential for any location in Bali.
          </p>
          <Link
            href="https://prime.balizero.com"
            className="inline-flex items-center gap-2 text-sm font-medium text-[#2E6FD4] hover:text-[#4a87e8] transition-colors"
          >
            Explore Prime Maps
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M5 12h14" />
              <path d="m12 5 7 7-7 7" />
            </svg>
          </Link>
        </div>
      </section>

      {/* Bottom CTA */}
      <section className="pb-16 md:pb-24 text-center">
        <h2 className="text-2xl font-bold text-white mb-3">
          Ready to invest in Bali?
        </h2>
        <p className="text-sm text-white/60 mb-6">
          Get a free 15-minute consultation with our property team.
        </p>
        <a
          href={buildWhatsAppLink("property")}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-accent-warm hover:bg-[#c07348] text-white font-medium transition-colors text-lg"
        >
          Contact Us on WhatsApp
        </a>
      </section>
    </div>
  );
}
