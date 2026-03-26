'use client';

import { LazyMotion, domAnimation, m } from 'framer-motion';
import { MILESTONES } from './book-data';

export function TimelineComponent() {
  return (
    <LazyMotion features={domAnimation}>
      <div className="px-8 md:px-16 py-12 overflow-x-auto">
        <div className="flex md:flex-row flex-col gap-0 min-w-max md:min-w-0 relative">
          {/* Horizontal line (desktop) */}
          <div className="hidden md:block absolute top-6 left-0 right-0 h-px bg-white/10" />

          {MILESTONES.map((milestone, i) => (
            <m.div
              key={milestone.year}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              viewport={{ once: true }}
              className="relative md:flex-1 flex md:flex-col items-start md:items-center gap-4 md:gap-0 pb-8 md:pb-0 pl-8 md:pl-0"
            >
              {/* Dot */}
              <div className="md:mb-4 flex-shrink-0">
                <div className="w-3 h-3 rounded-full bg-[#d4845a] ring-4 ring-[#d4845a]/20 relative z-10" />
              </div>
              {/* Vertical line (mobile) */}
              {i < MILESTONES.length - 1 && (
                <div className="md:hidden absolute left-[18px] top-3 bottom-0 w-px bg-white/10" />
              )}
              {/* Content */}
              <div className="md:text-center md:px-4 max-w-[200px]">
                <span className="font-[family-name:var(--font-spartan)] text-[#d4845a] font-bold text-sm block mb-1">
                  {milestone.year}
                </span>
                <h4 className="font-[family-name:var(--font-spartan)] text-white font-semibold text-base mb-1">
                  {milestone.label}
                </h4>
                <p className="font-[family-name:var(--font-montserrat)] text-white/50 text-xs leading-relaxed">
                  {milestone.description}
                </p>
              </div>
            </m.div>
          ))}
        </div>
      </div>
    </LazyMotion>
  );
}
