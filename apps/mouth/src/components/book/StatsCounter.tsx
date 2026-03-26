"use client";

import CountUp from "react-countup";
import { LazyMotion, domAnimation, m } from "framer-motion";
import type { Locale } from "./book-data";

interface Stat {
  value: number;
  suffix: string;
  label: string;
  separator: string;
}

const STATS_BY_LOCALE: Record<Locale, Stat[]> = {
  en: [
    { value: 5000, suffix: "+", label: "Clients served", separator: "," },
    { value: 20, suffix: "+", label: "Years of history", separator: "," },
    { value: 9612, suffix: "", label: "KBLI 2025 codes", separator: "," },
    { value: 4, suffix: "", label: "AI channels active", separator: "," },
  ],
  it: [
    { value: 5000, suffix: "+", label: "Clienti serviti", separator: "." },
    { value: 20, suffix: "+", label: "Anni di storia", separator: "." },
    { value: 9612, suffix: "", label: "Codici KBLI 2025", separator: "." },
    { value: 4, suffix: "", label: "Canali AI attivi", separator: "." },
  ],
  id: [
    { value: 5000, suffix: "+", label: "Klien dilayani", separator: "." },
    { value: 20, suffix: "+", label: "Tahun pengalaman", separator: "." },
    { value: 9612, suffix: "", label: "Kode KBLI 2025", separator: "." },
    { value: 4, suffix: "", label: "Channel AI aktif", separator: "." },
  ],
  ru: [
    { value: 5000, suffix: "+", label: "Клиентов обслужено", separator: " " },
    { value: 20, suffix: "+", label: "Лет опыта", separator: " " },
    { value: 9612, suffix: "", label: "Кодов KBLI 2025", separator: " " },
    { value: 4, suffix: "", label: "Активных AI-каналов", separator: " " },
  ],
  zh: [
    { value: 5000, suffix: "+", label: "服务客户数", separator: "," },
    { value: 20, suffix: "+", label: "年历史", separator: "," },
    { value: 9612, suffix: "", label: "KBLI 2025代码", separator: "," },
    { value: 4, suffix: "", label: "AI渠道", separator: "," },
  ],
};

interface StatsCounterProps {
  locale?: Locale;
}

export function StatsCounter({ locale = "en" }: StatsCounterProps) {
  const stats = STATS_BY_LOCALE[locale];
  return (
    <LazyMotion features={domAnimation}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-8 py-16 px-8 md:px-16">
        {stats.map((stat, i) => (
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
                separator={stat.separator}
              />
            </div>
            <div className="font-[family-name:var(--font-montserrat)] text-sm text-white/55 uppercase tracking-wider">
              {stat.label}
            </div>
          </m.div>
        ))}
      </div>
    </LazyMotion>
  );
}
