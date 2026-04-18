"use client";

import * as React from "react";

interface StickyCtaProps {
  label: string;
  href: string;
  /** Show after the user has scrolled past this % of the page (0–100). */
  revealAtScrollPct?: number;
  /** Only show on viewports narrower than this px. Default 768 (mobile). */
  maxViewportPx?: number;
  onClick?: () => void;
  className?: string;
}

export function StickyCta({
  label,
  href,
  revealAtScrollPct = 50,
  maxViewportPx = 768,
  onClick,
  className = "",
}: Readonly<StickyCtaProps>) {
  const [visible, setVisible] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined") return;

    const check = () => {
      if (window.innerWidth >= maxViewportPx) {
        setVisible(false);
        return;
      }
      const doc = document.documentElement;
      const total = doc.scrollHeight - doc.clientHeight;
      if (total <= 0) {
        setVisible(false);
        return;
      }
      const pct = (window.scrollY / total) * 100;
      setVisible(pct >= revealAtScrollPct);
    };

    check();
    window.addEventListener("scroll", check, { passive: true });
    window.addEventListener("resize", check);
    return () => {
      window.removeEventListener("scroll", check);
      window.removeEventListener("resize", check);
    };
  }, [revealAtScrollPct, maxViewportPx]);

  if (!visible) return null;

  return (
    <div
      role="complementary"
      aria-label="Quick action"
      className={`fixed bottom-4 left-4 right-4 z-50 ${className}`}
      style={{ pointerEvents: "none" }}
    >
      <a
        href={href}
        onClick={onClick}
        className="block w-full text-center px-6 py-3 rounded-xl font-semibold shadow-lg transition-transform active:scale-[0.98]"
        style={{
          backgroundColor: "var(--bz-accent, #d4845a)",
          color: "#fff",
          pointerEvents: "auto",
        }}
      >
        {label}
      </a>
    </div>
  );
}
