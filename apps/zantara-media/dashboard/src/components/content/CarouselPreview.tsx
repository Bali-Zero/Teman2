"use client";

import React, { useState } from "react";
import { ChevronLeft, ChevronRight, Download, Instagram, ArrowRight, AlertTriangle } from "lucide-react";

// --- Types ---
type SlideLayout = "cover" | "text-only" | "image-overlay" | "cta";

interface SlideData {
  id: number;
  layout: SlideLayout;
  title?: string;
  badge?: string;
  headline?: string;
  subhead?: string;
  body?: string;
  bodyAccent?: string;
  items?: string[];
  quotes?: { text: string; author: string }[];
  boxes?: { title: string; content: string }[];
  highlightBox?: string;
  footer?: string;
  image?: string;
  services?: string[];
  tagline?: string;
}

// --- Content Configuration (SAME AS BEFORE) ---
const SLIDES_CONTENT: SlideData[] = [
  {
    id: 1,
    layout: "cover",
    badge: "BREAKING UPDATE",
    headline: "BALI'S TRAFFIC EXPERIMENT",
    subhead: "BOLD TIMING OR PURE CHAOS?",
    image: "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&q=80&w=1000",
  },
  {
    id: 2,
    layout: "text-only",
    title: "WHAT ACTUALLY HAPPENED?",
    body: "Badung Regency launched a 1-month traffic experiment in Kerobokan starting December 14, 2025.\n\nThe goal? Ease congestion before 2.8 million tourists arrive for Christmas and New Year.",
    bodyAccent: "THE TIMING? LEGENDARY.",
    footer: "Same weekend: Cyclone 93S hits. Floods in Seminyak, Kerobokan, Denpasar. Viral gridlock videos everywhere.\nYou have to admire the confidence.",
  },
  {
    id: 3,
    layout: "image-overlay",
    title: "THE FIRST WEEKEND",
    quotes: [
      {
        text: "It took me 1 hour to get from Umalas to Bintang Supermarket. Normally 25 minutes. And 1h45 to get back.",
        author: "Local resident"
      }
    ],
    image: "https://images.unsplash.com/photo-1515696955266-4f67e13219a8?auto=format&fit=crop&q=80&w=1000",
  },
  {
    id: 4,
    layout: "text-only",
    title: "THE 9 NEW TRAFFIC RULES",
    items: [
      "Jl. Gunung Tangkuban Perahu → One-way EAST to WEST",
      "Jl. Raya Kerobokan (from Petitenget) → One-way NORTH to Semer",
      "Jl. Raya Kerobokan (from Petitenget) → One-way SOUTH to Oberoi",
      "Simpang Teuku Umar Barat → NO right turn. Left only.",
      "Jl. Mertasari & Merta Agung → One-way SOUTH to NORTH",
      "Jl. Kerangan-Pengubengan Kauh → One-way NORTH to SOUTH",
      "Jl. Intan Permai → Must turn LEFT only",
      "Jl. Merta Agung exit → Must turn RIGHT only",
      "Jl. Umalas I → Southern exit CLOSED",
    ],
    highlightBox: "⚠️ Google Maps doesn't know yet.",
  },
  {
    id: 5,
    layout: "image-overlay",
    title: "WHAT PEOPLE ARE SAYING",
    quotes: [
      {
        text: "If it's successful, we'll implement it permanently.",
        author: "Dishub Badung"
      },
      {
        text: "That's all traffic in Bali has: hope and prayers.",
        author: "Bali Sun commenter"
      }
    ],
    image: "https://images.unsplash.com/photo-1552152370-fb05b263b96e?auto=format&fit=crop&q=80&w=1000",
  },
  {
    id: 6,
    layout: "text-only",
    title: "IS IT WORKING?",
    boxes: [
      { title: "TEST PERIOD", content: "1 month trial: Dec 14 – Jan 14" },
      { title: "THE METRICS", content: "Nobody really knows what \"working\" means." },
      { title: "THE REALITY", content: "Weekend #1 was chaos\nOfficers deployed everywhere\nAuthorities will \"evaluate and adjust\"\nEveryone else is winging it" }
    ],
    footer: "Stay tuned.",
  },
  {
    id: 7,
    layout: "image-overlay",
    title: "HOW TO SURVIVE THIS",
    items: [
      "Check Waze/Maps — but don't trust them blindly",
      "Avoid 8-10am and 5-8pm",
      "Add 30-60 min to Kerobokan trips",
      "Follow the traffic officers",
      "Airport runs? Leave embarrassingly early",
    ],
    highlightBox: "Sanur tip: Park & Ride at Mertasari Beach",
    image: "https://images.unsplash.com/photo-1558981285-6f0c94958bb6?auto=format&fit=crop&q=80&w=1000",
  },
  {
    id: 8,
    layout: "text-only",
    title: "THE BIGGER PICTURE",
    body: "This is part of a larger (very slow) plan:",
    items: [
      "New Ring Road — Sunset Road to Canggu connection",
      "Ocean Taxi — Airport to Seminyak/Uluwatu (promised Dec 2025)",
      "South Ring Road — Bypassing GWK nightmare",
      "LRT/Metro — Airport to Seminyak (promised... eventually)"
    ],
    bodyAccent: "6.5M+ tourists expected in 2025",
    footer: "Something had to change. Whether this was the right move... we'll find out.",
  },
  {
    id: 9,
    layout: "cta",
    badge: "NAVIGATING BALI'S CHAOS?",
    headline: "WE HELP YOU STAY COMPLIANT",
    body: "Traffic we can't fix. Paperwork? That's our thing.",
    services: [
      "Company Formation — PT PMA, CV, PT",
      "Visa Services — E33G, KITAS, extensions",
      "Licensing — NIB, OSS, SKPL, permits",
      "Tax & Compliance — Monthly reporting, Coretax"
    ],
    tagline: "BUILD SMART. BUILD LEGAL. BUILD WITH CERTAINTY.",
    footer: "DM us or visit balizero.com",
    image: "https://images.unsplash.com/photo-1516455207990-7a41ce80f7ee?auto=format&fit=crop&q=80&w=1000",
  }
];

// --- Theme Constants (UPDATED) ---
// Primary Palette: Grigio Riposante + Gold Accent + Soft Gradient Background
const THEME = {
  bg: "bg-[#2A2B2E]", // Grigio riposante (base)
  bgGradient: "bg-gradient-to-br from-[#2A2B2E] to-[#1F2023]", // Soft gradient
  gold: "#D4AF37", // Gold classico
  text: "#EAEAEA", // Bianco sporco per leggibilità riposante
  textMuted: "#A0A0A0",
};

// --- Helper Components ---

const Noise = () => (
  <div className="absolute inset-0 z-[1] opacity-[0.03] pointer-events-none mix-blend-overlay"
       style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")` }}
  />
);

const Header = ({ index, total }: { index: number; total: number }) => (
  <div className="absolute top-0 left-0 right-0 z-20 flex justify-between items-center w-full px-6 py-5">
    <div className="flex items-center gap-2">
      <div className="w-1.5 h-1.5 rounded-full shadow-[0_0_8px_rgba(212,175,55,0.6)]" style={{ backgroundColor: THEME.gold }} />
      <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-white/80 font-sans">
        BALI ZERO
      </span>
    </div>
    <span className="text-[10px] font-mono font-medium text-white/30">
      {index + 1}/{total}
    </span>
  </div>
);

const Footer = () => (
  <div className="absolute bottom-0 w-full px-6 py-5 flex justify-between items-center z-20">
    <div className="flex items-center gap-2 text-white/40 hover:text-white transition-colors">
      <Instagram size={12} />
      <span className="text-[10px] font-medium tracking-wide">@balizero0</span>
    </div>
    <div className="w-12 h-0.5 bg-white/10 rounded-full overflow-hidden">
        <div className="h-full w-1/3" style={{ backgroundColor: THEME.gold }} />
    </div>
  </div>
);

const ImageBackground = ({ src, intensity = 0.4 }: { src?: string; intensity?: number }) => {
  if (!src) return null;
  return (
    <>
      <div 
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: `url(${src})` }}
      />
      <div 
        className="absolute inset-0 bg-[#1F2023]"
        style={{ opacity: intensity }}
      />
      <div className="absolute inset-0 bg-gradient-to-t from-[#1F2023] via-transparent to-[#1F2023]/60" />
    </>
  );
};

// --- Slide Types ---

const CoverSlide = ({ data }: { data: SlideData }) => (
  <div className={`h-full flex flex-col relative overflow-hidden text-white font-sans group ${THEME.bg}`}>
    <ImageBackground src={data.image} intensity={0.3} />
    <Noise />
    
    <div className="flex-1 flex flex-col justify-end p-8 pb-20 relative z-10">
      {/* Badge */}
      <div className="self-start mb-6 px-3 py-1 bg-white/10 backdrop-blur-md border border-white/10 rounded text-[9px] font-bold uppercase tracking-widest text-white shadow-sm">
        {data.badge}
      </div>

      {/* Title Area */}
      <div className="flex flex-col gap-3">
        <h1 className="text-4xl font-black text-white leading-[0.9] tracking-tight uppercase drop-shadow-xl">
          {data.headline}
        </h1>
        <div className="w-8 h-0.5 mt-2 mb-2" style={{ backgroundColor: THEME.gold }} />
        <h2 className="text-lg font-bold uppercase tracking-wider text-white/90">
          {data.subhead}
        </h2>
      </div>
    </div>
    <Footer />
  </div>
);

const TextOnlySlide = ({ data, index, total }: { data: SlideData; index: number; total: number }) => (
  <div className={`h-full flex flex-col relative overflow-hidden font-sans ${THEME.bgGradient}`}>
    <Noise />
    <Header index={index} total={total} />
    
    <div className="flex-1 px-8 pt-20 pb-10 flex flex-col relative z-10">
      <div className="text-center mb-8">
        <h3 className="text-xl font-bold uppercase tracking-wider mb-2" style={{ color: THEME.gold }}>
           {data.title}
        </h3>
        <div className="mx-auto w-6 h-px bg-white/10" />
      </div>

      <div className="flex-1 overflow-y-auto pr-2 scrollbar-hide space-y-6 text-center">
        {data.body && (
          <p className="text-[14px] leading-relaxed font-light whitespace-pre-line" style={{ color: THEME.text }}>
            {data.body}
          </p>
        )}

        {data.bodyAccent && (
          <p className="text-lg font-bold uppercase tracking-wide" style={{ color: THEME.gold }}>
            {data.bodyAccent}
          </p>
        )}

        {data.items && (
          <ul className="space-y-3 text-left pl-2">
            {data.items.map((item, i) => (
              <li key={i} className="flex gap-3 text-[13px] leading-snug font-light border-b border-white/5 pb-2 last:border-0" style={{ color: THEME.text }}>
                <span className="mt-1.5 w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: THEME.gold }} />
                <span>
                   {item.includes('→') ? (
                       <>
                         <strong className="block mb-0.5 text-white font-medium">{item.split('→')[0]}</strong>
                         <span className="text-white/50 text-xs">→ {item.split('→')[1]}</span>
                       </>
                   ) : item}
                </span>
              </li>
            ))}
          </ul>
        )}

        {data.boxes && (
          <div className="grid gap-3 text-left">
            {data.boxes.map((box, i) => (
              <div key={i} className="p-4 rounded bg-white/5 border border-white/5">
                <h4 className="text-[10px] font-bold uppercase mb-1 tracking-widest text-white/60">{box.title}</h4>
                <p className="text-xs font-light whitespace-pre-line leading-relaxed text-white/90">{box.content}</p>
              </div>
            ))}
          </div>
        )}

        {data.highlightBox && (
          <div className="bg-[#D4AF37]/10 border border-[#D4AF37]/30 p-3 rounded flex items-center justify-center gap-3 mt-4">
            <AlertTriangle size={14} className="text-[#D4AF37]" />
            <p className="font-bold text-[11px] uppercase tracking-wide text-[#D4AF37]">
              {data.highlightBox.replace('⚠️', '')}
            </p>
          </div>
        )}
      </div>

      {data.footer && (
        <div className="mt-4 pt-4 border-t border-white/5 text-[10px] text-white/30 italic text-center">
          {data.footer}
        </div>
      )}
    </div>

    <Footer />
  </div>
);

const ImageOverlaySlide = ({ data, index, total }: { data: SlideData; index: number; total: number }) => (
  <div className={`h-full flex flex-col relative font-sans ${THEME.bg}`}>
    <ImageBackground src={data.image} intensity={0.6} />
    <Noise />
    <Header index={index} total={total} />
    
    <div className="flex-1 px-8 pt-20 flex flex-col justify-center relative z-10 text-center">
      {data.title && (
        <h3 className="text-2xl font-black uppercase mb-8 tracking-tight leading-none drop-shadow-xl text-white">
           {data.title}
        </h3>
      )}

      {data.quotes && (
        <div className="space-y-8">
          {data.quotes.map((quote, i) => (
            <div key={i} className="relative">
              <div className="text-lg font-light italic leading-relaxed text-white/90 font-serif">
                "{quote.text}"
              </div>
              <div className="mt-4 flex justify-center items-center gap-2">
                <span className="text-[9px] font-bold uppercase tracking-widest text-[#D4AF37]">
                  — {quote.author}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {data.items && (
        <ul className="space-y-4 text-left pl-2">
          {data.items.map((item, i) => (
            <li key={i} className="flex items-center gap-3 text-[14px] font-medium text-white drop-shadow-md">
              <div className="w-1.5 h-1.5 rounded-full bg-[#D4AF37] flex-shrink-0" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}

      {data.highlightBox && (
        <div className="mt-8 bg-white/10 backdrop-blur-md border border-white/20 p-3 rounded text-white font-bold text-[11px] uppercase tracking-wide text-center">
          {data.highlightBox}
        </div>
      )}
    </div>

    <Footer />
  </div>
);

const CTASlide = ({ data, index, total }: { data: SlideData; index: number; total: number }) => (
  <div className={`h-full flex flex-col relative font-sans group ${THEME.bg}`}>
    <ImageBackground src={data.image} intensity={0.7} />
    <Noise />
    <Header index={index} total={total} />

    <div className="flex-1 px-8 pt-20 pb-12 flex flex-col relative z-10 text-center">
      <span className="text-[9px] font-bold tracking-[0.25em] uppercase mb-4 text-[#D4AF37]">
        {data.badge}
      </span>
      <h3 className="text-3xl font-black uppercase italic leading-[0.9] mb-6 tracking-tight text-white">
        {data.headline}
      </h3>
      <p className="text-xs font-medium text-white/80 mb-8 max-w-[80%] mx-auto">
        {data.body}
      </p>

      <ul className="space-y-2 mb-auto text-left mx-auto">
        {data.services?.map((service, i) => (
          <li key={i} className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-white">
            <span className="text-[#D4AF37]">•</span>
            {service}
          </li>
        ))}
      </ul>

      <div className="mt-8">
        <div className="border border-white/10 bg-black/40 p-2 text-center mb-4 rounded">
          <p className="text-[8px] font-bold tracking-[0.2em] uppercase text-[#D4AF37]">
            {data.tagline}
          </p>
        </div>

        <button className="w-full py-3 bg-white text-black font-bold text-[10px] uppercase tracking-widest hover:bg-[#D4AF37] transition-all flex items-center justify-center gap-2 rounded-sm">
          {data.footer} <ArrowRight size={12} />
        </button>
      </div>
    </div>
  </div>
);

// --- Main Container ---

export default function CarouselPreview() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const totalSlides = SLIDES_CONTENT.length;

  const nextSlide = () => setCurrentSlide((prev) => Math.min(prev + 1, totalSlides - 1));
  const prevSlide = () => setCurrentSlide((prev) => Math.max(prev - 1, 0));

  return (
    <div className="flex flex-col items-center gap-8 py-12 bg-[#1A1A1A] min-h-screen font-sans">
      <div className="flex flex-col items-center gap-1">
        <h1 className="text-lg font-bold text-[#EAEAEA] tracking-wide uppercase">
          Bali Zero <span className="text-[#D4AF37]">Editor</span>
        </h1>
      </div>

      <div className="relative group">
        <div 
          className="w-[380px] h-[475px] bg-[#2A2B2E] shadow-2xl rounded-sm overflow-hidden"
          style={{ aspectRatio: "4/5" }}
        >
          {(() => {
            const slide = SLIDES_CONTENT[currentSlide];
            switch (slide.layout) {
              case "cover": return <CoverSlide data={slide} />; 
              case "text-only": return <TextOnlySlide data={slide} index={currentSlide} total={totalSlides} />; 
              case "cta": return <CTASlide data={slide} index={currentSlide} total={totalSlides} />; 
              default: return <ImageOverlaySlide data={slide} index={currentSlide} total={totalSlides} />;
            }
          })()}
        </div>

        <div className="absolute -left-20 top-1/2 -translate-y-1/2 flex flex-col gap-2">
           <button onClick={prevSlide} disabled={currentSlide === 0} className="p-4 rounded-full bg-white/5 text-white hover:bg-white/10 transition-all disabled:opacity-0">
             <ChevronLeft size={20} />
           </button>
        </div>
        <div className="absolute -right-20 top-1/2 -translate-y-1/2 flex flex-col gap-2">
           <button onClick={nextSlide} disabled={currentSlide === totalSlides - 1} className="p-4 rounded-full bg-white/5 text-white hover:bg-white/10 transition-all disabled:opacity-0">
             <ChevronRight size={20} />
           </button>
        </div>
      </div>

      <div className="flex gap-4">
        <button className="px-8 py-3 bg-[#D4AF37] text-black font-bold text-xs uppercase tracking-widest hover:bg-white transition-colors shadow-lg shadow-black/20 flex items-center gap-2 rounded-sm">
          <Download size={16} /> Download
        </button>
      </div>
    </div>
  );
}
