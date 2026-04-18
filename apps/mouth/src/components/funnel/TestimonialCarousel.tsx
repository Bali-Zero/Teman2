"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface Testimonial {
  quote: string;
  author: string;
  role?: string;
  location?: string;
  rating?: 1 | 2 | 3 | 4 | 5;
}

interface TestimonialCarouselProps {
  testimonials: Testimonial[];
  autoPlayMs?: number;
  className?: string;
}

export function TestimonialCarousel({
  testimonials,
  autoPlayMs = 7000,
  className = "",
}: Readonly<TestimonialCarouselProps>) {
  const [index, setIndex] = React.useState(0);
  const [paused, setPaused] = React.useState(false);
  const count = testimonials.length;

  const goTo = React.useCallback(
    (next: number) => {
      if (count === 0) return;
      setIndex(((next % count) + count) % count);
    },
    [count],
  );

  React.useEffect(() => {
    if (paused || autoPlayMs <= 0 || count < 2) return;
    const id = window.setTimeout(() => goTo(index + 1), autoPlayMs);
    return () => window.clearTimeout(id);
  }, [index, paused, autoPlayMs, goTo, count]);

  if (count === 0) return null;
  const active = testimonials[index];

  const handleKey = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowRight") goTo(index + 1);
    if (event.key === "ArrowLeft") goTo(index - 1);
  };

  return (
    <section
      aria-roledescription="carousel"
      aria-label="Client testimonials"
      className={`relative rounded-2xl p-6 sm:p-8 ${className}`}
      style={{
        backgroundColor: "var(--bz-elevated, rgba(255,255,255,0.04))",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
      onKeyDown={handleKey}
      tabIndex={0}
    >
      <blockquote className="text-center">
        {active.rating ? (
          <div
            aria-label={`${active.rating} out of 5 stars`}
            className="flex items-center justify-center gap-1 mb-4"
          >
            {Array.from({ length: 5 }).map((_, i) => (
              <span
                key={i}
                aria-hidden="true"
                style={{
                  color:
                    i < (active.rating ?? 0)
                      ? "var(--bz-accent, #d4845a)"
                      : "rgba(255,255,255,0.2)",
                }}
              >
                ★
              </span>
            ))}
          </div>
        ) : null}
        <p className="text-base sm:text-lg leading-relaxed mb-4">
          “{active.quote}”
        </p>
        <footer
          className="text-sm"
          style={{ color: "var(--tx-secondary, rgba(255,255,255,0.55))" }}
        >
          <span className="font-semibold">{active.author}</span>
          {active.role ? <span> — {active.role}</span> : null}
          {active.location ? <span> · {active.location}</span> : null}
        </footer>
      </blockquote>

      {count > 1 ? (
        <>
          <button
            type="button"
            aria-label="Previous testimonial"
            onClick={() => goTo(index - 1)}
            className="absolute left-2 top-1/2 -translate-y-1/2 p-2 rounded-full hover:bg-white/10 transition-colors"
          >
            <ChevronLeft size={20} aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Next testimonial"
            onClick={() => goTo(index + 1)}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full hover:bg-white/10 transition-colors"
          >
            <ChevronRight size={20} aria-hidden="true" />
          </button>
          <div
            role="tablist"
            aria-label="Select testimonial"
            className="flex items-center justify-center gap-2 mt-4"
          >
            {testimonials.map((_, i) => (
              <button
                key={i}
                role="tab"
                aria-selected={i === index}
                aria-label={`Testimonial ${i + 1}`}
                onClick={() => goTo(i)}
                className="w-2 h-2 rounded-full transition-opacity"
                style={{
                  backgroundColor:
                    i === index
                      ? "var(--bz-accent, #d4845a)"
                      : "rgba(255,255,255,0.25)",
                }}
              />
            ))}
          </div>
        </>
      ) : null}
    </section>
  );
}
