'use client';

import * as React from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Users, Phone, Mail, ArrowRight, Sparkles } from 'lucide-react';

/**
 * Team Page - Bali Zero Team
 * McKinsey-inspired layout showcasing our team
 */
export default function TeamPage() {
  return (
    <div className="min-h-screen bg-[#051C2C]">
      {/* Hero Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16 lg:py-24">
          <div className="max-w-3xl">
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
              Our Team
            </span>
            <h1 className="font-serif text-4xl lg:text-5xl xl:text-6xl text-white leading-[1.1] mb-6">
              Meet the{' '}
              <span className="text-[#e85c41]">Experts</span>{' '}
              Behind Your Success
            </h1>
            <p className="text-lg text-white/70 mb-8 leading-relaxed">
              A dedicated team of visa specialists, tax consultants, and business advisors
              committed to making your Indonesian journey seamless.
            </p>

            <div className="flex flex-wrap gap-4">
              <Link
                href="https://wa.me/6285904369574"
                target="_blank"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#2251ff] text-white font-medium hover:bg-[#1a41cc] transition-colors"
              >
                <Phone className="w-4 h-4" />
                Contact Us
              </Link>
              <Link
                href="/services"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-white/20 text-white font-medium hover:bg-white/10 transition-colors"
              >
                View Services
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Leadership Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center mb-12">
            <h2 className="font-serif text-3xl text-white mb-4">Leadership</h2>
            <p className="text-white/60 max-w-2xl mx-auto">
              Guiding our vision and ensuring excellence in every service we provide.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-2xl mx-auto">
            {LEADERSHIP.map((member) => (
              <TeamCard key={member.initials} member={member} size="large" />
            ))}
          </div>
        </div>
      </section>

      {/* Setup Team Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center mb-12">
            <h2 className="font-serif text-3xl text-white mb-4">Setup Team</h2>
            <p className="text-white/60 max-w-2xl mx-auto">
              Company formation, visa processing, and business consulting experts.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {SETUP_TEAM.map((member) => (
              <TeamCard key={member.initials} member={member} />
            ))}
          </div>
        </div>
      </section>

      {/* Tax Department Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center mb-12">
            <h2 className="font-serif text-3xl text-white mb-4">Tax Department</h2>
            <p className="text-white/60 max-w-2xl mx-auto">
              Certified tax professionals ensuring your compliance and optimization.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {TAX_TEAM.map((member) => (
              <TeamCard key={member.initials} member={member} />
            ))}
          </div>
        </div>
      </section>

      {/* Support Team Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center mb-12">
            <h2 className="font-serif text-3xl text-white mb-4">Support & Marketing</h2>
            <p className="text-white/60 max-w-2xl mx-auto">
              Keeping you connected and informed throughout your journey.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {SUPPORT_TEAM.map((member) => (
              <TeamCard key={member.initials} member={member} />
            ))}
          </div>
        </div>
      </section>

      {/* Zero AI Section */}
      <section className="border-b border-white/10 bg-gradient-to-br from-[#0a2540] to-[#051C2C]">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="flex flex-col md:flex-row items-center gap-8 justify-center">
            <div className="relative">
              <div className="w-32 h-32 rounded-full bg-gradient-to-br from-[#2251ff] to-[#e85c41] flex items-center justify-center">
                <Image
                  src="/images/zantara-lotus.png"
                  alt="Zantara AI"
                  width={100}
                  height={100}
                  className="rounded-full"
                />
              </div>
              <div className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-[#2251ff] flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-white" />
              </div>
            </div>
            <div className="text-center md:text-left max-w-xl">
              <h3 className="font-serif text-2xl text-white mb-2">Zantara AI</h3>
              <p className="text-[#2251ff] font-medium mb-4">AI Bridge</p>
              <p className="text-white/60">
                Your 24/7 intelligent assistant. Zantara AI helps you get instant answers
                about visas, company setup, taxes, and more — bridging you to the right
                expert when you need human support.
              </p>
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 mt-6 px-6 py-3 rounded-lg bg-[#2251ff] text-white font-medium hover:bg-[#1a41cc] transition-colors"
              >
                <Sparkles className="w-4 h-4" />
                Ask Zantara AI
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Contact CTA */}
      <section className="bg-gradient-to-br from-[#e85c41] to-[#d14832]">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center max-w-2xl mx-auto">
            <h2 className="font-serif text-3xl lg:text-4xl text-white mb-4">
              Ready to Work With Us?
            </h2>
            <p className="text-white/80 text-lg mb-8">
              Get in touch with our team for a free consultation.
              We're here to help you navigate Indonesia with confidence.
            </p>

            <div className="flex flex-wrap gap-4 justify-center">
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
        </div>
      </section>
    </div>
  );
}

// Team Card Component
interface TeamMember {
  name: string;
  initials: string;
  role: string;
  gradient: string;
  external?: boolean;
  photo?: string; // Optional photo URL
}

function TeamCard({ member, size = 'normal' }: { member: TeamMember; size?: 'normal' | 'large' }) {
  const isLarge = size === 'large';

  return (
    <div className={`group rounded-xl border border-white/10 bg-[#0a2540] ${isLarge ? 'p-8' : 'p-6'} hover:border-[#2251ff]/50 transition-all text-center`}>
      {/* Avatar - Photo or Initials */}
      <div className={`${isLarge ? 'w-24 h-24' : 'w-16 h-16'} rounded-full ${member.gradient} flex items-center justify-center mx-auto mb-4 overflow-hidden`}>
        {member.photo ? (
          <Image
            src={member.photo}
            alt={member.name}
            width={isLarge ? 96 : 64}
            height={isLarge ? 96 : 64}
            className="w-full h-full object-cover"
          />
        ) : (
          <span className={`${isLarge ? 'text-2xl' : 'text-lg'} font-bold text-white`}>
            {member.initials}
          </span>
        )}
      </div>

      {/* Info */}
      <h3 className={`${isLarge ? 'text-xl' : 'text-base'} font-medium text-white mb-1 group-hover:text-[#2251ff] transition-colors`}>
        {member.name}
      </h3>
      <p className={`${isLarge ? 'text-sm' : 'text-xs'} text-white/60`}>
        {member.role}
        {member.external && (
          <span className="ml-2 text-[#2251ff]">(External)</span>
        )}
      </p>
    </div>
  );
}

// Team Data (excluding Amanda and Maria as requested)
const LEADERSHIP: TeamMember[] = [
  {
    name: 'Zainal Abidin',
    initials: 'ZA',
    role: 'Chief Executive Officer',
    gradient: 'bg-gradient-to-br from-[#2251ff] to-[#1a41cc]',
  },
  {
    name: 'Ruslana',
    initials: 'RS',
    role: 'Board Member',
    gradient: 'bg-gradient-to-br from-[#e85c41] to-[#d14832]',
  },
];

const SETUP_TEAM: TeamMember[] = [
  {
    name: 'Anton',
    initials: 'AN',
    role: 'Executive Consultant',
    gradient: 'bg-gradient-to-br from-emerald-500 to-teal-600',
  },
  {
    name: 'Vino',
    initials: 'VI',
    role: 'Junior Consultant',
    gradient: 'bg-gradient-to-br from-violet-500 to-purple-600',
  },
  {
    name: 'Krisna',
    initials: 'KR',
    role: 'Executive Consultant',
    gradient: 'bg-gradient-to-br from-orange-500 to-amber-600',
    photo: '/images/team/krisna.png',
  },
  {
    name: 'Adit',
    initials: 'AD',
    role: 'Supervisor (Lead Setup)',
    gradient: 'bg-gradient-to-br from-cyan-500 to-blue-600',
    photo: '/images/team/adit.png',
  },
  {
    name: 'Ari',
    initials: 'AR',
    role: 'Specialist Consultant',
    gradient: 'bg-gradient-to-br from-rose-500 to-pink-600',
    photo: '/images/team/ari.png',
  },
  {
    name: 'Dea',
    initials: 'DE',
    role: 'Executive Consultant',
    gradient: 'bg-gradient-to-br from-indigo-500 to-blue-600',
    photo: '/images/team/dea.png',
  },
  {
    name: 'Surya',
    initials: 'SU',
    role: 'Specialist Consultant',
    gradient: 'bg-gradient-to-br from-amber-500 to-orange-600',
  },
  {
    name: 'Damar',
    initials: 'DM',
    role: 'Junior Consultant',
    gradient: 'bg-gradient-to-br from-teal-500 to-emerald-600',
  },
  {
    name: 'Marta',
    initials: 'MA',
    role: 'External Advisory',
    gradient: 'bg-gradient-to-br from-fuchsia-500 to-pink-600',
    external: true,
  },
];

const TAX_TEAM: TeamMember[] = [
  {
    name: 'Veronika',
    initials: 'VE',
    role: 'Tax Manager',
    gradient: 'bg-gradient-to-br from-[#2251ff] to-[#1a41cc]',
  },
  {
    name: 'Angel',
    initials: 'AG',
    role: 'Tax Expert',
    gradient: 'bg-gradient-to-br from-rose-500 to-red-600',
  },
  {
    name: 'Kadek',
    initials: 'KD',
    role: 'Tax Consultant',
    gradient: 'bg-gradient-to-br from-emerald-500 to-green-600',
  },
  {
    name: 'Dewa Ayu',
    initials: 'DA',
    role: 'Tax Consultant',
    gradient: 'bg-gradient-to-br from-violet-500 to-indigo-600',
  },
  {
    name: 'Faisha',
    initials: 'FA',
    role: 'Tax Care',
    gradient: 'bg-gradient-to-br from-amber-500 to-yellow-600',
  },
  {
    name: 'Olena',
    initials: 'OL',
    role: 'External Advisory',
    gradient: 'bg-gradient-to-br from-cyan-500 to-teal-600',
    external: true,
  },
];

const SUPPORT_TEAM: TeamMember[] = [
  {
    name: 'Rina',
    initials: 'RI',
    role: 'Reception',
    gradient: 'bg-gradient-to-br from-pink-500 to-rose-600',
  },
  {
    name: 'Nina',
    initials: 'NI',
    role: 'Marketing Advisory',
    gradient: 'bg-gradient-to-br from-orange-500 to-red-600',
    external: true,
  },
  {
    name: 'Sahira',
    initials: 'SH',
    role: 'Marketing Specialist',
    gradient: 'bg-gradient-to-br from-purple-500 to-violet-600',
  },
];
