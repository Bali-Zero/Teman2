'use client';

import React from 'react';
import Link from 'next/link';
import {
  Plane,
  Building2,
  Calculator,
  Home,
  Users,
  MessageCircle,
  Mail,
  Phone,
  Instagram,
  MapPin,
  ArrowRight,
  Sparkles
} from 'lucide-react';
import { Button } from '@/components/ui/button';

// Service card data
const services = [
  {
    id: 'visas',
    title: 'Visas & Immigration',
    description: 'Stay and work in Bali with the right permits. We handle all paperwork and government processes.',
    icon: Plane,
    href: '/knowledge/kitas',
    accentColor: 'from-rose-500/20 to-rose-600/10',
    borderColor: 'border-l-rose-500',
    iconColor: 'text-rose-400',
  },
  {
    id: 'company',
    title: 'Company Setup',
    description: 'From licenses to structure — launch your business fast. PT PMA, CV, or representative office.',
    icon: Building2,
    href: '/knowledge',
    accentColor: 'from-orange-500/20 to-orange-600/10',
    borderColor: 'border-l-orange-500',
    iconColor: 'text-orange-400',
  },
  {
    id: 'tax',
    title: 'Tax Consulting',
    description: "Navigate Indonesia's tax system with confidence. Compliance, optimization, and peace of mind.",
    icon: Calculator,
    href: '/knowledge',
    accentColor: 'from-amber-500/20 to-amber-600/10',
    borderColor: 'border-l-amber-500',
    iconColor: 'text-amber-400',
  },
  {
    id: 'realestate',
    title: 'Real Estate',
    description: 'Secure property with legal clarity and guidance. Villa rentals, leases, and ownership structures.',
    icon: Home,
    href: '/knowledge',
    accentColor: 'from-emerald-500/20 to-emerald-600/10',
    borderColor: 'border-l-emerald-500',
    iconColor: 'text-emerald-400',
  },
];

// Contact info
const contactInfo = [
  {
    label: 'Office',
    value: 'Kerobokan, Bali\nIndonesia',
    icon: MapPin,
  },
  {
    label: 'Email',
    value: 'info@balizero.com',
    icon: Mail,
    href: 'mailto:info@balizero.com',
  },
  {
    label: 'WhatsApp',
    value: '+62 859 0436 9574',
    icon: Phone,
    href: 'https://wa.me/6285904369574',
  },
  {
    label: 'Instagram',
    value: '@balizero0',
    icon: Instagram,
    href: 'https://instagram.com/balizero0',
  },
];

export default function ServicesPage() {
  return (
    <div className="space-y-12 pb-12">
      {/* Hero Section */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[var(--background-elevated)] via-[var(--background-secondary)] to-[var(--background)] border border-[var(--border)] p-8 md:p-12">
        {/* Background decoration */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-[var(--accent)]/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-purple-500/5 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />

        <div className="relative z-10 max-w-3xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[var(--accent)]/10 border border-[var(--accent)]/20 mb-6">
            <Sparkles className="w-4 h-4 text-[var(--accent)]" />
            <span className="text-sm font-medium text-[var(--accent)]">From Zero to Infinity</span>
          </div>

          <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-[var(--foreground)] mb-4">
            Build Your{' '}
            <span className="text-gradient">Indonesian Dream</span>
            {' '}with Confidence
          </h1>

          <p className="text-lg text-[var(--foreground-muted)] max-w-2xl mx-auto mb-8">
            We simplify your journey in Bali: visas, business setup, taxes, and real estate — all under one roof.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button asChild size="lg" className="gap-2">
              <Link href="/chat">
                <MessageCircle className="w-5 h-5" />
                Ask Zantara AI
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="gap-2">
              <Link href="/knowledge">
                Explore Knowledge Base
                <ArrowRight className="w-4 h-4" />
              </Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Services Section */}
      <section>
        <div className="text-center mb-8">
          <h2 className="text-2xl md:text-3xl font-bold text-[var(--foreground)] mb-2">
            Our Services
          </h2>
          <p className="text-[var(--foreground-muted)]">
            Comprehensive solutions for expats and businesses in Indonesia
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {services.map((service) => (
            <Link
              key={service.id}
              href={service.href}
              className={`group relative overflow-hidden rounded-xl border border-[var(--border)] border-l-4 ${service.borderColor} bg-[var(--background-secondary)] p-6 transition-all hover:bg-[var(--background-elevated)] hover:shadow-lg hover:shadow-[var(--accent)]/5 hover:-translate-y-1`}
            >
              {/* Background gradient on hover */}
              <div className={`absolute inset-0 bg-gradient-to-br ${service.accentColor} opacity-0 group-hover:opacity-100 transition-opacity`} />

              <div className="relative z-10">
                <div className={`w-14 h-14 rounded-xl bg-[var(--background-elevated)] flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  <service.icon className={`w-7 h-7 ${service.iconColor}`} />
                </div>

                <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">
                  {service.title}
                </h3>

                <p className="text-sm text-[var(--foreground-muted)] leading-relaxed">
                  {service.description}
                </p>

                <div className="mt-4 flex items-center gap-2 text-sm font-medium text-[var(--accent)] opacity-0 group-hover:opacity-100 transition-opacity">
                  Learn more
                  <ArrowRight className="w-4 h-4" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Team CTA Section */}
      <section className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-[var(--accent)]/10 via-purple-500/10 to-[var(--accent)]/10 border border-[var(--accent)]/20 p-8 md:p-12">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-5" />

        <div className="relative z-10 text-center max-w-2xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-[var(--foreground)] mb-4">
            Work with Experts
          </h2>
          <p className="text-[var(--foreground-muted)] mb-8">
            Our team combines local knowledge with international experience.
            Get personalized guidance for your Indonesian journey.
          </p>
          <Button asChild size="lg" className="gap-2">
            <Link href="/team">
              <Users className="w-5 h-5" />
              Meet Our Team
            </Link>
          </Button>
        </div>
      </section>

      {/* Contact Section */}
      <section>
        <div className="text-center mb-8">
          <h2 className="text-2xl md:text-3xl font-bold text-[var(--foreground)] mb-2">
            Get in Touch
          </h2>
          <p className="text-[var(--foreground-muted)]">
            Ready to start? Contact us today
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {contactInfo.map((info) => (
            <div
              key={info.label}
              className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6 text-center hover:bg-[var(--background-elevated)] transition-colors"
            >
              <div className="w-12 h-12 rounded-full bg-[var(--accent)]/10 flex items-center justify-center mx-auto mb-4">
                <info.icon className="w-5 h-5 text-[var(--accent)]" />
              </div>
              <h3 className="text-sm font-medium text-[var(--foreground-muted)] mb-2">
                {info.label}
              </h3>
              {info.href ? (
                <a
                  href={info.href}
                  target={info.href.startsWith('http') ? '_blank' : undefined}
                  rel={info.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                  className="text-[var(--foreground)] hover:text-[var(--accent)] transition-colors whitespace-pre-line"
                >
                  {info.value}
                </a>
              ) : (
                <p className="text-[var(--foreground)] whitespace-pre-line">
                  {info.value}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* AI Assistant CTA */}
      <section className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <div className="flex items-center justify-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[var(--accent)] to-purple-500 flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <h3 className="text-lg font-semibold text-[var(--foreground)]">
            Need Quick Answers?
          </h3>
        </div>
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto mb-6">
          Ask Zantara AI about visas, company setup, taxes, or any Indonesia-related questions.
          Powered by our comprehensive knowledge base.
        </p>
        <Button asChild variant="outline" className="gap-2">
          <Link href="/chat">
            <MessageCircle className="w-4 h-4" />
            Start a Conversation
          </Link>
        </Button>
      </section>
    </div>
  );
}
