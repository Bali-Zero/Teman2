'use client';

import * as React from 'react';
import Link from 'next/link';
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
  ChevronRight
} from 'lucide-react';

/**
 * Individual Service Page - Blog Style
 * Detailed pricing and service information
 */
export default function ServiceDetailPage() {
  const params = useParams();
  const slug = params.slug as string;

  const service = SERVICES_DATA[slug];

  if (!service) {
    notFound();
  }

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
                  <MessageCircle className="w-4 h-4" />
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
            {service.packages.map((pkg, index) => (
              <div
                key={pkg.name}
                className={`rounded-xl border p-6 ${
                  pkg.popular
                    ? 'border-[#2251ff] bg-[#2251ff]/10'
                    : 'border-white/10 bg-[#0a2540]'
                }`}
              >
                {pkg.popular && (
                  <span className="inline-block px-3 py-1 rounded-full bg-[#2251ff] text-white text-xs font-medium mb-4">
                    Most Popular
                  </span>
                )}
                <h3 className="text-white font-medium text-lg mb-2">{pkg.name}</h3>
                <p className="text-white/50 text-sm mb-4">{pkg.description}</p>

                <div className="mb-6">
                  <span className="text-3xl font-bold text-white">{pkg.price}</span>
                  <span className="text-white/40 text-sm ml-2">IDR</span>
                </div>

                <ul className="space-y-3 mb-6">
                  {pkg.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2 text-white/70 text-sm">
                      <Check className="w-4 h-4 text-[#22c55e] mt-0.5 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>

                <Link
                  href="https://wa.me/6285904369574"
                  target="_blank"
                  className={`flex items-center justify-center w-full px-4 py-3 rounded-lg font-medium transition-colors ${
                    pkg.popular
                      ? 'bg-[#2251ff] text-white hover:bg-[#1a41cc]'
                      : 'border border-white/20 text-white hover:bg-white/10'
                  }`}
                >
                  Get Started
                </Link>
              </div>
            ))}
          </div>

          <p className="text-white/40 text-sm text-center mt-8">
            * Prices exclude government fees. Contact us for a detailed quote.
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
    </div>
  );
}

// Service Data
const SERVICES_DATA: Record<string, ServiceData> = {
  visa: {
    name: 'Visa & Immigration',
    slug: 'visa',
    tagline: 'Stay and work legally in Indonesia',
    description: 'Navigate Indonesia\'s immigration system with confidence. We handle KITAS, KITAP, Golden Visa, and all permit types with full government compliance and ongoing support.',
    icon: Plane,
    bgColor: 'bg-rose-500/10',
    iconColor: 'text-rose-400',
    timeline: '2-8 weeks',
    documentsRequired: '5-10 docs',
    validity: '1-10 years',
    packages: [
      {
        name: 'Tourist Visa Extension',
        description: 'Extend your 60-day visa',
        price: '3.500.000',
        features: [
          '30-day extension',
          'Immigration handling',
          'Document preparation',
          'Pick-up & delivery',
        ],
        popular: false,
      },
      {
        name: 'KITAS (Work/Investor)',
        description: 'Stay permit for 1-2 years',
        price: '18.000.000',
        features: [
          'Full application handling',
          'Sponsor arrangement',
          'IMTA work permit included',
          'Multiple entry permit',
          'Airport pick-up assistance',
        ],
        popular: true,
      },
      {
        name: 'Golden Visa',
        description: '5-10 year premium stay',
        price: '35.000.000',
        features: [
          'Investment guidance',
          'Premium processing',
          'Family inclusion',
          'Dedicated case manager',
          'VIP immigration service',
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
        'Sponsorship letter',
        'CV/Resume',
        'Educational certificates',
        'Health insurance proof',
      ],
      eligibility: [
        'No criminal record',
        'Valid sponsor (company or individual)',
        'Meet minimum investment (for investor visa)',
        'Relevant qualifications (for work visa)',
      ],
    },
    faqs: [
      {
        question: 'How long does KITAS processing take?',
        answer: 'Standard KITAS processing takes 4-8 weeks from document submission. We offer expedited processing for urgent cases.',
      },
      {
        question: 'Can I work while my KITAS is being processed?',
        answer: 'No, you cannot legally work until your KITAS and IMTA are approved. You can stay on a visitor visa during processing.',
      },
      {
        question: 'What is the Golden Visa?',
        answer: 'The Golden Visa is Indonesia\'s premium residency program for high-net-worth individuals and investors, offering 5-10 year stays with simplified renewals.',
      },
    ],
  },
  company: {
    name: 'Company Setup',
    slug: 'company',
    tagline: 'Launch your business in Indonesia',
    description: 'Start your Indonesian business the right way. We handle PT PMA formation, business licensing, virtual offices, and ongoing compliance so you can focus on growth.',
    icon: Building2,
    bgColor: 'bg-orange-500/10',
    iconColor: 'text-orange-400',
    timeline: '4-12 weeks',
    documentsRequired: '10-15 docs',
    validity: 'Perpetual',
    packages: [
      {
        name: 'Virtual Office',
        description: 'Business address & mail handling',
        price: '5.000.000',
        features: [
          'Prestigious Bali address',
          'Mail & package handling',
          'Meeting room access (2hrs/mo)',
          'Phone answering service',
        ],
        popular: false,
      },
      {
        name: 'PT PMA Setup',
        description: 'Foreign-owned company',
        price: '35.000.000',
        features: [
          'Company registration',
          'NIB & business licenses',
          'Tax registration (NPWP)',
          'Bank account assistance',
          'Virtual office (1 year)',
        ],
        popular: true,
      },
      {
        name: 'Full Business Package',
        description: 'Company + Director KITAS',
        price: '55.000.000',
        features: [
          'Everything in PT PMA Setup',
          'Director KITAS (1 year)',
          'Annual compliance (1 year)',
          'Dedicated account manager',
          'Priority support',
        ],
        popular: false,
      },
    ],
    included: [
      'Company name reservation',
      'Deed of establishment',
      'Ministry of Law approval',
      'NIB (Business ID Number)',
      'OSS licenses',
      'Tax registration (NPWP/PKP)',
      'Company stamp',
      'Digital document copies',
    ],
    requirements: {
      documents: [
        'Shareholder passports',
        'Director passport & KITAS',
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
        answer: 'Typically 6-10 weeks for full registration. Expedited processing available for additional fee.',
      },
    ],
  },
  tax: {
    name: 'Tax & Compliance',
    slug: 'tax',
    tagline: 'Stay compliant, optimize taxes',
    description: 'Indonesian tax compliance made simple. We handle personal and corporate tax filings, annual reports, and strategic tax planning to keep you legal and optimized.',
    icon: Calculator,
    bgColor: 'bg-amber-500/10',
    iconColor: 'text-amber-400',
    timeline: 'Ongoing',
    documentsRequired: 'Varies',
    validity: 'Annual',
    packages: [
      {
        name: 'Personal Tax (SPT)',
        description: 'Annual tax return filing',
        price: '2.500.000',
        features: [
          'Income calculation',
          'Deduction optimization',
          'E-filing submission',
          'Payment guidance',
        ],
        popular: false,
      },
      {
        name: 'Corporate Monthly',
        description: 'Ongoing tax compliance',
        price: '5.000.000',
        features: [
          'Monthly tax calculation',
          'PPh 21/23/25/29 filing',
          'VAT filing (if applicable)',
          'Quarterly reports',
          'Tax consultation (2hrs/mo)',
        ],
        popular: true,
      },
      {
        name: 'Full Compliance',
        description: 'Tax + accounting + audit',
        price: '12.000.000',
        features: [
          'Everything in Corporate Monthly',
          'Full bookkeeping',
          'Financial statements',
          'Annual audit preparation',
          'Tax planning strategy',
        ],
        popular: false,
      },
    ],
    included: [
      'NPWP registration/update',
      'Tax calculation & filing',
      'Payment slip preparation',
      'Archive of all filings',
      'Deadline reminders',
      'Tax office liaison',
      'Audit support',
      'Tax optimization advice',
    ],
    requirements: {
      documents: [
        'NPWP (Tax ID)',
        'Previous year tax returns',
        'Income statements',
        'Bank statements',
        'Business financial records',
        'Employee data (for corporate)',
      ],
      eligibility: [
        'Valid NPWP',
        'Indonesian resident status (for personal)',
        'Active company (for corporate)',
      ],
    },
    faqs: [
      {
        question: 'When is the tax filing deadline?',
        answer: 'Personal tax (SPT) is due March 31. Corporate tax is due April 30. Monthly taxes are due by the 15th of the following month.',
      },
      {
        question: 'Do expats need to file Indonesian taxes?',
        answer: 'Yes, if you stay 183+ days in Indonesia, you\'re a tax resident and must file. We can help determine your status and obligations.',
      },
      {
        question: 'What are the tax rates in Indonesia?',
        answer: 'Personal income tax ranges from 5-35%. Corporate tax is 22% (20% for public companies). We can help optimize your structure.',
      },
    ],
  },
  property: {
    name: 'Property Services',
    slug: 'property',
    tagline: 'Secure your Indonesian property',
    description: 'Navigate Indonesian property law with confidence. We provide due diligence, lease agreements, and ownership structures to protect your investment.',
    icon: Home,
    bgColor: 'bg-emerald-500/10',
    iconColor: 'text-emerald-400',
    timeline: '1-4 weeks',
    documentsRequired: 'Varies',
    validity: 'Per transaction',
    packages: [
      {
        name: 'Due Diligence',
        description: 'Property legal check',
        price: '5.000.000',
        features: [
          'Certificate verification',
          'Ownership history check',
          'Zoning compliance',
          'Encumbrance search',
          'Written report',
        ],
        popular: false,
      },
      {
        name: 'Lease Agreement',
        description: 'Long-term rental contract',
        price: '7.500.000',
        features: [
          'Contract drafting',
          'Negotiation support',
          'Notarization',
          'Registration assistance',
          'Renewal clause included',
        ],
        popular: true,
      },
      {
        name: 'Full Acquisition',
        description: 'Purchase with PT structure',
        price: '25.000.000',
        features: [
          'Due diligence included',
          'PT PMA setup for property',
          'Purchase agreement',
          'Title transfer assistance',
          'Ongoing compliance setup',
        ],
        popular: false,
      },
    ],
    included: [
      'Property inspection coordination',
      'Legal document review',
      'Ownership verification',
      'Tax assessment review',
      'Contract drafting/review',
      'Notary coordination',
      'Registration assistance',
      'Post-purchase support',
    ],
    requirements: {
      documents: [
        'Property certificate copy',
        'Owner ID/company docs',
        'Tax payment receipts (PBB)',
        'Building permit (IMB)',
        'Land use certificate',
        'Buyer identification',
      ],
      eligibility: [
        'Foreigners can lease (max 80 years)',
        'PT PMA can own land/buildings',
        'Right of Use (Hak Pakai) for individuals',
        'Investment minimum may apply',
      ],
    },
    faqs: [
      {
        question: 'Can foreigners own property in Indonesia?',
        answer: 'Foreigners cannot own freehold land but can hold long-term leases (up to 80 years) or own through a PT PMA company structure.',
      },
      {
        question: 'What is Hak Pakai?',
        answer: 'Hak Pakai (Right of Use) allows foreigners to own buildings on leased land for 30 years, extendable to 80 years total.',
      },
      {
        question: 'Is nominee ownership safe?',
        answer: 'Nominee arrangements are legally risky. We recommend proper structures like PT PMA or long-term leases for security.',
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
