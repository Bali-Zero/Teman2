/**
 * PortalEmptyState
 *
 * Shared empty-state card used across portal pages (visa / taxes / billing /
 * process / companies). Before this component every page rendered its own
 * hand-crafted "no data" card with slightly different spacing, opacity and
 * copy — so the portal looked like five different apps depending on which
 * tab you landed on.
 *
 * Keep the surface simple: an icon bubble, a heading, a supporting line,
 * and an optional CTA. If the CTA is a chat link we route to /portal/chat
 * (shareholders don't have email we can open for them).
 */

import React from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";

interface PortalEmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  cta?: {
    label: string;
    href: string;
  };
  className?: string;
}

export function PortalEmptyState({
  icon: Icon,
  title,
  description,
  cta,
  className,
}: PortalEmptyStateProps) {
  return (
    <section
      className={`rounded-xl border border-dashed p-12 text-center ${className ?? ""}`}
      style={{
        background: "rgba(30,30,35,0.7)",
        borderColor: "rgba(255,255,255,0.08)",
        backdropFilter: "blur(24px)",
      }}
    >
      <Icon
        className="w-16 h-16 mx-auto mb-4 opacity-30"
        style={{ color: "var(--bz-text-2)" }}
      />
      <h2
        className="text-lg font-semibold"
        style={{ color: "var(--bz-text-2)" }}
      >
        {title}
      </h2>
      {description && (
        <p className="text-sm mt-1" style={{ color: "var(--bz-text-3)" }}>
          {description}
        </p>
      )}
      {cta && (
        <Link
          href={cta.href}
          className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-full text-sm font-medium transition-opacity hover:opacity-80"
          style={{
            background: "rgba(201,169,110,0.12)",
            color: "var(--bz-accent-warm)",
          }}
        >
          {cta.label}
        </Link>
      )}
    </section>
  );
}
