'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useParams, notFound } from 'next/navigation';
import {
  Plane,
  Building2,
  Calculator,
  Home,
  ArrowLeft,
  Check,
  Clock,
  Phone,
  Mail,
  MessageCircle,
  FileText,
  AlertCircle,
  ChevronRight,
  X,
  Info
} from 'lucide-react';

/**
 * Individual Service Page - Blog Style
 * Detailed pricing and service information
 */
// Get visa package color based on type (KITAS/KITAP = orange, Visit = blue)
function getVisaPackageColor(name: string): { bg: string; border: string; badge: string } {
  const lowerName = name.toLowerCase();
  // KITAS, KITAP, Working, Freelance, Investor KITAS, Spouse, Dependent, Retirement KITAS = Orange
  if (lowerName.includes('kitas') || lowerName.includes('kitap') ||
      lowerName.includes('working') || lowerName.includes('freelance') ||
      lowerName.includes('spouse') || lowerName.includes('dependent') ||
      lowerName.includes('retirement') || lowerName.includes('investor kitas')) {
    return {
      bg: 'bg-orange-500/20',
      border: 'border-orange-500/40 hover:border-orange-400',
      badge: 'bg-orange-500'
    };
  }
  // Visit visas (C, D series) = Blue
  return {
    bg: 'bg-sky-500/20',
    border: 'border-sky-500/40 hover:border-sky-400',
    badge: 'bg-sky-500'
  };
}

export default function ServiceDetailPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [selectedPackage, setSelectedPackage] = React.useState<typeof SERVICES_DATA.visa.packages[0] | null>(null);

  const service = SERVICES_DATA[slug];

  if (!service) {
    notFound();
  }

  // Close modal on escape key
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedPackage(null);
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, []);

  return (
    <div className="min-h-screen bg-[#051C2C]">
      {/* Breadcrumb */}
      <div className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-4">
          <nav className="flex items-center gap-2 text-sm">
            <Link href="/services" className="text-white/50 hover:text-white transition-colors">
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
                <div className={`w-16 h-16 rounded-xl ${service.bgColor} flex items-center justify-center flex-shrink-0`}>
                  <service.icon className={`w-8 h-8 ${service.iconColor}`} />
                </div>
                <div>
                  <h1 className="font-serif text-3xl lg:text-4xl text-white mb-2">
                    {service.name}
                  </h1>
                  <p className="text-white/60 text-lg">{service.tagline}</p>
                </div>
              </div>

              <p className="text-white/70 text-lg leading-relaxed mb-8">
                {service.description}
              </p>

              {/* Key Info */}
              <div className="grid grid-cols-3 gap-4 mb-8">
                <div className="bg-[#0a2540] rounded-lg p-4">
                  <Clock className="w-5 h-5 text-[#2251ff] mb-2" />
                  <p className="text-white/40 text-xs uppercase tracking-wider">Timeline</p>
                  <p className="text-white font-medium">{service.timeline}</p>
                </div>
                <div className="bg-[#0a2540] rounded-lg p-4">
                  <FileText className="w-5 h-5 text-[#2251ff] mb-2" />
                  <p className="text-white/40 text-xs uppercase tracking-wider">Documents</p>
                  <p className="text-white font-medium">{service.documentsRequired}</p>
                </div>
                <div className="bg-[#0a2540] rounded-lg p-4">
                  <AlertCircle className="w-5 h-5 text-[#2251ff] mb-2" />
                  <p className="text-white/40 text-xs uppercase tracking-wider">Validity</p>
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
                    src="/images/balizero-logo.png"
                    alt="Bali Zero"
                    width={52}
                    height={52}
                    className="rounded-full border-2 border-white/30"
                  />
                </div>
                <h3 className="text-white font-medium mb-2">Free Consultation</h3>
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
                <Link
                  href="/chat"
                  className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg border border-white/40 text-white font-medium hover:bg-white/10 transition-colors"
                >
                  <Image src="/images/zantara-lotus.png" alt="" width={24} height={24} />
                  Ask Zantara AI
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Table */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <h2 className="font-serif text-2xl text-white mb-8">Pricing</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {service.packages.map((pkg, index) => {
              // Use visa colors for visa service
              const visaColors = slug === 'visa' ? getVisaPackageColor(pkg.name) : null;

              return (
              <div
                key={pkg.name}
                className={`rounded-xl border p-6 cursor-pointer transition-all hover:scale-[1.02] ${
                  slug === 'visa' && visaColors
                    ? `${visaColors.bg} ${visaColors.border}`
                    : pkg.popular
                      ? 'border-[#2251ff] bg-[#2251ff]/10 hover:border-[#2251ff]'
                      : 'border-white/10 bg-[#0a2540] hover:border-white/30'
                }`}
                onClick={() => setSelectedPackage(pkg)}
              >
                {pkg.popular && (
                  <span className={`inline-block px-3 py-1 rounded-full text-white text-xs font-medium mb-4 ${
                    slug === 'visa' && visaColors ? visaColors.badge : 'bg-[#2251ff]'
                  }`}>
                    Most Popular
                  </span>
                )}
                <h3 className="text-white font-medium text-lg mb-2">{pkg.name}</h3>
                <p className="text-white/50 text-sm mb-4">{pkg.description}</p>

                <div className="mb-6">
                  {pkg.price === 'Contact' ? (
                    <span className="text-2xl font-bold text-[#2251ff]">Contact for quote</span>
                  ) : (
                    <>
                      <span className="text-3xl font-bold text-white">{pkg.price}</span>
                      <span className="text-white/40 text-sm ml-2">IDR</span>
                    </>
                  )}
                </div>

                <ul className="space-y-3 mb-6">
                  {pkg.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2 text-white/70 text-sm">
                      <Check className="w-4 h-4 text-[#22c55e] mt-0.5 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>

                <button
                  className={`flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg font-medium transition-colors ${
                    slug === 'visa' && visaColors
                      ? `${visaColors.badge} text-white hover:opacity-90`
                      : pkg.popular
                        ? 'bg-[#2251ff] text-white hover:bg-[#1a41cc]'
                        : 'border border-white/20 text-white hover:bg-white/10'
                  }`}
                >
                  <Info className="w-4 h-4" />
                  More Details
                </button>
              </div>
            );
            })}
          </div>

          <p className="text-white/40 text-sm text-center mt-8">
            * All-inclusive pricing. No hidden fees.
          </p>
        </div>
      </section>

      {/* What's Included */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <h2 className="font-serif text-2xl text-white mb-8">What's Included</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {service.included.map((item, i) => (
              <div key={i} className="flex items-center gap-3 bg-[#0a2540] rounded-lg p-4">
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
          <h2 className="font-serif text-2xl text-white mb-8">Requirements</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-white font-medium mb-4">Documents Needed</h3>
              <ul className="space-y-3">
                {service.requirements.documents.map((doc, i) => (
                  <li key={i} className="flex items-start gap-2 text-white/70 text-sm">
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
                  <li key={i} className="flex items-start gap-2 text-white/70 text-sm">
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
          <h2 className="font-serif text-2xl text-white mb-8">Frequently Asked Questions</h2>

          <div className="space-y-4">
            {service.faqs.map((faq, i) => (
              <details key={i} className="group bg-[#0a2540] rounded-lg">
                <summary className="flex items-center justify-between cursor-pointer p-6 text-white font-medium">
                  {faq.question}
                  <ChevronRight className="w-5 h-5 text-white/40 group-open:rotate-90 transition-transform" />
                </summary>
                <div className="px-6 pb-6 text-white/70">
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
          <h2 className="font-serif text-2xl text-white mb-8">Other Services</h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {Object.entries(SERVICES_DATA)
              .filter(([key]) => key !== slug)
              .slice(0, 3)
              .map(([key, svc]) => (
                <Link key={key} href={`/services/${key}`} className="group">
                  <div className="rounded-xl border border-white/10 bg-[#0a2540] p-6 hover:border-[#2251ff]/50 transition-all">
                    <div className={`w-12 h-12 rounded-lg ${svc.bgColor} flex items-center justify-center mb-4`}>
                      <svc.icon className={`w-6 h-6 ${svc.iconColor}`} />
                    </div>
                    <h3 className="text-white font-medium mb-2 group-hover:text-[#2251ff] transition-colors">
                      {svc.name}
                    </h3>
                    <p className="text-white/50 text-sm">{svc.tagline}</p>
                  </div>
                </Link>
              ))}
          </div>
        </div>
      </section>

      {/* Modal Popup */}
      {selectedPackage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => setSelectedPackage(null)}
        >
          <div
            className="relative w-full max-w-lg bg-[#0a2540] rounded-2xl border border-white/10 shadow-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              onClick={() => setSelectedPackage(null)}
              className="absolute top-4 right-4 p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
            >
              <X className="w-5 h-5 text-white" />
            </button>

            {/* Modal Content */}
            <div className="p-8">
              {/* Header */}
              {selectedPackage.popular && (
                <span className="inline-block px-3 py-1 rounded-full bg-[#2251ff] text-white text-xs font-medium mb-4">
                  Most Popular
                </span>
              )}
              <h2 className="font-serif text-2xl text-white mb-2">{selectedPackage.name}</h2>
              <p className="text-white/60 mb-6">{selectedPackage.description}</p>

              {/* Price */}
              <div className="bg-[#051C2C] rounded-xl p-4 mb-6">
                {selectedPackage.price === 'Contact' ? (
                  <span className="text-2xl font-bold text-[#2251ff]">Contact for quote</span>
                ) : (
                  <div>
                    <span className="text-3xl font-bold text-white">{selectedPackage.price}</span>
                    <span className="text-white/40 text-sm ml-2">IDR</span>
                    <p className="text-[#22c55e] text-sm mt-1">All-inclusive pricing</p>
                  </div>
                )}
              </div>

              {/* Features */}
              <h3 className="text-white font-medium mb-3">What's Included:</h3>
              <ul className="space-y-3 mb-6">
                {selectedPackage.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-3 text-white/80">
                    <Check className="w-5 h-5 text-[#22c55e] mt-0.5 flex-shrink-0" />
                    {feature}
                  </li>
                ))}
              </ul>

              {/* Additional Info */}
              <div className="bg-[#051C2C] rounded-xl p-4 mb-6">
                <h4 className="text-white/60 text-sm uppercase tracking-wider mb-2">Our Service Includes:</h4>
                <ul className="text-white/70 text-sm space-y-1">
                  <li>• Document preparation & review</li>
                  <li>• Government submission & liaison</li>
                  <li>• Status tracking & updates</li>
                  <li>• Dedicated support throughout</li>
                </ul>
              </div>

              {/* WhatsApp CTA */}
              <Link
                href={`https://wa.me/6285904369574?text=${encodeURIComponent(`Hi, I'm interested in ${selectedPackage.name}. Can you help me?`)}`}
                target="_blank"
                className="flex items-center justify-center gap-2 w-full px-6 py-4 rounded-xl bg-[#25D366] text-white font-medium hover:bg-[#20BD5A] transition-colors mb-3"
              >
                <Phone className="w-5 h-5" />
                Chat on WhatsApp
              </Link>

              <Link
                href="/chat"
                className="flex items-center justify-center gap-2 w-full px-6 py-3 rounded-xl border border-white/20 text-white font-medium hover:bg-white/10 transition-colors"
              >
                <Image src="/images/zantara-lotus.png" alt="" width={24} height={24} />
                Ask Zantara AI
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Service Data
const SERVICES_DATA: Record<string, ServiceData> = {
  visa: {
    name: 'Visa & Immigration',
    slug: 'visa',
    tagline: 'Complete visa solutions for living and working in Indonesia',
    description: 'Navigate Indonesia\'s immigration system with confidence. From short-term visit visas to permanent residency, we handle all visa types with full government compliance and ongoing support.',
    icon: Plane,
    bgColor: 'bg-rose-500/10',
    iconColor: 'text-rose-400',
    timeline: '7-10 days / 4-6 weeks (Working/Freelance)',
    documentsRequired: '5-10 docs',
    validity: '30 days - Permanent',
    packages: [
      // === VISIT VISAS (C) ===
      {
        name: 'C1 Visit Visa',
        description: 'Tourism, friends/family, meetings',
        price: '2.300.000',
        features: [
          '60 days initial (max 180 days)',
          '7-10 days processing',
          'Extension: 1.700.000 IDR each',
        ],
        popular: false,
      },
      {
        name: 'C2 Business Visa',
        description: 'Business activities & meetings',
        price: '3.600.000',
        features: [
          '60 days (extendable to 180)',
          '7-10 days processing',
          'Extension: 1.700.000 IDR each',
        ],
        popular: false,
      },
      {
        name: 'C7 Professional Visa',
        description: 'Chefs, yoga instructors, photographers',
        price: '4.500.000',
        features: [
          '30 days validity',
          'Event participation visa',
          'Including urgent processing',
        ],
        popular: false,
      },
      {
        name: 'C7AB Music Visa',
        description: 'Musical performances & events',
        price: '4.500.000',
        features: [
          'For music performances',
          'Event-based validity',
          'Including urgent processing',
        ],
        popular: false,
      },
      {
        name: 'C22A Academic Internship',
        description: 'Academic internship programs',
        price: '4.800.000',
        features: [
          '60 days (or 5.8M for 180 days)',
          'For academic requirements',
          'Educational institutions',
        ],
        popular: false,
      },
      {
        name: 'C22B Skills Development',
        description: 'Company training programs',
        price: '4.800.000',
        features: [
          '60 days (or 5.8M for 180 days)',
          'Company-sponsored training',
          'Professional development',
        ],
        popular: false,
      },
      // === MULTIPLE ENTRY VISAS (D) ===
      {
        name: 'D1 Multiple Entry Visit',
        description: 'Tourism & family visits',
        price: 'Contact',
        features: [
          '1 or 2 years validity',
          'Multiple entries allowed',
          'Meetings, exhibitions, tourism',
        ],
        popular: false,
      },
      {
        name: 'D2 Multiple Entry Business',
        description: 'Frequent business travelers',
        price: 'Contact',
        features: [
          '1 or 2 years validity',
          'Multiple entries allowed',
          'Business activities & shopping',
        ],
        popular: false,
      },
      {
        name: 'D12 Investment Investigation',
        description: 'Pre-investment site visits',
        price: '7.500.000',
        features: [
          '1 year (or 10M for 2 years)',
          '7-10 days processing',
          'Path to investor visa',
        ],
        popular: false,
      },
      // === KITAS (WORK & STAY PERMITS) - Ordered by code ===
      {
        name: 'Working KITAS (E23)',
        description: 'Employment permit with sponsor',
        price: '34.500.000',
        features: [
          '1 year validity (renewable)',
          '4-6 weeks processing (RPTKA + IMTA)',
          'Company sponsorship required',
        ],
        popular: false,
      },
      {
        name: 'Freelance KITAS (E23)',
        description: 'For freelancers & remote workers',
        price: '26.000.000',
        features: [
          'Up to 6 months validity',
          '4-6 weeks processing (RPTKA + IMTA)',
          'Work without specific employer',
        ],
        popular: true,
      },
      {
        name: 'Investor KITAS (E28A)',
        description: 'For PT PMA investors',
        price: '17.000.000',
        features: [
          '2 years validity',
          '7-10 days processing',
          'Extension: 18.000.000 IDR',
        ],
        popular: false,
      },
      {
        name: 'Spouse KITAS (E31A)',
        description: 'Married to Indonesian citizen',
        price: '11.000.000',
        features: [
          '1 year (or 15M for 2 years)',
          '7-10 days processing',
          'Marriage certificate required',
        ],
        popular: false,
      },
      {
        name: 'Dependent KITAS (E31B/F)',
        description: 'Family of KITAS holders',
        price: '11.000.000',
        features: [
          '1 year (or 15M for 2 years)',
          '7-10 days processing',
          'Linked to main permit holder',
        ],
        popular: false,
      },
      {
        name: 'Retirement KITAS (E33F)',
        description: 'For retirees aged 60+',
        price: '14.000.000',
        features: [
          '1 year validity',
          '7-10 days processing',
          'Extension: 10.000.000 IDR',
        ],
        popular: false,
      },
      // === KITAP (PERMANENT RESIDENCE) ===
      {
        name: 'Investor KITAP',
        description: 'Permanent residence for investors',
        price: '55.000.000',
        features: [
          'Permanent residence + MERP',
          'Consecutive KITAS required',
          'Expedited processing available',
        ],
        popular: false,
      },
      {
        name: 'Working KITAP',
        description: 'Permanent residence for workers',
        price: 'Contact',
        features: [
          'Permanent residence',
          '4 consecutive KITAS required',
          'For established workers',
        ],
        popular: false,
      },
      {
        name: 'Family KITAP',
        description: 'Family of Indonesian citizens',
        price: '33.000.000',
        features: [
          'Permanent residence + MERP',
          'For Indonesian citizen families',
          'Expedited processing available',
        ],
        popular: false,
      },
      {
        name: 'Retirement KITAP',
        description: 'Permanent residence for retirees',
        price: '45.000.000',
        features: [
          'Permanent residence + MERP',
          'Consecutive KITAS required',
          'For established retirees',
        ],
        popular: false,
      },
    ],
    included: [
      'Document review and preparation',
      'Government liaison and submission',
      'Status tracking and updates',
      'Translation services',
      'Immigration interview coaching',
      'SKTT/SKLD registration',
      'Re-entry permit arrangement',
      'Renewal reminders',
    ],
    requirements: {
      documents: [
        'Valid passport (min 18 months validity)',
        'Passport-size photos (4x6, red background)',
        'Sponsorship letter (for KITAS)',
        'CV/Resume and educational certificates',
        'Proof of income/financial capacity',
        'Medical check-up results',
        'Police clearance from home country',
      ],
      eligibility: [
        'No criminal record',
        'Valid sponsor (company or individual)',
        'Meet minimum investment (for investor visa)',
        'Relevant qualifications (for work visa)',
        'Age 60+ for retirement KITAS',
      ],
    },
    faqs: [
      {
        question: 'How long does KITAS processing take?',
        answer: 'Most visas and KITAS (C, D, E series) take 7-10 days from application to e-visa issuance. Only Working and Freelance KITAS take 4-6 weeks due to RPTKA and IMTA approval process.',
      },
      {
        question: 'Can I work while my KITAS is being processed?',
        answer: 'No, you cannot legally work until your KITAS and IMTA are approved. You can stay on a visitor visa during processing.',
      },
      {
        question: 'What\'s the difference between offshore and onshore pricing?',
        answer: 'Offshore means applying from outside Indonesia (often faster), onshore means converting from within Indonesia. Onshore is typically 2-4 million IDR more.',
      },
      {
        question: 'What is the path to permanent residency (KITAP)?',
        answer: 'After holding KITAS for 4-5 consecutive years, you can apply for KITAP which grants permanent residence. We help with the transition.',
      },
    ],
  },
  company: {
    name: 'Company Setup & Licenses',
    slug: 'company',
    tagline: 'From licenses to structure — launch your business fast',
    description: 'Start your Indonesian business the right way. We handle PT PMA/PMDN formation, business licensing through OSS, special permits like alcohol licenses, and ongoing compliance so you can focus on growth.',
    icon: Building2,
    bgColor: 'bg-orange-500/10',
    iconColor: 'text-orange-400',
    timeline: '2-12 weeks',
    documentsRequired: '10-15 docs',
    validity: 'Perpetual',
    packages: [
      {
        name: 'Company Revision',
        description: 'Changes to existing company',
        price: '7.000.000',
        features: [
          'Director/shareholder changes',
          'Business activity updates',
          'Address changes',
          'Capital adjustments',
          'Ministry of Law filing',
        ],
        popular: false,
      },
      {
        name: 'Alcohol License',
        description: 'SIUP-MB for alcohol sales',
        price: '15.000.000',
        features: [
          'Restaurant/bar alcohol permit',
          'Full OSS registration',
          'Category A/B/C licensing',
          'Compliance documentation',
          'Renewal guidance',
        ],
        popular: false,
      },
      {
        name: 'PT PMA/PMDN Setup',
        description: 'Full company establishment',
        price: '20.000.000',
        features: [
          'Company registration',
          'Deed of establishment',
          'NIB & OSS licenses',
          'Tax registration (NPWP)',
          'Bank account assistance',
          'Company stamp',
        ],
        popular: true,
      },
    ],
    included: [
      'Company name reservation',
      'Deed of establishment',
      'Ministry of Law approval',
      'NIB (Business ID Number)',
      'OSS licenses & permits',
      'Tax registration (NPWP/PKP)',
      'Company stamp',
      'Digital document copies',
    ],
    requirements: {
      documents: [
        'Shareholder passports/KTP',
        'Director passport & KITAS (if foreign)',
        'Proof of address (all shareholders)',
        'Company name options (3)',
        'Business plan summary',
        'Paid-up capital proof',
      ],
      eligibility: [
        'Minimum 2 shareholders',
        'Minimum 1 director',
        'Paid-up capital (varies by sector)',
        'Business activity on positive list',
      ],
    },
    faqs: [
      {
        question: 'What is the minimum capital for PT PMA?',
        answer: 'The minimum investment is IDR 10 billion (~USD 650,000), with IDR 2.5 billion (~USD 160,000) paid-up capital. Some sectors have different requirements.',
      },
      {
        question: 'Can foreigners own 100% of a PT PMA?',
        answer: 'Yes, for most business sectors. Some sectors have foreign ownership restrictions. We\'ll advise on your specific case.',
      },
      {
        question: 'How long does PT PMA setup take?',
        answer: 'Typically 4-8 weeks for full registration including all licenses. Expedited processing available.',
      },
      {
        question: 'Do I need a physical office for my company?',
        answer: 'Yes, Indonesian law requires a registered business address. We can help with virtual office solutions that meet legal requirements.',
      },
    ],
  },
  tax: {
    name: 'Tax Consulting',
    slug: 'tax',
    tagline: "Navigate Indonesia's tax system with confidence",
    description: 'Indonesian tax compliance made simple. From NPWP registration to annual SPT filing, corporate tax planning to personal income optimization — we handle it all with expert precision.',
    icon: Calculator,
    bgColor: 'bg-amber-500/10',
    iconColor: 'text-amber-400',
    timeline: 'Ongoing',
    documentsRequired: 'Varies',
    validity: 'Annual',
    packages: [
      {
        name: 'Tax Registration (NPWP)',
        description: 'Get your Indonesian Tax ID',
        price: 'Contact',
        features: [
          'Personal or corporate NPWP',
          'Full documentation support',
          'Tax office registration',
          'Digital NPWP card',
        ],
        popular: false,
      },
      {
        name: 'Tax Filing (SPT)',
        description: 'Annual tax return submission',
        price: 'Contact',
        features: [
          'Personal & corporate SPT',
          'Income calculation',
          'Deduction optimization',
          'E-filing submission',
          'Payment guidance',
        ],
        popular: true,
      },
      {
        name: 'Corporate Tax Planning',
        description: 'Strategic tax optimization',
        price: 'Contact',
        features: [
          'Tax structure review',
          'Compliance assessment',
          'Withholding tax (PPh 21/23/26)',
          'VAT registration & filing',
          'Transfer pricing support',
        ],
        popular: false,
      },
    ],
    included: [
      'NPWP registration/update',
      'Tax calculation & filing',
      'Payment slip preparation (SSP)',
      'Archive of all filings',
      'Deadline reminders',
      'Tax office liaison',
      'Audit support',
      'Tax optimization advice',
    ],
    requirements: {
      documents: [
        'NPWP (Tax ID) or application docs',
        'Previous year tax returns (if any)',
        'Income statements/certificates',
        'Bank statements',
        'Business financial records',
        'Employee data (for corporate)',
      ],
      eligibility: [
        'Valid passport/KTP',
        'Indonesian resident status (for personal)',
        'Active company with NIB (for corporate)',
        'KITAS holders must file taxes',
      ],
    },
    faqs: [
      {
        question: 'When is the tax filing deadline?',
        answer: 'Personal tax (SPT) is due March 31. Corporate tax is due April 30. Monthly taxes are due by the 15th of the following month.',
      },
      {
        question: 'Do expats need to file Indonesian taxes?',
        answer: 'Yes, if you stay 183+ days in Indonesia, you\'re a tax resident and must file. KITAS holders are automatically tax residents. We can help determine your status.',
      },
      {
        question: 'What are the tax rates in Indonesia?',
        answer: 'Personal income tax ranges from 5-35%. Corporate tax is 22% (20% for public companies). We can help optimize your structure.',
      },
      {
        question: 'What is the difference between PPh 21, 23, and 26?',
        answer: 'PPh 21 is employee income tax, PPh 23 is withholding on services/royalties, and PPh 26 is withholding for non-residents. Each has different rates and filing requirements.',
      },
    ],
  },
  property: {
    name: 'Real Estate Services',
    slug: 'property',
    tagline: 'Secure property with legal clarity and guidance',
    description: 'Navigate Indonesian property law with confidence. From due diligence to leasehold agreements, building permits to ownership structures — we protect your investment every step of the way.',
    icon: Home,
    bgColor: 'bg-emerald-500/10',
    iconColor: 'text-emerald-400',
    timeline: '1-8 weeks',
    documentsRequired: 'Varies',
    validity: 'Per transaction',
    packages: [
      {
        name: 'Legal Due Diligence',
        description: 'Complete property verification',
        price: 'Contact',
        features: [
          'Certificate authenticity check',
          'Ownership history verification',
          'Zoning & land use compliance',
          'Encumbrance/lien search',
          'Detailed written report',
        ],
        popular: false,
      },
      {
        name: 'Leasehold Agreement (Hak Sewa)',
        description: 'Long-term rental contracts',
        price: 'Contact',
        features: [
          'Contract drafting in English/Indonesian',
          'Terms negotiation support',
          'Notarization & legalization',
          'Registration at land office',
          'Up to 25+25+25 year terms',
        ],
        popular: true,
      },
      {
        name: 'IMB & Building Permits',
        description: 'Construction permits',
        price: 'Contact',
        features: [
          'Building permit application (IMB/PBG)',
          'Site plan approval',
          'Environmental compliance (AMDAL/UKL-UPL)',
          'Occupancy certificate (SLF)',
          'Renovation permits',
        ],
        popular: false,
      },
      {
        name: 'Ownership Structures (PT PMA)',
        description: 'Foreign ownership solutions',
        price: 'Contact',
        features: [
          'PT PMA for property holding',
          'Hak Guna Bangunan (HGB) rights',
          'Asset protection setup',
          'Tax-efficient structuring',
          'Succession planning',
        ],
        popular: false,
      },
    ],
    included: [
      'Property inspection coordination',
      'Legal document review',
      'Ownership & title verification',
      'Tax assessment review (PBB/BPHTB)',
      'Contract drafting/review',
      'Notary coordination',
      'Land office registration',
      'Post-transaction support',
    ],
    requirements: {
      documents: [
        'Property certificate copy (SHM/HGB/SHGB)',
        'Owner ID/company documents',
        'Tax payment receipts (PBB)',
        'Building permit (IMB/PBG)',
        'Site plan & location permit',
        'Buyer identification (passport/KTP)',
      ],
      eligibility: [
        'Foreigners can lease (up to 80 years total)',
        'PT PMA can hold HGB rights',
        'Hak Pakai available for KITAS holders',
        'Investment thresholds may apply',
      ],
    },
    faqs: [
      {
        question: 'Can foreigners own property in Indonesia?',
        answer: 'Foreigners cannot own freehold (Hak Milik) but can hold long-term leases (Hak Sewa up to 80 years), Hak Pakai (Right of Use), or own through a PT PMA company.',
      },
      {
        question: 'What is Hak Guna Bangunan (HGB)?',
        answer: 'HGB is a right to build and own structures on land. PT PMA companies can hold HGB for 30+20+20 years (70 years total), renewable.',
      },
      {
        question: 'Is nominee ownership safe?',
        answer: 'Nominee arrangements are legally risky and can result in total loss of your investment. We strongly recommend proper structures like PT PMA or notarized leases.',
      },
      {
        question: 'What is the difference between IMB and PBG?',
        answer: 'IMB (Izin Mendirikan Bangunan) is the old building permit system. PBG (Persetujuan Bangunan Gedung) is the new system under OSS. We handle both.',
      },
    ],
  },
};

interface ServiceData {
  name: string;
  slug: string;
  tagline: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  bgColor: string;
  iconColor: string;
  timeline: string;
  documentsRequired: string;
  validity: string;
  packages: {
    name: string;
    description: string;
    price: string;
    features: string[];
    popular: boolean;
  }[];
  included: string[];
  requirements: {
    documents: string[];
    eligibility: string[];
  };
  faqs: {
    question: string;
    answer: string;
  }[];
}
