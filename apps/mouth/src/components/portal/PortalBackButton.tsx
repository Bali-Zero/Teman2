"use client";

/**
 * PortalBackButton
 *
 * Standardises the "back" affordance used on portal detail pages. Before
 * this we had three flavours: shadcn Button variant="ghost" with ChevronLeft,
 * bare <Link> with ArrowLeft, and router.back() buttons. Same job, different
 * paddings and colors.
 *
 * Always prefers an explicit href (safer: no history dead-ends when the user
 * lands on a deep URL directly) and falls back to router.back() if none is
 * given.
 */

import React from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

interface PortalBackButtonProps {
  href?: string;
  label?: string;
  className?: string;
}

export function PortalBackButton({
  href,
  label = "Back",
  className,
}: PortalBackButtonProps) {
  const router = useRouter();
  const baseClass =
    "inline-flex items-center gap-1 -ml-2 mb-4 px-2 py-1 rounded-md text-sm transition-colors hover:bg-white/5";
  const style: React.CSSProperties = { color: "var(--bz-text-2)" };

  if (href) {
    return (
      <Link
        href={href}
        className={`${baseClass} ${className ?? ""}`}
        style={style}
      >
        <ChevronLeft className="w-4 h-4" />
        {label}
      </Link>
    );
  }
  return (
    <button
      type="button"
      onClick={() => router.back()}
      className={`${baseClass} ${className ?? ""}`}
      style={style}
    >
      <ChevronLeft className="w-4 h-4" />
      {label}
    </button>
  );
}
