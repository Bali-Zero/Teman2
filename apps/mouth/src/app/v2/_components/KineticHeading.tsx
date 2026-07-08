"use client";

import { useRef, type ElementType, type ReactNode, type CSSProperties } from "react";
import { motion, useInView } from "framer-motion";
import { usePrefersReducedMotion } from "@/lib/hooks/optimized/useMediaQuery";

// Wrapper is always a plain <div> (block, no intrinsic style) so the inView
// ref target is stable regardless of which semantic tag the caller renders
// inside it — dynamic tags (ElementType) can't safely take a typed DOM ref.

/**
 * KineticHeading — editorial section-title reveal (Wave 3 "The Dispatch").
 *
 * Blur→focus + a small rise as the heading crosses into viewport. Sobrio on
 * purpose: 12px of travel, 400ms, no bounce, no repeat-on-rescroll (`once:
 * true` — a masthead doesn't re-announce itself every time you scroll past
 * it). Reserves its own box (`willChange` only, no layout-affecting size
 * change) so there is no CLS: the element occupies its final geometry from
 * first paint, only opacity/blur/transform animate.
 *
 * `prefers-reduced-motion` → renders the heading with the animation already
 * complete (no transform, no blur, no fade) instead of skipping the
 * component; content is never gated behind motion.
 */
export function KineticHeading({
  as: Tag = "h2",
  children,
  className,
  style,
}: {
  as?: ElementType;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10% 0px" });
  const reduced = usePrefersReducedMotion();

  if (reduced) {
    return (
      <div ref={ref}>
        <Tag className={className} style={style}>
          {children}
        </Tag>
      </div>
    );
  }

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
      animate={
        inView
          ? { opacity: 1, y: 0, filter: "blur(0px)" }
          : { opacity: 0, y: 14, filter: "blur(6px)" }
      }
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      style={{ willChange: "opacity, transform, filter" }}
    >
      <Tag className={className} style={style}>
        {children}
      </Tag>
    </motion.div>
  );
}
