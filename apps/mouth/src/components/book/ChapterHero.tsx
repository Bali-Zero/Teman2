"use client";

import Image from "next/image";
import { LazyMotion, domAnimation, m } from "framer-motion";

interface ChapterHeroProps {
  image: string;
  imageAlt: string;
  title: string;
  subtitle?: string;
  centered?: boolean;
}

export function ChapterHero({
  image,
  imageAlt,
  title,
  subtitle,
  centered,
}: ChapterHeroProps) {
  return (
    <LazyMotion features={domAnimation}>
      <div className="relative w-full min-h-screen overflow-hidden flex items-end">
        <Image
          src={image}
          alt={imageAlt}
          fill
          priority={false}
          className="object-cover"
          sizes="100vw"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0c0c0e] via-[#0c0c0e]/60 to-transparent" />
        <div
          className={`relative z-10 w-full px-8 md:px-16 pb-16 md:pb-24 ${
            centered ? "text-center mx-auto max-w-3xl" : "max-w-3xl"
          }`}
        >
          <m.h2
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            viewport={{ once: true }}
            className="font-[family-name:var(--font-spartan)] text-4xl md:text-5xl lg:text-6xl font-bold text-white leading-tight mb-4"
          >
            {title}
          </m.h2>
          {subtitle && (
            <m.p
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.15 }}
              viewport={{ once: true }}
              className="font-[family-name:var(--font-montserrat)] text-lg text-white/70 leading-relaxed"
            >
              {subtitle}
            </m.p>
          )}
        </div>
      </div>
    </LazyMotion>
  );
}
