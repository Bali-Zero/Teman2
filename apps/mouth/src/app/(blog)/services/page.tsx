'use client';

import * as React from 'react';
import Link from 'next/link';
import {
  Plane,
  Building2,
  Calculator,
  Home,
  ArrowRight,
  Check,
  Clock,
  Shield,
  Users,
  MessageCircle,
  Phone,
  Mail,
  ChevronRight
} from 'lucide-react';

/**
 * Services Overview Page - Blog Style
 * McKinsey-inspired layout with pricing
 */
export default function ServicesPage() {
  return (
    <div className="min-h-screen bg-[#051C2C]">
      {/* Hero Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16 lg:py-24">
          <div className="max-w-3xl">
            <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-4 block">
              Our Services
            </span>
            <h1 className="font-serif text-4xl lg:text-5xl xl:text-6xl text-white leading-[1.1] mb-6">
              Build Your{' '}
              <span className="text-[#e85c41]">Indonesian Dream</span>{' '}
              with Confidence
            </h1>
            <p className="text-lg text-white/70 mb-8 leading-relaxed">
              From Zero to Infinity. We handle visas, company setup, taxes, and property —
              so you can focus on what matters most.
            </p>

            <div className="flex flex-wrap gap-4">
              <Link
                href="https://wa.me/6285904369574"
                target="_blank"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#2251ff] text-white font-medium hover:bg-[#1a41cc] transition-colors"
              >
                <Phone className="w-4 h-4" />
                WhatsApp Us
              </Link>
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-white/20 text-white font-medium hover:bg-white/10 transition-colors"
              >
                <MessageCircle className="w-4 h-4" />
                Ask Zantara AI
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Why Choose Us */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-12">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {TRUST_BADGES.map((badge) => (
              <div key={badge.label} className="text-center">
                <div className="w-12 h-12 rounded-lg bg-[#2251ff]/10 flex items-center justify-center mx-auto mb-3">
                  <badge.icon className="w-6 h-6 text-[#2251ff]" />
                </div>
                <p className="text-white font-medium">{badge.value}</p>
                <p className="text-white/50 text-sm">{badge.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Services Grid */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center mb-12">
            <h2 className="font-serif text-3xl text-white mb-4">Our Services & Pricing</h2>
            <p className="text-white/60 max-w-2xl mx-auto">
              Transparent pricing with no hidden fees. All prices in IDR.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {SERVICES.map((service) => (
              <Link
                key={service.slug}
                href={`/services/${service.slug}`}
                className="group"
              >
                <div className="h-full rounded-xl border border-white/10 bg-[#0a2540] p-8 hover:border-[#2251ff]/50 transition-all">
                  {/* Header */}
                  <div className="flex items-start gap-4 mb-6">
                    <div className={`w-14 h-14 rounded-xl ${service.bgColor} flex items-center justify-center flex-shrink-0`}>
                      <service.icon className={`w-7 h-7 ${service.iconColor}`} />
                    </div>
                    <div>
                      <h3 className="font-serif text-xl text-white mb-1 group-hover:text-[#2251ff] transition-colors">
                        {service.name}
                      </h3>
                      <p className="text-white/60 text-sm">{service.tagline}</p>
                    </div>
                  </div>

                  {/* Pricing */}
                  <div className="mb-6">
                    <p className="text-white/40 text-xs uppercase tracking-wider mb-2">Starting from</p>
                    <p className="text-2xl font-bold text-white">
                      {service.startingPrice}
                      <span className="text-white/40 text-sm font-normal ml-2">IDR</span>
                    </p>
                  </div>

                  {/* Features */}
                  <ul className="space-y-2 mb-6">
                    {service.highlights.map((item, i) => (
                      <li key={i} className="flex items-center gap-2 text-white/70 text-sm">
                        <Check className="w-4 h-4 text-[#22c55e]" />
                        {item}
                      </li>
                    ))}
                  </ul>

                  {/* CTA */}
                  <div className="flex items-center gap-2 text-[#2251ff] font-medium group-hover:gap-3 transition-all">
                    View details & pricing
                    <ArrowRight className="w-4 h-4" />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Process Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center mb-12">
            <h2 className="font-serif text-3xl text-white mb-4">How It Works</h2>
            <p className="text-white/60">Simple, transparent, professional</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {PROCESS_STEPS.map((step, index) => (
              <div key={step.title} className="text-center">
                <div className="w-12 h-12 rounded-full bg-[#2251ff] text-white font-bold text-lg flex items-center justify-center mx-auto mb-4">
                  {index + 1}
                </div>
                <h3 className="text-white font-medium mb-2">{step.title}</h3>
                <p className="text-white/50 text-sm">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Contact CTA */}
      <section className="bg-gradient-to-br from-[#e85c41] to-[#d14832]">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <h2 className="font-serif text-3xl lg:text-4xl text-white mb-4">
                Ready to Start?
              </h2>
              <p className="text-white/80 text-lg mb-8 leading-relaxed">
                Get a free consultation with our experts. We'll guide you through
                the process and give you a clear timeline and quote.
              </p>

              <div className="flex flex-wrap gap-4">
                <Link
                  href="https://wa.me/6285904369574"
                  target="_blank"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white text-[#e85c41] font-medium hover:bg-white/90 transition-colors"
                >
                  <Phone className="w-4 h-4" />
                  +62 859 0436 9574
                </Link>
                <a
                  href="mailto:info@balizero.com"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border-2 border-white/40 text-white font-medium hover:bg-white/10 transition-colors"
                >
                  <Mail className="w-4 h-4" />
                  info@balizero.com
                </a>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              {CONTACT_INFO.map((info) => (
                <div key={info.label} className="bg-white/10 rounded-xl p-6">
                  <p className="text-white/60 text-sm mb-1">{info.label}</p>
                  <p className="text-white font-medium">{info.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

// Data
const TRUST_BADGES = [
  { icon: Users, value: '500+', label: 'Clients Served' },
  { icon: Clock, value: '10+ Years', label: 'Experience' },
  { icon: Shield, value: '100%', label: 'Compliance Rate' },
  { icon: Check, value: '24/7', label: 'Support' },
];

const SERVICES = [
  {
    name: 'Visa & Immigration',
    slug: 'visa',
    tagline: 'Stay and work legally in Indonesia',
    icon: Plane,
    bgColor: 'bg-rose-500/10',
    iconColor: 'text-rose-400',
    startingPrice: '3.500.000',
    highlights: [
      'KITAS (Work & Investor Permits)',
      'KITAP (Permanent Stay)',
      'Golden Visa Program',
      'Visa Extensions & Renewals',
    ],
  },
  {
    name: 'Company Setup',
    slug: 'company',
    tagline: 'Launch your business in Indonesia',
    icon: Building2,
    bgColor: 'bg-orange-500/10',
    iconColor: 'text-orange-400',
    startingPrice: '15.000.000',
    highlights: [
      'PT PMA (Foreign Company)',
      'PT Local & CV',
      'Business Licenses (NIB, OSS)',
      'Virtual Office Solutions',
    ],
  },
  {
    name: 'Tax & Compliance',
    slug: 'tax',
    tagline: 'Stay compliant, optimize taxes',
    icon: Calculator,
    bgColor: 'bg-amber-500/10',
    iconColor: 'text-amber-400',
    startingPrice: '2.500.000',
    highlights: [
      'Personal Tax (SPT)',
      'Corporate Tax Filing',
      'Tax Planning & Optimization',
      'Annual Compliance Reports',
    ],
  },
  {
    name: 'Property Services',
    slug: 'property',
    tagline: 'Secure your Indonesian property',
    icon: Home,
    bgColor: 'bg-emerald-500/10',
    iconColor: 'text-emerald-400',
    startingPrice: '5.000.000',
    highlights: [
      'Property Due Diligence',
      'Lease Agreements',
      'Land Certificate Checks',
      'Ownership Structures (PT/Nominee)',
    ],
  },
];

const PROCESS_STEPS = [
  {
    title: 'Consultation',
    description: 'Free initial call to understand your needs',
  },
  {
    title: 'Proposal',
    description: 'Clear timeline and transparent pricing',
  },
  {
    title: 'Execution',
    description: 'We handle all paperwork and processes',
  },
  {
    title: 'Delivery',
    description: 'Receive your documents and ongoing support',
  },
];

const CONTACT_INFO = [
  { label: 'Office', value: 'Kerobokan, Bali' },
  { label: 'Hours', value: 'Mon-Fri 9am-6pm' },
  { label: 'Response', value: 'Within 24 hours' },
  { label: 'Languages', value: 'EN, ID, IT' },
];
