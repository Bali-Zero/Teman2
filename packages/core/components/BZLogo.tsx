import Image from "next/image";

export type BZLogoVariant = "full" | "mark" | "round" | "zantara";

interface BZLogoProps {
  variant: BZLogoVariant;
  size?: number;
  className?: string;
  priority?: boolean;
}

// Square intrinsic aspect for all variants (all assets are n×n).
const SOURCES: Record<
  BZLogoVariant,
  { src: string; alt: string; defaultSize: number }
> = {
  full: {
    src: "/assets/logo/balizero-logo-clean.png",
    alt: "Bali Zero",
    defaultSize: 44,
  },
  mark: {
    src: "/assets/logo/balizero-3-red.png",
    alt: "Bali Zero",
    defaultSize: 24,
  },
  round: {
    src: "/assets/logo/balizero-logo-circle.png",
    alt: "Bali Zero",
    defaultSize: 56,
  },
  zantara: {
    src: "/static/zantara-lotus.png",
    alt: "Zantara",
    defaultSize: 32,
  },
};

export function BZLogo({ variant, size, className, priority }: BZLogoProps) {
  const entry = SOURCES[variant];
  const dim = size ?? entry.defaultSize;
  return (
    <Image
      src={entry.src}
      alt={entry.alt}
      width={dim}
      height={dim}
      priority={priority}
      className={className}
      style={{ height: `${dim}px`, width: "auto" }}
    />
  );
}
