/**
 * BrandTopbar — Bali Zero logo + ZANTARA wordmark + status pills slot.
 *
 * Read-only: pure presentational. Status pills are passed in as children
 * so each page composes its own (Global Pulse on home, Page nav on /wr2).
 */
import Image from "next/image";

interface BrandTopbarProps {
  tagline?: string;
  children?: React.ReactNode;
}

export default function BrandTopbar({
  tagline = "— Bali Zero command center",
  children,
}: BrandTopbarProps) {
  return (
    <header className="cockpit-topbar">
      <div className="cockpit-brand">
        <Image
          src="/balizero_logo_circle.png"
          alt="Bali Zero"
          className="cockpit-logo"
          width={44}
          height={44}
          priority
        />
        <span>ZANTARA</span>
        {tagline ? <span className="cockpit-tagline">{tagline}</span> : null}
      </div>
      <div className="cockpit-topbar-stats">{children}</div>
    </header>
  );
}
