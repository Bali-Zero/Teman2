'use client';

import CountUp from 'react-countup';
import { LazyMotion, domAnimation, m } from 'framer-motion';

interface Stat {
  value: number;
  suffix: string;
  label: string;
}

const STATS: Stat[] = [
  { value: 5000, suffix: '+', label: 'Clienti serviti' },
  { value: 20, suffix: '+', label: 'Anni di storia' },
  { value: 9612, suffix: '', label: 'Codici KBLI 2025' },
  { value: 4, suffix: '', label: 'Canali AI attivi' },
];

export function StatsCounter() {
  return (
    <LazyMotion features={domAnimation}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-8 py-16 px-8 md:px-16">
        {STATS.map((stat, i) => (
          <m.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <div className="font-[family-name:var(--font-spartan)] text-4xl md:text-5xl font-black text-[#d4845a] mb-2">
              <CountUp
                end={stat.value}
                suffix={stat.suffix}
                duration={2}
                enableScrollSpy
                scrollSpyOnce
                separator="."
              />
            </div>
            <div className="font-[family-name:var(--font-montserrat)] text-sm text-white/60 uppercase tracking-wider">
              {stat.label}
            </div>
          </m.div>
        ))}
      </div>
    </LazyMotion>
  );
}
