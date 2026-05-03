"use client";

import CountUp from "react-countup";
import { LazyMotion, domAnimation, m } from "framer-motion";
import { useTranslation } from "@/i18n";
import type { Locale } from "./book-data";

interface Stat {
  value: number;
  suffix: string;
  labelKey: string;
}

// Number-formatting separator per locale. Stays hardcoded — it's typographical
// data, not user-facing copy.
const SEPARATOR_BY_LOCALE: Record<Locale, string> = {
  en: ",",
  it: ".",
  id: ".",
  ru: " ",
  zh: ",",
};

const STATS: Stat[] = [
  { value: 5000, suffix: "+", labelKey: "book.stats.clientsServed" },
  { value: 20, suffix: "+", labelKey: "book.stats.yearsOfHistory" },
  { value: 1563, suffix: "", labelKey: "book.stats.kbliNavigatorCodes" },
  { value: 4, suffix: "", labelKey: "book.stats.aiChannelsActive" },
];

interface StatsCounterProps {
  locale?: Locale;
}

export function StatsCounter({ locale = "en" }: StatsCounterProps) {
  const { t } = useTranslation();
  const separator = SEPARATOR_BY_LOCALE[locale] ?? ",";
  return (
    <LazyMotion features={domAnimation}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-8 py-16 px-8 md:px-16">
        {STATS.map((stat, i) => (
          <m.div
            key={stat.labelKey}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <div className="font-[family-name:var(--font-spartan)] text-4xl md:text-5xl font-black text-accent-warm mb-2">
              <CountUp
                end={stat.value}
                suffix={stat.suffix}
                duration={2}
                enableScrollSpy
                scrollSpyOnce
                separator={separator}
              />
            </div>
            <div className="font-[family-name:var(--font-montserrat)] text-sm text-white/55 uppercase tracking-wider">
              {t(stat.labelKey)}
            </div>
          </m.div>
        ))}
      </div>
    </LazyMotion>
  );
}
