"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const navRef = useRef<HTMLElement>(null);
  const searchTextRef = useRef<HTMLSpanElement>(null);
  const router = useRouter();

  const handleHeroSearch = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const query = new FormData(e.currentTarget).get("q");
    if (query) {
      router.push(`/kbli?q=${encodeURIComponent(query.toString())}`);
    }
  };

  useEffect(() => {
    const nav = navRef.current;
    if (!nav) return;
    const onScroll = () => {
      if (window.scrollY > 20) nav.classList.add("scrolled");
      else nav.classList.remove("scrolled");
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = searchTextRef.current;
    if (!el) return;
    const queries = ["62019", "villa bali", "cafe restoran", "IT consulting"];
    let qi = 0;
    let timer: ReturnType<typeof setTimeout>;
    function cycle() {
      el!.style.animation = "none";
      el!.textContent = "";
      void el!.offsetWidth;
      const q = queries[qi % queries.length];
      el!.textContent = q;
      el!.style.animation = `typing 1.5s steps(${q.length}) 0.3s both`;
      qi++;
      timer = setTimeout(cycle, 4000);
    }
    timer = setTimeout(cycle, 3500);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    const reveals = document.querySelectorAll(".reveal");
    const obs = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add("visible");
        }),
      { threshold: 0.1 },
    );
    reveals.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  return (
    <>
      <style>{`
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
          --red: #dc2626;
          --red-dim: rgba(220,38,38,0.15);
          --red-border: rgba(220,38,38,0.25);
          --bg: #0a0a0a;
          --bg2: #0f0f0f;
          --bg3: #141414;
          --surface: rgba(255,255,255,0.03);
          --border: rgba(255,255,255,0.07);
          --text: #ffffff;
          --muted: #6b7280;
          --subtle: #9ca3af;
          --violet: #7c3aed;
          --violet-dim: rgba(124,58,237,0.2);
          --violet-border: rgba(124,58,237,0.35);
        }
        html { scroll-behavior: smooth; }
        body { font-family: var(--font-montserrat), 'Montserrat', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; overflow-x: hidden; }

        /* ── BACKGROUND ORNAMENTAL PATTERN ── */
        .bali-bg {
          position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden;
        }
        /* Tiled ornamental SVG pattern — Balinese / Art Nouveau */
        .bali-pattern {
          position: absolute; inset: 0; width: 100%; height: 100%;
          background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect width='200' height='200' fill='none'/%3E%3Crect x='0' y='0' width='200' height='200' fill='none' stroke='rgba(255,255,255,0.06)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='50' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='30' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='8' fill='none' stroke='rgba(255,255,255,0.06)' stroke-width='0.5'/%3E%3Ccircle cx='100' cy='100' r='2' fill='rgba(255,255,255,0.08)'/%3E%3Cpath d='M100,50 Q120,70 100,90 Q80,70 100,50Z' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Cpath d='M100,150 Q120,130 100,110 Q80,130 100,150Z' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Cpath d='M50,100 Q70,120 90,100 Q70,80 50,100Z' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Cpath d='M150,100 Q130,120 110,100 Q130,80 150,100Z' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Cpath d='M60,60 Q80,80 100,70' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Cpath d='M140,60 Q120,80 100,70' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Cpath d='M60,140 Q80,120 100,130' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Cpath d='M140,140 Q120,120 100,130' fill='none' stroke='rgba(255,255,255,0.04)' stroke-width='0.5'/%3E%3Ccircle cx='0' cy='0' r='20' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Ccircle cx='200' cy='0' r='20' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Ccircle cx='0' cy='200' r='20' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3Ccircle cx='200' cy='200' r='20' fill='none' stroke='rgba(255,255,255,0.05)' stroke-width='0.5'/%3E%3C/svg%3E");
          background-size: 200px 200px;
          opacity: 1;
        }
        /* Vignette to fade edges */
        .bali-vignette {
          position: absolute; inset: 0;
          background: radial-gradient(ellipse 80% 70% at 50% 50%, transparent 30%, rgba(10,10,10,0.85) 100%);
        }

        /* AMBIENT ORBS — cool blue/violet, no warm red */
        .orb { position: fixed; border-radius: 50%; filter: blur(130px); pointer-events: none; z-index: 0; }
        .orb-1 { width: 700px; height: 700px; background: radial-gradient(circle, rgba(59,130,246,0.07), transparent 70%); top: -150px; left: -150px; }
        .orb-2 { width: 500px; height: 500px; background: radial-gradient(circle, rgba(124,58,237,0.07), transparent 70%); bottom: 100px; right: -150px; }
        .orb-3 { width: 300px; height: 300px; background: radial-gradient(circle, rgba(16,185,129,0.04), transparent 70%); top: 60%; left: 40%; }

        /* ── NAV ── */
        .kbli-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 100; background: rgba(5, 5, 5, 0.35); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border-bottom: 1px solid rgba(255,255,255,0.04); box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1); transition: border-color 0.3s, background 0.3s; padding: 0 48px; height: 64px; display: flex; align-items: center; justify-content: space-between; }
        .kbli-nav.scrolled { border-bottom-color: rgba(255,255,255,0.08); background: rgba(5, 5, 5, 0.55); }
        .nav-logo { display: flex; align-items: center; gap: 10px; text-decoration: none; }
        .nav-links { display: flex; list-style: none; gap: 8px; }
        .nav-links a { color: var(--subtle); text-decoration: none; font-size: 14px; font-weight: 500; padding: 6px 14px; border-radius: 8px; transition: color 0.2s, background 0.2s; }
        .nav-links a:hover { color: #fff; background: rgba(255,255,255,0.06); }
        /* Zantara AI — violet pill with lotus image */
        .nav-cta { display: inline-flex; align-items: center; gap: 7px; background: var(--violet-dim); border: 1px solid var(--violet-border); color: #c4b5fd; font-size: 13px; font-weight: 600; padding: 6px 16px 6px 6px; border-radius: 20px; text-decoration: none; transition: background 0.2s; }
        .nav-cta:hover { background: rgba(124,58,237,0.35); }
        .lotus-icon { width: 28px; height: 28px; flex-shrink: 0; object-fit: contain; }
        @media (max-width: 768px) { .kbli-nav { padding: 0 20px; } .nav-links { display: none; } }

        /* ── HERO ── */
        .hero { position: relative; z-index: 1; min-height: 100vh; display: flex; align-items: center; padding: 100px 64px 60px; gap: 80px; max-width: 1280px; margin: 0 auto; }
        .hero-left { flex: 1; max-width: 580px; }

        /* Tagline top — logo bigger, text bold white */
        .hero-tagline-top { display: flex; align-items: center; gap: 18px; margin-bottom: 32px; }
        .tagline-logo-wrap { flex-shrink: 0; }
        .tagline-lines { display: flex; flex-direction: column; gap: 2px; }
        .tagline-line { font-size: 15px; font-weight: 700; color: #ffffff; letter-spacing: 0.01em; line-height: 1.5; }

        .hero-h1 { font-family: var(--font-league-spartan), 'League Spartan', sans-serif; font-size: clamp(64px, 8vw, 96px); font-weight: 900; line-height: 0.95; letter-spacing: -0.02em; margin-bottom: 16px; }

        /* ── KBLI 2025: Indonesia flag — white→red→white shimmer, exactly like original ── */
        .kbli-shine {
          background: linear-gradient(
            90deg,
            #ffffff 0%,
            #ffffff 20%,
            #f87171 38%,
            #dc2626 48%,
            #f87171 58%,
            #ffffff 75%,
            #ffffff 100%
          );
          background-size: 250% auto;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          animation: shine 4s linear infinite;
        }
        @keyframes shine { to { background-position: -250% center; } }

        .hero-guide { font-family: var(--font-montserrat), 'Montserrat', sans-serif; font-style: normal; font-size: clamp(22px, 3vw, 28px); color: var(--subtle); margin-bottom: 16px; }
        .shine-text {
          font-style: italic;
          background: linear-gradient(
            90deg,
            #ffffff 0%,
            #ffffff 15%,
            #f87171 35%,
            #dc2626 50%,
            #f87171 65%,
            #ffffff 85%,
            #ffffff 100%
          );
          background-size: 250% auto;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          animation: shine 4s linear infinite;
          animation-delay: 0.8s;
        }
        .hero-sub { font-size: 14px; color: var(--muted); margin-bottom: 32px; letter-spacing: 0.02em; }
        .sep { margin: 0 8px; opacity: 0.4; }
        
        /* ── HERO SEARCH (Liquid Glass) ── */
        .hero-search-form { display: flex; width: 100%; max-width: 520px; align-items: center; background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 8px 8px 8px 20px; box-shadow: 0 8px 32px rgba(0,0,0,0.3); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); transition: border-color 0.3s, background 0.3s, box-shadow 0.3s; }
        .hero-search-form:focus-within { border-color: rgba(255, 255, 255, 0.15); background: rgba(255, 255, 255, 0.04); box-shadow: 0 8px 40px rgba(0,0,0,0.4); }
        .hero-search-icon { color: var(--muted); margin-right: 12px; font-size: 18px; }
        .hero-search-input { flex: 1; background: transparent; border: none; color: #fff; font-size: 16px; outline: none; }
        .hero-search-input::placeholder { color: var(--subtle); }
        .hero-search-btn { background: var(--red); color: white; border: none; padding: 14px 28px; border-radius: 12px; font-weight: 700; cursor: pointer; transition: background 0.2s, transform 0.2s; letter-spacing: 0.01em; }
        .hero-search-btn:hover { background: #b91c1c; transform: translateY(-1px); }
        
        .cta-primary { display: inline-flex; align-items: center; gap: 8px; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #fff; font-size: 14px; font-weight: 600; padding: 12px 24px; border-radius: 12px; text-decoration: none; transition: background 0.2s, transform 0.2s; letter-spacing: 0.01em; backdrop-filter: blur(10px); }
        .cta-primary:hover { background: rgba(255,255,255,0.1); transform: translateY(-1px); }
        @media (max-width: 900px) { .hero { flex-direction: column; padding: 100px 24px 60px; } .hero-right { width: 100%; display: flex; justify-content: center; } }

        /* ── TRUST BAR ── */
        .trust-bar { position: relative; z-index: 1; display: flex; justify-content: center; gap: 64px; padding: 32px 48px; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); background: var(--bg2); }
        .trust-item { text-align: center; }
        .trust-num { font-family: var(--font-montserrat), 'Montserrat', sans-serif; font-size: 28px; font-weight: 900; color: #fff; }
        .trust-label { font-size: 11px; color: var(--muted); margin-top: 2px; letter-spacing: 0.05em; text-transform: uppercase; }

        /* ── FEATURES ── */
        .features { position: relative; z-index: 1; max-width: 1100px; margin: 0 auto; padding: 80px 48px; }
        .section-tag { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.12em; color: var(--red); margin-bottom: 14px; }
        .section-h2 { font-family: var(--font-montserrat), 'Montserrat', sans-serif; font-style: normal; font-weight: 800; font-size: clamp(32px, 4vw, 48px); color: #fff; margin-bottom: 12px; line-height: 1.1; }
        .section-sub { font-size: 15px; color: var(--muted); max-width: 520px; line-height: 1.65; margin-bottom: 48px; }
        .bento { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
        .bento-card { background: var(--bg3); border: 1px solid var(--border); border-radius: 20px; padding: 28px; opacity: 0; transform: translateY(20px); }
        .bento-card.visible { opacity: 1; transform: translateY(0); transition: opacity 0.5s ease, transform 0.5s ease, border-color 0.2s, box-shadow 0.2s; }
        .bento-card:hover { border-color: rgba(220,38,38,0.3); box-shadow: 0 0 32px rgba(220,38,38,0.06); }
        .bento-card.span2 { grid-column: span 2; }
        .bento-card.tall { min-height: 280px; }
        .card-icon { font-size: 24px; margin-bottom: 14px; }
        .card-title { font-size: 16px; font-weight: 700; color: #fff; margin-bottom: 8px; }
        .card-desc { font-size: 13px; color: var(--muted); line-height: 1.65; }
        @media (max-width: 768px) { .bento { grid-template-columns: 1fr; } .bento-card.span2 { grid-column: span 1; } }

        /* AI DEMO */
        .ai-demo { margin-top: 20px; display: flex; flex-direction: column; gap: 10px; }
        .ai-msg { padding: 10px 14px; border-radius: 12px; font-size: 13px; line-height: 1.55; max-width: 85%; }
        .ai-msg.user { background: rgba(255,255,255,0.06); color: var(--subtle); align-self: flex-end; border-radius: 12px 12px 4px 12px; }
        .ai-msg.bot { background: rgba(220,38,38,0.1); border: 1px solid var(--red-border); color: #fca5a5; align-self: flex-start; border-radius: 4px 12px 12px 12px; }

        /* SECTORS */
        .sector-grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
        .sector-pill { padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 600; border: 1px solid var(--border); color: var(--muted); }
        .sector-pill.lit { background: rgba(220,38,38,0.08); border-color: rgba(220,38,38,0.2); color: #f87171; }

        /* ── TABLET (tilted, white screen) ── */
        .hero-right { flex: 1; max-width: 580px; position: relative; display: flex; align-items: center; justify-content: center; }
        .mock-glow { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); width: 320px; height: 320px; background: radial-gradient(circle, rgba(124,58,237,0.05), transparent 70%); filter: blur(80px); pointer-events: none; }
        .tablet-wrap {
          position: relative; z-index: 1;
          transform: perspective(1000px) rotateY(-12deg) rotateX(4deg) rotate(-3deg);
          transform-style: preserve-3d;
          filter: drop-shadow(0 40px 60px rgba(0,0,0,0.7)) drop-shadow(0 0 40px rgba(124,58,237,0.12));
          transition: transform 0.4s ease;
        }
        .tablet-wrap:hover {
          transform: perspective(1000px) rotateY(-8deg) rotateX(2deg) rotate(-2deg);
        }
        .tablet-device { background: #1c1c1e; border-radius: 36px; border: 2px solid #2a2a2a; padding: 18px; width: 442px; }
        .tablet-topbar { display: flex; justify-content: center; padding: 6px 0 10px; }
        .tablet-camera { width: 8px; height: 8px; border-radius: 50%; background: #2a2a2a; }
        /* Screen — muted off-white, not blinding */
        .tablet-screen { background: #f0f0f2; border-radius: 18px; padding: 20px; border: 1px solid rgba(0,0,0,0.10); }
        .ts-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; padding-bottom: 14px; border-bottom: 1px solid #e5e7eb; }
        .ts-header-text { flex: 1; }
        .ts-header-title { font-size: 12px; font-weight: 700; color: #111; }
        .ts-header-sub { font-size: 10px; color: #6b7280; margin-top: 2px; }
        .ts-live-pill { display: flex; align-items: center; gap: 5px; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.3); padding: 4px 10px; border-radius: 20px; font-size: 10px; font-weight: 700; color: #16a34a; }
        .ts-live-dot { width: 5px; height: 5px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
        .ts-timeline { display: flex; flex-direction: column; gap: 14px; }
        .ts-item { display: flex; gap: 10px; align-items: flex-start; }
        .ts-badge { width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; flex-shrink: 0; }
        .ts-badge-green { background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); color: #16a34a; }
        .ts-badge-yellow { background: rgba(234,179,8,0.12); border: 1px solid rgba(234,179,8,0.3); color: #ca8a04; }
        .ts-badge-blue { background: rgba(99,102,241,0.12); border: 1px solid rgba(99,102,241,0.3); color: #4f46e5; }
        .ts-content { flex: 1; }
        .ts-tag { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 3px; }
        .ts-tag-green { color: #16a34a; }
        .ts-tag-yellow { color: #ca8a04; }
        .ts-tag-blue { color: #4f46e5; }
        .ts-title { font-size: 11px; font-weight: 700; color: #111; margin-bottom: 3px; }
        .ts-desc { font-size: 10px; color: #6b7280; line-height: 1.5; }
        .ts-footer { display: flex; align-items: center; margin-top: 16px; padding-top: 14px; border-top: 1px solid #e5e7eb; }
        .ts-stat { flex: 1; text-align: center; }
        .ts-stat-num { display: block; font-family: var(--font-montserrat), 'Montserrat', sans-serif; font-size: 13px; font-weight: 900; color: #111; }
        .ts-stat-label { display: block; font-size: 9px; color: #9ca3af; margin-top: 1px; text-transform: uppercase; letter-spacing: 0.04em; }
        .ts-divider { width: 1px; height: 28px; background: #e5e7eb; }
        .tablet-bottombar { display: flex; justify-content: center; padding: 10px 0 6px; }
        .tablet-home-bar { width: 60px; height: 4px; border-radius: 2px; background: #2a2a2a; }

        /* MOCK SEARCH */
        .mock-search { display: flex; align-items: center; gap: 10px; background: rgba(255,255,255,0.04); border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; margin-top: 16px; }
        .mock-search.active { border-color: rgba(220,38,38,0.4); }
        .search-icon { color: var(--muted); font-size: 14px; }
        .search-text { flex: 1; font-size: 13px; color: var(--subtle); display: flex; align-items: center; gap: 4px; }
        .search-kbd { background: rgba(255,255,255,0.06); border: 1px solid var(--border); border-radius: 5px; padding: 2px 7px; font-size: 11px; color: var(--muted); font-family: monospace; }
        .typed { color: #fff; overflow: hidden; white-space: nowrap; border-right: 2px solid var(--red); }
        @keyframes typing { from { width: 0; } to { width: 100%; } }

        /* CTA SECTION */
        .cta-section { position: relative; z-index: 1; text-align: center; padding: 100px 48px; border-top: 1px solid var(--border); }
        .cta-section h2 { font-family: var(--font-montserrat), 'Montserrat', sans-serif; font-style: normal; font-weight: 800; font-size: clamp(32px, 5vw, 56px); color: #fff; line-height: 1.15; margin-bottom: 40px; }

        /* FOOTER */
        .kbli-footer { position: relative; z-index: 1; border-top: 1px solid var(--border); padding: 28px 48px; display: flex; align-items: center; justify-content: space-between; }
        .footer-left { font-size: 13px; color: var(--muted); }
        .footer-left span { color: var(--subtle); }
        .footer-tagline { font-family: 'Instrument Serif', serif; font-style: italic; font-size: 13px; color: var(--muted); }
      `}</style>

      {/* ── ORNAMENTAL BACKGROUND ── */}
      <div className="bali-bg">
        <div className="bali-pattern" />
        <div className="bali-vignette" />
      </div>
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />

      {/* ── NAV ── */}
      <nav className="kbli-nav" ref={navRef}>
        <Link href="/" className="nav-logo">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/kbli-navigator/lotus-logo.png"
            alt="Zantara"
            width={40}
            height={40}
            style={{ objectFit: "contain", display: "block" }}
          />
        </Link>
        <ul className="nav-links">
          <li>
            <Link href="/kbli">KBLI</Link>
          </li>

          <li>
            <Link href="/knowledge">Knowledge</Link>
          </li>
        </ul>
        {/* Violet Zantara AI pill with real lotus image */}
        <Link
          href="https://kita.balizero.com/chat"
          className="nav-cta"
          target="_blank"
          rel="noopener noreferrer"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/kbli-navigator/lotus-logo.png"
            alt="Zantara"
            width={32}
            height={32}
            className="lotus-icon"
            style={{ objectFit: "contain" }}
          />
          Zantara AI — Your ultimate consultant
        </Link>
      </nav>

      {/* ── HERO ── */}
      <section className="hero">
        <div className="hero-left">
          {/* Logo 2x bigger + tagline bold white */}
          <div className="hero-tagline-top">
            <div className="tagline-logo-wrap">
              <Image
                src="/lotus-logo.png"
                alt="Zantara Lotus"
                width={80}
                height={80}
                style={{
                  objectFit: "contain",
                  display: "block",
                  filter: "drop-shadow(0 0 20px rgba(59,130,246,0.3))",
                }}
                unoptimized
                onError={(e) => {
                  (e.target as HTMLImageElement).style.display = "none";
                }}
              />
            </div>
            <div className="tagline-lines">
              <span className="tagline-line">We don&apos;t sell services.</span>
              <span className="tagline-line">We offer intelligence.</span>
            </div>
          </div>

          <h1 className="hero-h1">
            <span className="kbli-shine">KBLI 2025</span>
          </h1>
          <div className="hero-guide">
            Your <span className="shine-text">Indonesian</span> Business Codes
          </div>
          <p className="hero-sub">
            1,563 codes <span className="sep">·</span> 22 sectors{" "}
            <span className="sep">·</span> PMA rules
          </p>

          <form className="hero-search-form" onSubmit={handleHeroSearch}>
            <span className="hero-search-icon">⌕</span>
            <input
              type="text"
              name="q"
              className="hero-search-input"
              placeholder="Search a sector (e.g. Software, Villa) or code..."
              autoComplete="off"
            />
            <button type="submit" className="hero-search-btn">
              Search
            </button>
          </form>

          <div
            className="hero-ctas"
            style={{ marginTop: "24px", display: "flex", gap: "12px" }}
          >
            <Link href="/kbli" className="cta-primary">
              Explore All KBLI Sectors
            </Link>
          </div>
        </div>

        {/* ── TILTED TABLET with VIDEO ── */}
        <div className="hero-right">
          <div className="mock-glow" />
          <div className="tablet-wrap">
            <div className="tablet-device">
              <div className="tablet-topbar">
                <div className="tablet-camera" />
              </div>
              <div
                className="tablet-screen"
                style={{
                  padding: 0,
                  overflow: "hidden",
                  background: "#000",
                  height: "286px",
                }}
              >
                <video
                  src="/kbli-navigator/kbli-demo-compressed.mp4"
                  autoPlay
                  muted
                  loop
                  playsInline
                  controls
                  style={{
                    width: "100%",
                    height: "100%",
                    display: "block",
                    borderRadius: "18px",
                    objectFit: "cover",
                  }}
                />
              </div>
              <div className="tablet-bottombar">
                <div className="tablet-home-bar" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── TRUST BAR ── */}
      <div className="trust-bar">
        {[
          { num: "1,563", label: "KBLI Codes" },
          { num: "22", label: "Industry Sectors" },
          { num: "100%", label: "PMA Coverage" },
          { num: "AI", label: "Powered by Zantara" },
        ].map((t) => (
          <div className="trust-item" key={t.label}>
            <div className="trust-num">{t.num}</div>
            <div className="trust-label">{t.label}</div>
          </div>
        ))}
      </div>

      {/* ── FEATURES ── */}
      <section className="features">
        <div className="section-tag">Key Features</div>
        <h2 className="section-h2">
          Intelligence, not just
          <br />a directory.
        </h2>
        <p className="section-sub">
          Built for founders, lawyers, and consultants who need precise answers
          — not thousands of pages of regulation.
        </p>
        <div className="bento">
          <div className="bento-card span2 tall reveal">
            <div className="card-icon-lotus">
              <Image
                src="/lotus-logo.png"
                alt="Zantara"
                width={56}
                height={56}
                style={{ objectFit: "contain", display: "block" }}
                unoptimized
              />
            </div>
            <div
              className="card-title"
              style={{ fontSize: "18px", marginTop: "12px" }}
            >
              Zantara AI — Ask Like You&apos;d Ask a Lawyer
            </div>
            <div
              className="card-title"
              style={{
                fontSize: "14px",
                fontWeight: 500,
                color: "var(--subtle)",
                marginBottom: "12px",
              }}
            >
              Your Ultimate Consultant
            </div>
            <div className="card-desc">
              From &quot;I want to open a café in Bali&quot; to the exact KBLI
              code, PMA coverage, and OSS next steps — in plain language,
              instant answers.
            </div>
          </div>
          <div
            className="bento-card reveal"
            style={{ transitionDelay: "0.1s" }}
          >
            <div className="card-icon">⬡</div>
            <div className="card-title">22 Structured Sectors</div>
            <div className="card-desc">
              Hierarchical navigation from Sector A through U.
            </div>
            <div className="sector-grid">
              <div className="sector-pill lit">A · Agriculture</div>
              <div className="sector-pill lit">J · IT &amp; Comms</div>
              <div className="sector-pill lit">I · Tourism</div>
              <div className="sector-pill">C · Manufacturing</div>
              <div className="sector-pill">G · Trade</div>
              <div className="sector-pill">K · Finance</div>
            </div>
          </div>
          <div
            className="bento-card reveal"
            style={{ transitionDelay: "0.15s" }}
          >
            <div className="card-icon">🛡</div>
            <div className="card-title">Real-Time PMA Rules</div>
            <div className="card-desc">
              Foreign ownership percentages, restricted sectors, and minimum
              capital — all in a single code card.
            </div>
          </div>
          <div
            className="bento-card reveal"
            style={{ transitionDelay: "0.2s" }}
          >
            <div className="card-icon">⌘</div>
            <div className="card-title">Semantic Search</div>
            <div className="card-desc">
              Type your business activity in plain language, find the right code
              in milliseconds.
            </div>
            <div className="mock-search active">
              <span className="search-icon">⌕</span>
              <span className="search-text">
                <span className="typed" ref={searchTextRef} />
              </span>
              <span className="search-kbd">↵</span>
            </div>
          </div>
          <div
            className="bento-card reveal"
            style={{ transitionDelay: "0.25s" }}
          >
            <div className="card-icon">📡</div>
            <div className="card-title">Always Up to Date</div>
            <div className="card-desc">
              KBLI 2025 &amp; 2020 side by side. Updates monitored from BKPM
              &amp; OSS.
            </div>
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section className="cta-section">
        <h2>Start navigating Indonesia&apos;s business codes.</h2>
        <Link
          href="/kbli"
          className="cta-primary"
          style={{
            display: "inline-flex",
            fontSize: "16px",
            padding: "16px 48px",
          }}
        >
          Open KBLI Navigator →
        </Link>
      </section>

      {/* ── FOOTER ── */}
      <footer className="kbli-footer">
        <div className="footer-left">
          © 2025 <span>Bali Zero</span> · All data sourced from official
          Indonesian regulations
        </div>
        <div className="footer-tagline">
          We don&apos;t sell services. We offer intelligence.
        </div>
      </footer>
    </>
  );
}
