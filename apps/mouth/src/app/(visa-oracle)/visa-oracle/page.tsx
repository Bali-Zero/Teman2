"use client";

import Link from "next/link";
import { FunnelFrame, getOrCreateSessionId } from "@balizero/core";
import {
  TrustBadges,
  TestimonialCarousel,
  ExitIntent,
  StickyCta,
  type Testimonial,
} from "@/components/funnel";

const TRUST_STATS = [
  { value: "5,000+", label: "Clients served", hint: "since 2020" },
  { value: "68,000+", label: "Legal documents", hint: "indexed by AI" },
  { value: "3 free", label: "Questions", hint: "no account required" },
  { value: "4.9/5", label: "Average rating", hint: "Google Reviews" },
];

const TESTIMONIALS: Testimonial[] = [
  {
    quote:
      "Visa Oracle matched me with the right KITAS in two minutes. I booked a WhatsApp call and we filed the same week.",
    author: "Sofia M.",
    role: "Digital nomad",
    location: "Canggu",
    rating: 5,
  },
  {
    quote:
      "I was stuck between three visa types. The follow-up chat referenced the exact regulations I needed to convince my employer.",
    author: "Daniel K.",
    role: "Engineering Manager",
    location: "Ubud",
    rating: 5,
  },
  {
    quote:
      "Clear answers, no upsell. When I was ready, the Bali Zero team picked it up straight from the quiz.",
    author: "Priya R.",
    role: "Founder",
    location: "Seminyak",
    rating: 5,
  },
];

const HOW_IT_WORKS = [
  {
    step: 1,
    title: "Take the quiz",
    description:
      "Answer a few simple questions about your nationality, purpose of stay, and how long you plan to be in Indonesia.",
  },
  {
    step: 2,
    title: "Get personalized recommendations",
    description:
      "Our AI matches your profile against all available visa types and ranks them by fit, cost, and complexity.",
  },
  {
    step: 3,
    title: "Ask follow-up questions",
    description:
      "Not sure about requirements? Ask anything about your recommended visa — extensions, sponsorship, documents needed.",
  },
  {
    step: 4,
    title: "Talk to our team on WhatsApp",
    description:
      "Ready to apply? Connect directly with our Bali Zero immigration specialists for fast, hands-on assistance.",
  },
];

export default function VisaOracleLandingPage() {
  return (
    <FunnelFrame
      funnel="visa"
      sessionId={getOrCreateSessionId()}
      trust={{ clientCount: 5000, rating: 4.9, responseMinutes: 15 }}
    >
      <div className="flex flex-col gap-16">
        {/* Hero */}
        <section className="flex flex-col items-center text-center gap-6 pt-8">
          <h1 className="text-4xl sm:text-5xl font-bold leading-tight tracking-tight max-w-3xl">
            What visa do you need for{" "}
            <span style={{ color: "var(--bz-accent)" }}>Indonesia?</span>
          </h1>
          <p
            className="text-lg sm:text-xl max-w-2xl leading-relaxed"
            style={{ color: "var(--tx-secondary)" }}
          >
            Get instant, AI-powered visa guidance built on 68,000+ Indonesian
            legal documents.
          </p>

          {/* Dual CTA */}
          <div className="flex flex-col sm:flex-row items-center gap-4 mt-2">
            <Link
              href="/visa-oracle/quiz"
              className="inline-flex items-center justify-center px-8 py-3 rounded-lg font-semibold text-base transition-opacity hover:opacity-90 active:opacity-80"
              style={{
                backgroundColor: "var(--bz-accent)",
                color: "#fff",
              }}
            >
              Start Quiz
            </Link>
            <Link
              href="/visa-oracle/chat"
              className="inline-flex items-center justify-center px-8 py-3 rounded-lg font-semibold text-base transition-opacity hover:opacity-80 active:opacity-70 border"
              style={{
                borderColor: "var(--bz-accent)",
                color: "var(--bz-accent)",
              }}
            >
              I already know what I need
            </Link>
          </div>
        </section>

        {/* Trust signals */}
        <TrustBadges stats={TRUST_STATS} />

        {/* Social proof */}
        <TestimonialCarousel testimonials={TESTIMONIALS} />


        {/* How it works */}
        <section className="flex flex-col gap-8">
          <h2 className="text-2xl font-bold text-center">How it works</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {HOW_IT_WORKS.map((item) => (
              <div
                key={item.step}
                className="flex gap-4 p-6 rounded-xl"
                style={{ backgroundColor: "var(--bz-elevated)" }}
              >
                <div
                  className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                  style={{
                    backgroundColor: "var(--bz-accent)",
                    color: "#fff",
                  }}
                >
                  {item.step}
                </div>
                <div className="flex flex-col gap-1">
                  <h3 className="font-semibold">{item.title}</h3>
                  <p
                    className="text-sm leading-relaxed"
                    style={{ color: "var(--tx-secondary)" }}
                  >
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Bottom CTA */}
        <section className="flex flex-col items-center text-center gap-4 pb-8">
          <p className="text-base" style={{ color: "var(--tx-secondary)" }}>
            Free to try. No account required.
          </p>
          <Link
            href="/visa-oracle/quiz"
            className="inline-flex items-center justify-center px-10 py-3 rounded-lg font-semibold text-base transition-opacity hover:opacity-90 active:opacity-80"
            style={{
              backgroundColor: "var(--bz-accent)",
              color: "#fff",
            }}
          >
            Find my visa
          </Link>
        </section>
      </div>

      <StickyCta label="Start the visa quiz" href="/visa-oracle/quiz" />
      <ExitIntent
        storageKey="bz:exit-intent:visa-oracle"
        title="Before you go — 60 seconds to your visa."
        description="Take the free quiz and get a personalized recommendation. No account, no spam."
        ctaLabel="Start the quiz"
        ctaHref="/visa-oracle/quiz"
      />
    </FunnelFrame>
  );
}
