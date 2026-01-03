'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { motion } from 'framer-motion';
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
  ChevronRight,
  Star,
  Quote
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
            {/* BALI ZERO Logo */}
            <div className="mb-8">
              <Image
                src="/images/balizero-logo.png"
                alt="Bali Zero"
                width={80}
                height={80}
                className="rounded-full"
              />
            </div>
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
                <Image src="/images/zantara-lotus.png" alt="" width={60} height={60} />
                Ask Zantara AI
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Google Reviews Section */}
      <section className="border-b border-white/10 overflow-hidden">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-12">
          {/* Google Rating Header - Linked to Google Maps */}
          <a
            href="https://maps.app.goo.gl/SHEuJpR1ghDgdmA28"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-4 mb-8 hover:opacity-80 transition-opacity"
          >
            <svg className="w-10 h-10" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <div className="flex items-center gap-1">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="w-6 h-6 fill-yellow-400 text-yellow-400" />
              ))}
            </div>
            <span className="text-4xl font-bold text-white">5.0</span>
            <div className="flex flex-col">
              <span className="text-white/80 text-sm font-medium">700+ reviews</span>
              <span className="text-white/50 text-xs">on Google Maps</span>
            </div>
          </a>

          {/* Scrolling Reviews with Framer Motion */}
          <div className="relative overflow-hidden">
            <motion.div
              className="flex gap-6"
              animate={{ x: [0, -2840] }}
              transition={{
                x: {
                  repeat: Infinity,
                  repeatType: "loop",
                  duration: 40,
                  ease: "linear",
                },
              }}
            >
              {[...GOOGLE_REVIEWS, ...GOOGLE_REVIEWS].map((review, index) => {
                // Alternating colors: yellow, green, red, blue
                const colors = [
                  { border: '2px solid rgba(234, 179, 8, 0.5)', accent: 'bg-yellow-500/20', text: 'text-yellow-400' },
                  { border: '2px solid rgba(34, 197, 94, 0.5)', accent: 'bg-green-500/20', text: 'text-green-400' },
                  { border: '2px solid rgba(239, 68, 68, 0.5)', accent: 'bg-red-500/20', text: 'text-red-400' },
                  { border: '2px solid rgba(59, 130, 246, 0.5)', accent: 'bg-blue-500/20', text: 'text-blue-400' },
                ];
                const colorIndex = index % 4;
                const color = colors[colorIndex];

                return (
                  <div
                    key={`${review.name}-${index}`}
                    className="flex-shrink-0 w-[350px] p-6 rounded-xl bg-[#0a2540]"
                    style={{ border: color.border }}
                  >
                    <div className="flex items-center gap-1 mb-3">
                      {[...Array(5)].map((_, i) => (
                        <Star key={i} className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                      ))}
                    </div>
                    <p className="text-white/80 text-sm mb-4 line-clamp-3 italic">
                      &ldquo;{review.text}&rdquo;
                    </p>
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full ${color.accent} flex items-center justify-center ${color.text} font-medium text-sm`}>
                        {review.name.charAt(0)}
                      </div>
                      <div>
                        <p className="text-white text-sm font-medium">{review.name}</p>
                        <p className="text-white/40 text-xs">{review.date}</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </motion.div>
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
                      {service.startingPrice === 'Contact' ? (
                        <span className="text-[#2251ff]">Contact for quote</span>
                      ) : (
                        <>
                          {service.startingPrice}
                          <span className="text-white/40 text-sm font-normal ml-2">IDR</span>
                        </>
                      )}
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

      {/* Team Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center mb-12">
            <h2 className="font-serif text-3xl text-white mb-4">Meet Our Team</h2>
            <p className="text-white/60 max-w-2xl mx-auto">
              A dedicated team of visa specialists, tax consultants, and business advisors.
            </p>
          </div>

          {/* Team Grid */}
          <div className="grid grid-cols-3 md:grid-cols-6 lg:grid-cols-8 gap-4 mb-8">
            {TEAM_MEMBERS.map((member) => (
              <div key={member.initials} className="text-center group">
                {member.image ? (
                  <div className="w-14 h-14 md:w-16 md:h-16 rounded-full mx-auto mb-2 group-hover:scale-110 transition-transform overflow-hidden">
                    <Image
                      src={member.image}
                      alt={member.name}
                      width={64}
                      height={64}
                      className="w-full h-full object-cover"
                    />
                  </div>
                ) : (
                  <div className={`w-14 h-14 md:w-16 md:h-16 rounded-full ${member.gradient} flex items-center justify-center mx-auto mb-2 group-hover:scale-110 transition-transform`}>
                    <span className="text-sm md:text-base font-bold text-white">
                      {member.initials}
                    </span>
                  </div>
                )}
                <p className="text-white text-xs font-medium truncate">{member.name}</p>
                <p className="text-white/40 text-[10px] truncate">{member.role}</p>
              </div>
            ))}
          </div>

          {/* Zantara AI */}
          <div className="flex items-center justify-center gap-4 p-6 rounded-xl bg-gradient-to-r from-[#2251ff]/20 to-[#e85c41]/20 border border-white/10">
            <Image
              src="/images/zantara-lotus.png"
              alt="Zantara AI"
              width={60}
              height={60}
              className="rounded-full"
            />
            <div>
              <p className="text-white font-medium">Zantara AI</p>
              <p className="text-white/60 text-sm">Your 24/7 intelligent assistant</p>
            </div>
            <Link
              href="/chat"
              className="ml-auto px-4 py-2 rounded-lg bg-[#2251ff] text-white text-sm font-medium hover:bg-[#1a41cc] transition-colors"
            >
              Ask Now
            </Link>
          </div>

          {/* View Full Team Link */}
          <div className="text-center mt-8">
            <Link
              href="/team"
              className="inline-flex items-center gap-2 text-[#2251ff] hover:text-[#1a41cc] font-medium transition-colors"
            >
              View full team
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* Contact CTA */}
      <section className="bg-gradient-to-br from-[#e85c41] to-[#d14832]">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              {/* BALI ZERO Logo */}
              <div className="mb-6">
                <Image
                  src="/images/balizero-logo.png"
                  alt="Bali Zero"
                  width={64}
                  height={64}
                  className="rounded-full border-2 border-white/30"
                />
              </div>
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
const GOOGLE_REVIEWS = [
  {
    name: 'Marco R.',
    text: 'Incredible service! They handled my PT PMA setup flawlessly. Everything was done in 3 weeks, exactly as promised. Highly recommended for anyone starting a business in Bali.',
    date: '2 weeks ago',
  },
  {
    name: 'Sarah K.',
    text: 'Zantara made my KITAS application so easy. They explained every step clearly and were always available on WhatsApp. Got my visa approved without any issues!',
    date: '1 month ago',
  },
  {
    name: 'David M.',
    text: 'Best immigration consultants in Bali. Professional, transparent pricing, and they actually know what they\'re doing. Saved me from so much stress.',
    date: '3 weeks ago',
  },
  {
    name: 'Anna L.',
    text: 'They helped us buy property in Ubud as foreigners. Explained all the legal structures clearly. Very trustworthy team, we felt safe throughout the process.',
    date: '1 month ago',
  },
  {
    name: 'Thomas B.',
    text: 'Fast and efficient! My investor KITAS was done in record time. The team is super responsive and knows Indonesian bureaucracy inside out.',
    date: '2 months ago',
  },
  {
    name: 'Julia W.',
    text: 'Finally a company that doesn\'t overcharge. Fair prices, excellent service. They even helped me set up my tax registration. 5 stars!',
    date: '1 month ago',
  },
  {
    name: 'Michael C.',
    text: 'I\'ve used many agents in Bali over 10 years. Bali Zero is by far the most professional. They handle everything from visas to company compliance.',
    date: '3 weeks ago',
  },
  {
    name: 'Emma S.',
    text: 'The AI assistant Zantara answered all my questions instantly, then the human team took over for the actual process. Perfect combination of tech and personal service.',
    date: '2 weeks ago',
  },
];

const SERVICES = [
  {
    name: 'Visa & Immigration',
    slug: 'visa',
    tagline: 'Complete visa solutions for living and working in Indonesia',
    icon: Plane,
    bgColor: 'bg-rose-500/10',
    iconColor: 'text-rose-400',
    startingPrice: '2.300.000',
    highlights: [
      'Visit Visas (C1, C2 Business)',
      'KITAS (Working, Freelance, Investor)',
      'KITAP (Permanent Residence)',
      'Multiple Entry Visas (D Series)',
    ],
  },
  {
    name: 'Company Setup & Licenses',
    slug: 'company',
    tagline: 'From licenses to structure — launch your business fast',
    icon: Building2,
    bgColor: 'bg-orange-500/10',
    iconColor: 'text-orange-400',
    startingPrice: '7.000.000',
    highlights: [
      'PT PMA/PMDN (Foreign Company)',
      'SLHS (Hygiene Certificate)',
      'Alcohol License (NPBBKC)',
      'Company Revision & Changes',
    ],
  },
  {
    name: 'Tax Consulting',
    slug: 'tax',
    tagline: 'Navigate Indonesia\'s tax system with confidence',
    icon: Calculator,
    bgColor: 'bg-amber-500/10',
    iconColor: 'text-amber-400',
    startingPrice: 'Contact',
    highlights: [
      'Tax Registration (NPWP)',
      'Tax Filing & Reporting (SPT)',
      'Corporate Tax Planning',
      'Personal Income Tax',
    ],
  },
  {
    name: 'Real Estate Services',
    slug: 'property',
    tagline: 'Secure property with legal clarity and guidance',
    icon: Home,
    bgColor: 'bg-emerald-500/10',
    iconColor: 'text-emerald-400',
    startingPrice: 'Contact',
    highlights: [
      'Legal Due Diligence',
      'Leasehold Agreements (Hak Sewa)',
      'IMB & Building Permits',
      'Ownership Structures (PT PMA)',
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

const TEAM_MEMBERS = [
  { name: 'Zero', initials: 'ZE', role: 'CEO', gradient: 'bg-gradient-to-br from-[#2251ff] to-[#1a41cc]', image: '/images/team/zero.jpg' },
  { name: 'Ruslana', initials: 'RS', role: 'Board', gradient: 'bg-gradient-to-br from-[#e85c41] to-[#d14832]' },
  { name: 'Anton', initials: 'AN', role: 'Consultant', gradient: 'bg-gradient-to-br from-emerald-500 to-teal-600' },
  { name: 'Vino', initials: 'VI', role: 'Consultant', gradient: 'bg-gradient-to-br from-violet-500 to-purple-600' },
  { name: 'Krisna', initials: 'KR', role: 'Consultant', gradient: 'bg-gradient-to-br from-orange-500 to-amber-600' },
  { name: 'Adit', initials: 'AD', role: 'Crew Lead', gradient: 'bg-gradient-to-br from-cyan-500 to-blue-600' },
  { name: 'Ari', initials: 'AR', role: 'Specialist', gradient: 'bg-gradient-to-br from-rose-500 to-pink-600' },
  { name: 'Dea', initials: 'DE', role: 'Consultant', gradient: 'bg-gradient-to-br from-indigo-500 to-blue-600' },
  { name: 'Surya', initials: 'SU', role: 'Specialist', gradient: 'bg-gradient-to-br from-amber-500 to-orange-600' },
  { name: 'Damar', initials: 'DM', role: 'Consultant', gradient: 'bg-gradient-to-br from-teal-500 to-emerald-600' },
  { name: 'Veronika', initials: 'VE', role: 'Tax Manager', gradient: 'bg-gradient-to-br from-[#2251ff] to-[#1a41cc]' },
  { name: 'Angel', initials: 'AG', role: 'Tax Expert', gradient: 'bg-gradient-to-br from-rose-500 to-red-600' },
  { name: 'Kadek', initials: 'KD', role: 'Tax', gradient: 'bg-gradient-to-br from-emerald-500 to-green-600' },
  { name: 'Dewa Ayu', initials: 'DA', role: 'Tax', gradient: 'bg-gradient-to-br from-violet-500 to-indigo-600' },
  { name: 'Rina', initials: 'RI', role: 'Reception', gradient: 'bg-gradient-to-br from-pink-500 to-rose-600' },
  { name: 'Sahira', initials: 'SH', role: 'Marketing', gradient: 'bg-gradient-to-br from-purple-500 to-violet-600' },
];
