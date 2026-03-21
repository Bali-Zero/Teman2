"use client";

import React from "react";
import Image from "next/image";
import { ExternalLink, Sparkles } from "lucide-react";

const ZANTARA_URL = "https://zantara.balizero.com";

export function ZantaraPortalCard() {
  return (
    <a
      href={ZANTARA_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="group relative block overflow-hidden rounded-2xl transition-all duration-500"
      style={{
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.08)",
        boxShadow:
          "0 8px 32px rgba(0,0,0,0.28), 0 2px 8px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.06)",
      }}
    >
      {/* Animated liquid background gradient */}
      <div
        className="absolute inset-0 opacity-40 transition-opacity duration-700 group-hover:opacity-60"
        style={{
          background:
            "radial-gradient(ellipse 80% 60% at 20% 30%, rgba(212,132,90,0.12) 0%, transparent 60%), radial-gradient(ellipse 60% 80% at 80% 70%, rgba(139,92,246,0.08) 0%, transparent 60%)",
          animation: "liquidShift 8s ease-in-out infinite alternate",
        }}
      />

      {/* Satin sheen on hover */}
      <div
        className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
        style={{
          background:
            "linear-gradient(135deg, rgba(255,255,255,0.06) 0%, transparent 50%, rgba(255,255,255,0.02) 100%)",
        }}
      />

      {/* Content */}
      <div className="relative flex items-center gap-4 px-5 py-4">
        {/* Logos cluster */}
        <div className="relative flex-shrink-0 w-[52px] h-[52px]">
          {/* BZ logo — background */}
          <div
            className="absolute inset-0 rounded-xl overflow-hidden"
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            <Image
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              fill
              className="object-contain p-2 opacity-70"
              sizes="52px"
            />
          </div>
          {/* Lotus — overlaid bottom-right with glow pulse */}
          <div
            className="absolute -bottom-1.5 -right-1.5 w-[26px] h-[26px] rounded-full flex items-center justify-center"
            style={{
              background: "rgba(12,12,14,0.85)",
              border: "1px solid rgba(59,130,246,0.25)",
              boxShadow: "0 0 0 0 rgba(59,130,246,0.5)",
              animation: "lotusPulse 3s ease-in-out infinite",
            }}
          >
            <Image
              src="/static/zantara-lotus-v2.png"
              alt="Zantara"
              width={22}
              height={22}
              className="object-contain"
            />
          </div>
        </div>

        {/* Text */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span
              className="text-[13px] font-semibold tracking-tight"
              style={{ color: "var(--bz-text-1)" }}
            >
              Zantara AI
            </span>
            <Sparkles
              size={10}
              className="flex-shrink-0"
              style={{ color: "var(--bz-accent)", opacity: 0.8 }}
            />
          </div>
          <p
            className="text-[11px] leading-snug truncate"
            style={{ color: "var(--bz-text-3)" }}
          >
            Intelligence &middot; Bali Zero
          </p>
        </div>

        {/* Arrow */}
        <ExternalLink
          size={13}
          className="flex-shrink-0 opacity-30 group-hover:opacity-70 transition-opacity duration-300"
          style={{ color: "var(--bz-text-2)" }}
        />
      </div>

      <style jsx>{`
        @keyframes lotusPulse {
          0%,
          100% {
            box-shadow: 0 0 0 0 rgba(212, 132, 90, 0.35);
          }
          50% {
            box-shadow: 0 0 0 5px rgba(212, 132, 90, 0);
          }
        }
        @keyframes liquidShift {
          0% {
            transform: scale(1) translate(0, 0);
          }
          100% {
            transform: scale(1.06) translate(2%, 1%);
          }
        }
      `}</style>
    </a>
  );
}
