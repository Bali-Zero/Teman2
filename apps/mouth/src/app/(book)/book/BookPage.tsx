'use client';

import { BookShell } from '@/components/book/BookShell';
import { ChapterSection } from '@/components/book/ChapterSection';
import { ChapterHero } from '@/components/book/ChapterHero';
import { StatsCounter } from '@/components/book/StatsCounter';
import { TeamGrid } from '@/components/book/TeamGrid';
import { TimelineComponent } from '@/components/book/TimelineComponent';
import { ZantaraCTA } from '@/components/book/ZantaraCTA';
import { ServicePricingCard } from '@/components/book/ServicePricingCard';
import { CHAPTERS, CONTACTS } from '@/components/book/book-data';
import Image from 'next/image';

interface BookPageProps {
  initialChapter?: string;
}

export function BookPage({ initialChapter }: BookPageProps) {
  const handleZantara = () => {
    const trigger = document.querySelector<HTMLButtonElement>('[data-zantara-trigger]');
    if (trigger) trigger.click();
  };

  return (
    <BookShell initialChapter={initialChapter}>
      {/* Chapter 1: Cover */}
      <ChapterSection id="cover" className="flex items-center justify-center">
        <div className="absolute inset-0">
          <Image
            src="/static/image_art/zantara_gold_black_gradient_transparent.png"
            alt="Bali Zero"
            fill
            priority
            className="object-cover"
            sizes="100vw"
          />
          <div className="absolute inset-0 bg-[#0c0c0e]/50" />
        </div>
        <div className="relative z-10 text-center px-8">
          <p className="font-[family-name:var(--font-montserrat)] text-[#d4845a] tracking-[0.3em] text-sm uppercase mb-6">
            Da CV Bayu Santero (2006) a Bali Zero (2020)
          </p>
          <h1 className="font-[family-name:var(--font-spartan)] text-6xl md:text-8xl font-black text-white mb-4">
            Bali Zero
          </h1>
          <p className="font-[family-name:var(--font-montserrat)] text-white/60 text-xl">
            L&apos;unica agenzia AI-first in Indonesia.
          </p>
          <div className="mt-12 animate-bounce text-white/30">↓</div>
        </div>
      </ChapterSection>

      {/* Chapter 2: Manifesto */}
      <ChapterSection id="manifesto">
        <ChapterHero
          image={CHAPTERS[1].heroImage}
          imageAlt={CHAPTERS[1].heroImageAlt}
          title={CHAPTERS[1].title}
          subtitle={CHAPTERS[1].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-3xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-6">
            Tutto è iniziato nel 2006, quando Pak Zainal Abidin ha fondato CV Bayu Santero a Bali.
            Quattordici anni di esperienza nel mercato indonesiano. Di clienti aiutati. Di regolamenti
            navigati. Di storie di successo costruite mattone per mattone.
          </p>
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed">
            Nel 2020, un incontro ha cambiato tutto. Una visione nuova si è unita a radici profonde.
            Da quell&apos;incontro è nato Bali Zero — non una startup, ma l&apos;evoluzione di vent&apos;anni di storia.
          </p>
        </div>
        <StatsCounter />
      </ChapterSection>

      {/* Chapter 3: Origin */}
      <ChapterSection id="origin">
        <ChapterHero
          image={CHAPTERS[2].heroImage}
          imageAlt={CHAPTERS[2].heroImageAlt}
          title={CHAPTERS[2].title}
          subtitle={CHAPTERS[2].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-3xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-6">
            Pak Zainal Abidin aveva già visto tutto. Clienti stranieri persi nel labirinto burocratico
            indonesiano. Visti sbagliati. Aziende aperte con codici KBLI errati. Soldi sprecati per
            mancanza di informazioni precise.
          </p>
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed">
            L&apos;incontro con Zero ha portato una risposta diversa: trasparenza totale sui prezzi,
            tecnologia AI per rispondere in 3 secondi, un team di 22 persone completamente dedicato.
            Non un&apos;agenzia. Una piattaforma.
          </p>
        </div>
        <TimelineComponent />
      </ChapterSection>

      {/* Chapter 4: Team */}
      <ChapterSection id="team">
        <ChapterHero
          image={CHAPTERS[3].heroImage}
          imageAlt={CHAPTERS[3].heroImageAlt}
          title={CHAPTERS[3].title}
          subtitle={CHAPTERS[3].subtitle}
        />
        <div className="bg-[#0c0c0e]">
          <TeamGrid />
        </div>
      </ChapterSection>

      {/* Chapter 5: Services */}
      <ChapterSection id="services">
        <ChapterHero
          image={CHAPTERS[4].heroImage}
          imageAlt={CHAPTERS[4].heroImageAlt}
          title={CHAPTERS[4].title}
          subtitle={CHAPTERS[4].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl">
            <ServicePricingCard
              title="Visto Singola Entrata"
              tagline="C317 / B1 — fino a 180 giorni"
              serviceKey="C317 Single Entry"
              features={[
                'Consulenza iniziale',
                'Preparazione documenti',
                'Presentazione pratica',
                'Tracking status',
              ]}
              waMessage="Ciao, sono interessato al Visto Singola Entrata. Puoi darmi info?"
            />
            <ServicePricingCard
              title="Visto Multipla Entrata"
              tagline="E33G — 12 mesi, entrate illimitate"
              serviceKey="E33G Multiple Entry"
              features={[
                'Consulenza iniziale',
                'Preparazione documenti',
                'Presentazione pratica',
                'Tracking status',
                'Supporto rinnovi',
              ]}
              waMessage="Ciao, sono interessato al Visto Multipla Entrata E33G. Puoi darmi info?"
            />
            <ServicePricingCard
              title="KITAS Pensionato"
              tagline="Permesso soggiorno annuale"
              serviceKey="KITAS Retirement"
              features={[
                'Verifica requisiti',
                'Preparazione documenti',
                'Pratica completa',
                'Rinnovi inclusi 1° anno',
              ]}
              waMessage="Ciao, sono interessato al KITAS Pensionato. Puoi darmi info?"
            />
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* Chapter 6: Impact */}
      <ChapterSection id="impact">
        <ChapterHero
          image={CHAPTERS[5].heroImage}
          imageAlt={CHAPTERS[5].heroImageAlt}
          title={CHAPTERS[5].title}
          subtitle={CHAPTERS[5].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-4xl">
          <p className="font-[family-name:var(--font-montserrat)] text-white/70 text-lg leading-relaxed mb-10">
            Mentre i competitor perdono personale (-8% a -23% annuo), Bali Zero cresce.
            La differenza? Siamo gli unici con un AI stack in produzione.
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { name: 'Emerhub', founded: 2011, trend: '-8.5%' },
              { name: 'InCorp', founded: 2012, trend: '-19%' },
              { name: 'LetsMoveIndonesia', founded: 2015, trend: '-23.5%' },
              { name: 'Seven Stones', founded: 2016, trend: '+1.8%' },
            ].map((c) => (
              <div key={c.name} className="border border-white/5 rounded-xl p-4 text-center">
                <p className="font-[family-name:var(--font-spartan)] text-white/60 text-sm font-semibold mb-1">
                  {c.name}
                </p>
                <p className="font-[family-name:var(--font-spartan)] text-red-400 font-black text-2xl">
                  {c.trend}
                </p>
                <p className="text-white/30 text-xs mt-1">headcount YoY</p>
              </div>
            ))}
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* Chapter 7: Technology */}
      <ChapterSection id="technology">
        <ChapterHero
          image={CHAPTERS[6].heroImage}
          imageAlt={CHAPTERS[6].heroImageAlt}
          title={CHAPTERS[6].title}
          subtitle={CHAPTERS[6].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-12 max-w-3xl">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-10">
            {[
              { n: '96', l: 'MCP Tools in produzione' },
              { n: '56K', l: 'Nodi nel knowledge graph' },
              { n: '66K+', l: 'Documenti legali indicizzati' },
              { n: '9.612', l: 'Codici KBLI 2025' },
              { n: '4', l: 'Canali AI attivi 24/7' },
              { n: '< 3s', l: 'Tempo medio di risposta' },
            ].map((s) => (
              <div key={s.l} className="border border-white/5 rounded-xl p-4">
                <p className="font-[family-name:var(--font-spartan)] text-[#d4845a] font-black text-3xl mb-1">
                  {s.n}
                </p>
                <p className="font-[family-name:var(--font-montserrat)] text-white/50 text-xs">
                  {s.l}
                </p>
              </div>
            ))}
          </div>
        </div>
        <ZantaraCTA onClick={handleZantara} />
      </ChapterSection>

      {/* Chapter 8: Contact */}
      <ChapterSection id="contact">
        <ChapterHero
          image={CHAPTERS[7].heroImage}
          imageAlt={CHAPTERS[7].heroImageAlt}
          title={CHAPTERS[7].title}
          subtitle={CHAPTERS[7].subtitle}
        />
        <div className="bg-[#0c0c0e] px-8 md:px-16 py-16 text-center max-w-2xl mx-auto">
          <div className="flex flex-col sm:flex-row gap-4 justify-center mt-8">
            <a
              href={`${CONTACTS.whatsappUrl}?text=Ciao, vorrei saperne di più sui servizi Bali Zero`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl bg-[#25D366] text-white font-[family-name:var(--font-montserrat)] font-semibold text-lg hover:bg-[#1fb855] transition-colors"
            >
              {CONTACTS.whatsapp}
            </a>
            <a
              href={`mailto:${CONTACTS.email}`}
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-2xl border border-white/20 text-white font-[family-name:var(--font-montserrat)] font-semibold hover:bg-white/5 transition-colors"
            >
              {CONTACTS.email}
            </a>
          </div>
          <p className="font-[family-name:var(--font-montserrat)] text-white/30 text-sm mt-8">
            © 2006–2026 CV Bayu Santero / Bali Zero. Tutti i diritti riservati.
          </p>
        </div>
      </ChapterSection>
    </BookShell>
  );
}
