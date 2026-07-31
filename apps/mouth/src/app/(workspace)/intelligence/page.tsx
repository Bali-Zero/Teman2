"use client";

import React from "react";
import Link from "next/link";
import { Newspaper, PenTool, ArrowRight, Shield, Zap } from "lucide-react";

const TRINITY = [
  {
    name: "Visa Oracle",
    href: "/intelligence/visa-oracle",
    icon: Shield,
    description:
      "Review visa & immigration regulation changes detected on imigrasi.go.id and approve updates.",
    // Documented one-off (WS2 slice 3): sky identity — no operative token
    // covers the sky hue; pinned by the intelligence drain-guard test.
    overlayGradient:
      "linear-gradient(to bottom right, rgba(14,165,233,0.2), rgba(14,165,233,0.1) 50%, transparent)", // token-lint-ok: sky one-off, no token covers the hue
    glow: "rgba(14,165,233,0.15)", // token-lint-ok: sky one-off, no token covers the hue
    iconColor: "#38bdf8", // token-lint-ok: sky-400 one-off accent, no token covers the hue
    borderColor: "rgba(14,165,233,0.15)", // token-lint-ok: sky one-off, no token covers the hue
    step: "01",
  },
  {
    name: "News Room",
    href: "/intelligence/news-room",
    icon: Newspaper,
    description:
      "Curate AI-scraped Bali news & visa intel. Edit, add cover images, and publish to the live site.",
    overlayGradient:
      "linear-gradient(to bottom right, color-mix(in srgb, var(--state-success) 20%, transparent), color-mix(in srgb, var(--state-success) 10%, transparent) 50%, transparent)",
    glow: "color-mix(in srgb, var(--state-success) 15%, transparent)",
    iconColor: "var(--state-success)",
    borderColor: "color-mix(in srgb, var(--state-success) 15%, transparent)",
    step: "02",
  },
  {
    name: "Article Composer",
    href: "/intelligence/article-composer",
    icon: PenTool,
    description:
      "Transform raw content into polished Bali Zero Executive Briefs with AI-powered enrichment.",
    overlayGradient:
      "linear-gradient(to bottom right, color-mix(in srgb, var(--bz-neon-purple) 20%, transparent), color-mix(in srgb, var(--bz-neon-purple) 10%, transparent) 50%, transparent)",
    glow: "color-mix(in srgb, var(--bz-neon-purple) 15%, transparent)",
    iconColor: "var(--bz-neon-purple)",
    borderColor: "color-mix(in srgb, var(--bz-neon-purple) 15%, transparent)",
    step: "03",
    badge: "AI",
  },
];

export default function IntelligencePage() {
  return (
    <div className="animate-in fade-in duration-500 space-y-10">
      {/* Hero Headline */}
      <div className="text-center pt-6 pb-2">
        <div
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full mb-4 text-[11px] font-medium"
          style={{
            background: "var(--bz-accent-subtle)",
            border:
              "1px solid color-mix(in srgb, var(--bz-accent) 20%, transparent)",
            color: "var(--bz-accent)",
          }}
        >
          <Zap size={10} />
          AI-Powered Editorial Suite
        </div>
        <h1
          className="text-[40px] font-bold tracking-tight leading-none mb-3"
          style={{
            background:
              "linear-gradient(135deg, var(--bz-text-1) 0%, var(--bz-accent) 60%, color-mix(in srgb, var(--bz-accent) 55%, var(--bz-text-pure)) 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
          }}
        >
          Intelligence Center
        </h1>
        <p
          className="text-[15px] max-w-xl mx-auto leading-relaxed"
          style={{ color: "var(--bz-text-2)" }}
        >
          Monitor Indonesian immigration regulations, curate breaking news, and
          craft expert content — all in one pipeline.
        </p>
      </div>

      {/* Trinity Cards Row
          Layout: cards are flex-1 siblings, arrows are flex-shrink-0 siblings.
          Do NOT nest the arrow inside the card wrapper — that would steal width from the card.
      */}
      <div className="flex items-stretch gap-0">
        {TRINITY.map((tool, index) => {
          const Icon = tool.icon;
          const isLast = index === TRINITY.length - 1;

          return (
            <React.Fragment key={tool.href}>
              {/* Card — flex-1 so all three cards share equal width */}
              <Link
                href={tool.href}
                className={`
                  group relative flex flex-col flex-1 min-h-[260px] p-6 rounded-2xl overflow-hidden
                  transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl
                `}
                style={{
                  background: `linear-gradient(145deg, ${tool.glow} 0%, rgba(255,255,255,0.02) 100%)`,
                  border: `1px solid ${tool.borderColor}`,
                  backdropFilter: "blur(24px)",
                  WebkitBackdropFilter: "blur(24px)",
                }}
              >
                {/* Subtle gradient overlay */}
                <div
                  className="absolute inset-0 opacity-60 pointer-events-none"
                  style={{ background: tool.overlayGradient }}
                />

                {/* Step number */}
                <div
                  className="absolute top-4 right-4 text-[11px] font-bold font-mono opacity-30"
                  style={{ color: tool.iconColor }}
                >
                  {tool.step}
                </div>

                {/* Badge */}
                {tool.badge && (
                  <div
                    className="absolute top-4 left-[4.5rem] px-1.5 py-0.5 rounded text-[9px] font-bold tracking-wide"
                    style={{
                      background: "rgba(212,132,90,0.2)",
                      color: "var(--bz-accent)",
                      border: "1px solid rgba(212,132,90,0.3)",
                    }}
                  >
                    {tool.badge}
                  </div>
                )}

                {/* Icon */}
                <div
                  className="relative w-10 h-10 rounded-xl flex items-center justify-center mb-4 flex-shrink-0"
                  style={{
                    background: `${tool.glow}`,
                    border: `1px solid ${tool.borderColor}`,
                  }}
                >
                  <Icon size={20} style={{ color: tool.iconColor }} />
                </div>

                {/* Content */}
                <div className="relative flex-1 flex flex-col">
                  <h3
                    className="text-[17px] font-bold mb-2 transition-colors"
                    style={{ color: "var(--bz-text-1)" }}
                  >
                    {tool.name}
                  </h3>
                  <p
                    className="text-[13px] leading-relaxed flex-1"
                    style={{ color: "var(--bz-text-2)" }}
                  >
                    {tool.description}
                  </p>

                  {/* Open CTA — visible on hover */}
                  <div
                    className="mt-4 flex items-center gap-1 text-[12px] font-medium opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                    style={{ color: tool.iconColor }}
                  >
                    Open tool
                    <ArrowRight
                      size={12}
                      className="group-hover:translate-x-1 transition-transform"
                    />
                  </div>
                </div>
              </Link>

              {/* Workflow Connector Arrow — OUTSIDE the card, flex-shrink-0 sibling */}
              {!isLast && (
                <div
                  className="flex-shrink-0 w-10 flex items-center justify-center self-center"
                  style={{ color: "var(--bz-text-3)" }}
                >
                  <ArrowRight size={16} className="opacity-40" />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Status Strip */}
      <div
        className="flex items-center justify-between px-5 py-3 rounded-xl"
        style={{
          background: "var(--surface-raised)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-[6px] h-[6px] rounded-full animate-pulse"
            style={{
              background: "var(--bz-green)",
              boxShadow: "0 0 5px rgba(77,184,122,0.5)",
            }}
          />
          <span className="text-[11.5px]" style={{ color: "var(--bz-text-2)" }}>
            Intelligence pipeline active
          </span>
        </div>
        <span className="text-[11px]" style={{ color: "var(--bz-text-3)" }}>
          Bali Zero Intelligence Center
        </span>
      </div>
    </div>
  );
}
