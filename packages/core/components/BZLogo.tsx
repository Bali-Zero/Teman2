import type { CSSProperties } from "react";

export type BZLogoVariant = "full" | "mark" | "zantara" | "round";

interface BZLogoProps {
  variant: BZLogoVariant;
  size?: number;
  className?: string;
}

const SOURCES: Record<BZLogoVariant, { src: string; alt: string; defaultSize: number }> = {
  full:    { src: "/assets/logo/balizero-logo-clean.png",  alt: "Bali Zero", defaultSize: 44 },
  mark:    { src: "/assets/logo/balizero-3-red.png",       alt: "Bali Zero", defaultSize: 24 },
  zantara: { src: "/static/zantara-lotus.png",             alt: "Zantara",   defaultSize: 32 },
  round:   { src: "/assets/logo/balizero-logo-circle.png", alt: "Bali Zero", defaultSize: 48 },
};

export function BZLogo({ variant, size, className }: BZLogoProps) {
  const entry = SOURCES[variant];
  const style: CSSProperties = { height: `${size ?? entry.defaultSize}px`, width: "auto" };
  return <img src={entry.src} alt={entry.alt} style={style} className={className} />;
}
