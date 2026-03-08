"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import { ExternalLink, Globe, ArrowRight } from "lucide-react";

/**
 * HomepagePreviewWidget - Mostra un'anteprima della homepage balizero.com
 * sulla dashboard di kita.balizero.com
 */
export function HomepagePreviewWidget() {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--background-elevated)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border)] bg-gradient-to-r from-[#051C2C] to-[#0a1628]">
        <div className="flex items-center gap-2">
          <Globe className="w-5 h-5 text-[#2251ff]" />
          <h3 className="font-semibold text-[var(--foreground)]">
            Bali Zero Website
          </h3>
        </div>
        <Link
          href="https://balizero.com"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 text-sm text-[#2251ff] hover:text-[#2251ff]/80 transition-colors"
        >
          <span>Visita</span>
          <ExternalLink className="w-4 h-4" />
        </Link>
      </div>

      {/* Preview Content */}
      <div className="relative group">
        {/* Screenshot/Preview */}
        <div className="relative aspect-[16/9] overflow-hidden bg-[var(--muted)]">
          <Image
            src="/homepage-preview.jpg"
            alt="Bali Zero Homepage Preview"
            fill
            className="object-cover object-top transition-transform duration-500 group-hover:scale-105"
            sizes="(max-width: 768px) 100vw, 600px"
          />

          {/* Overlay gradient */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#051C2C]/90 via-transparent to-transparent" />

          {/* Live Badge */}
          <div className="absolute top-3 left-3 flex items-center gap-2 px-2.5 py-1 rounded-full bg-green-500/20 border border-green-500/30">
            <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs font-medium text-green-400">LIVE</span>
          </div>

          {/* Hover Action */}
          <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
            <Link
              href="https://balizero.com"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-[#2251ff] text-white font-medium hover:bg-[#2251ff]/90 transition-colors"
            >
              <span>Apri Homepage</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Footer Info */}
        <div className="absolute bottom-0 left-0 right-0 px-4 py-3">
          <p className="text-sm text-white/80 line-clamp-2">
            Esperti di visto, immigrazione e costituzione societaria a Bali. PT
            PMA, KITAS, Golden Visa, conformità fiscale.
          </p>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-px border-t border-[var(--border)] bg-[var(--border)]">
        <div className="px-4 py-3 bg-[var(--background-elevated)] text-center">
          <p className="text-lg font-semibold text-[var(--foreground)]">
            1000+
          </p>
          <p className="text-xs text-[var(--foreground-muted)]">Clienti</p>
        </div>
        <div className="px-4 py-3 bg-[var(--background-elevated)] text-center">
          <p className="text-lg font-semibold text-[var(--foreground)]">24/7</p>
          <p className="text-xs text-[var(--foreground-muted)]">Supporto</p>
        </div>
        <div className="px-4 py-3 bg-[var(--background-elevated)] text-center">
          <p className="text-lg font-semibold text-[var(--foreground)]">5★</p>
          <p className="text-xs text-[var(--foreground-muted)]">Rating</p>
        </div>
      </div>
    </div>
  );
}

/**
 * HomepagePreviewCompact - Versione compatta per sidebar o header
 */
export function HomepagePreviewCompact() {
  return (
    <Link
      href="https://balizero.com"
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-3 p-3 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] hover:border-[#2251ff]/50 hover:bg-[var(--background-elevated)]/80 transition-all group"
    >
      <div className="relative w-12 h-12 rounded-md overflow-hidden flex-shrink-0">
        <Image
          src="/homepage-preview.jpg"
          alt="Bali Zero"
          fill
          className="object-cover"
          sizes="48px"
        />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-[var(--foreground)] text-sm truncate">
          balizero.com
        </p>
        <p className="text-xs text-[var(--foreground-muted)] truncate">
          Sito pubblico live
        </p>
      </div>
      <ExternalLink className="w-4 h-4 text-[var(--foreground-muted)] group-hover:text-[#2251ff] transition-colors" />
    </Link>
  );
}
