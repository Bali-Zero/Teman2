import type { Metadata } from "next";
import Script from "next/script";
import { ZantaraWidget } from "@/components/ZantaraWidget";
import { KbliSearchBox } from "./KbliSearchBox";
import { LatestIntelligence } from "./LatestIntelligence";
import { HomepageStaticContent } from "./HomepageStaticContent";

export const metadata: Metadata = {
  title: {
    absolute: "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia",
  },
  description:
    "Indonesia's AI-powered visa agency. KITAS, KITAP, Golden Visa, PT PMA company setup, tax compliance. 24/7 AI assistant. Trusted by 5000+ clients since 2020.",
  alternates: {
    canonical: "https://balizero.com",
  },
  openGraph: {
    title: "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia",
    description:
      "Indonesia's AI-powered visa agency. KITAS, KITAP, Golden Visa, PT PMA company setup, tax compliance. 24/7 AI assistant. Trusted by 5000+ clients.",
    url: "https://balizero.com",
  },
};

export const revalidate = 3600;

export default function HomePage() {
  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap"
        rel="stylesheet"
      />
      <style
        suppressHydrationWarning
        dangerouslySetInnerHTML={{
          __html: `:root {
  --navy: #060D14;
  --navy2: #0A1520;
  --gold: #D4A853;
  --blue: #2E6FD4;
  --blue-light: #4a87e8;
  --cream: #F2EDE6;
  --w55: rgba(242,237,230,0.55);
  --w35: rgba(242,237,230,0.35);
  --w15: rgba(242,237,230,0.15);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--navy);
  color: var(--cream);
  font-family: 'Inter', sans-serif;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}
em { font-style: italic; color: var(--gold); }

/* ══════════════════════════════════════════
   NAVBAR
══════════════════════════════════════════ */
nav {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 32px; height: 62px;
  background: rgba(6,13,20,0.75);
  backdrop-filter: blur(18px);
  border-bottom: 1px solid rgba(255,255,255,0.04);
}
.logo-wrap { display: flex; align-items: center; text-decoration: none; }
.logo-img { width: 92px; height: 92px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.nav-links { display: flex; align-items: center; gap: 28px; }
.nav-dropdown { position: relative; }
.nav-drop-trigger {
  display: flex; align-items: center; gap: 4px;
  font-size: 13px; font-weight: 400; color: var(--w55);
  text-decoration: none; text-transform: none; letter-spacing: 0;
  cursor: pointer; transition: color 0.2s;
}
.nav-drop-trigger:hover { color: var(--cream); }
.nav-arrow { font-size: 9px; opacity: 0.6; }
.nav-dropdown-menu {
  display: none; position: absolute; top: calc(100% + 14px); left: 0;
  background: rgba(6,13,20,0.97); backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;
  padding: 8px 0; min-width: 180px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.5); z-index: 200;
}
.nav-dropdown:hover .nav-dropdown-menu { display: block; }
.nav-dropdown-menu a {
  display: block; padding: 9px 16px;
  color: var(--w55); font-size: 13px; text-decoration: none;
  text-transform: none; letter-spacing: 0;
  transition: color 0.15s, background 0.15s;
}
.nav-dropdown-menu a:hover { color: var(--cream); background: rgba(255,255,255,0.04); }
.nav-simple {
  font-size: 13px; color: var(--w55); text-decoration: none;
  transition: color 0.2s;
}
.nav-simple:hover { color: var(--cream); }
.nav-divider { width: 1px; height: 20px; background: rgba(255,255,255,0.1); }
.nav-icon-btn {
  background: none; border: none; cursor: pointer;
  color: var(--w55); font-size: 13px; padding: 4px;
  transition: color 0.2s; display: flex; align-items: center;
}
.nav-icon-btn:hover { color: var(--cream); }
.nav-cmd {
  font-size: 11px; letter-spacing: 0.02em;
  border: 1px solid rgba(255,255,255,0.12) !important;
  border-radius: 5px; padding: 3px 8px;
}
.nav-lang {
  background: none; border: 1px solid rgba(255,255,255,0.12);
  border-radius: 5px; padding: 3px 10px;
  color: var(--w55); font-size: 12px; cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.nav-lang:hover { border-color: rgba(255,255,255,0.3); color: var(--cream); }
.btn-consult {
  background: transparent; border: 1px solid var(--gold);
  color: var(--gold); padding: 7px 18px; border-radius: 4px;
  font-size: 11px; font-weight: 600; letter-spacing: 0.08em;
  text-transform: uppercase; cursor: pointer; transition: all 0.2s;
}
.btn-consult:hover { background: var(--gold); color: var(--navy); }

/* ══════════════════════════════════════════
   BRAND ENTRANCE
══════════════════════════════════════════ */
.brand-entrance {
  margin-top: 62px;
  border-bottom: 1px solid rgba(212,168,83,0.15);
  background: var(--navy);
  position: relative;
}
.brand-inner {
  max-width: 1400px; margin: 0 auto;
  padding: 0 60px;
  height: 80px;
  display: flex; align-items: center; justify-content: space-between;
}
.brand-left {
  display: flex; align-items: center; gap: 16px;
}
.brand-text { display: flex; flex-direction: column; gap: 5px; }
.brand-tagline {
  font-family: "Arial Black", "Impact", "Franklin Gothic Heavy", sans-serif;
  font-weight: 900;
  font-style: normal;
  font-size: 32px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #fff;
  line-height: 1;
  margin: 0;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.4);
}
.brand-logo-3-img {
  display: inline-block;
  vertical-align: middle;
  height: 1.2em;
  width: auto;
  margin-top: -0.35em;
  margin-right: -0.02em;
  object-fit: contain;
  filter: drop-shadow(0 3px 6px rgba(0,0,0,0.5));
}
.brand-om-circle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 0.85em;
  height: 0.85em;
  background: #fff;
  border-radius: 50%;
  position: relative;
  flex-shrink: 0;
  vertical-align: middle;
  margin-top: 0.15em;
}
.brand-om-circle::after {
  content: "ॐ";
  font-size: 0.55em;
  font-family: serif;
  color: #111;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
}
.brand-sub {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px; letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--w35); margin: 0;
}
.brand-right {
  display: flex; align-items: center; gap: 8px;
}
.brand-stat {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px; font-weight: 500;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--w35);
}
.brand-stat-sep {
  font-size: 8px; color: rgba(212,168,83,0.4);
}
@media (max-width: 768px) {
  .brand-inner { padding: 0 20px; height: 80px; }
  .brand-tagline { font-size: 22px; }
  .brand-right { display: none; }
}

/* ══════════════════════════════════════════
   CAROUSEL HERO
══════════════════════════════════════════ */
.hero-carousel {
  position: relative; height: 100vh; overflow: hidden;
  background: var(--navy);
}
.slide {
  position: absolute; inset: 0;
  opacity: 0; transition: opacity 0.1s;
  pointer-events: none;
}
.slide.active { opacity: 1; pointer-events: auto; }
.slide.leaving {
  animation: dustAway 0.85s cubic-bezier(0.4,0,0.2,1) forwards;
}
.slide.entering {
  animation: dustIn 0.85s cubic-bezier(0.4,0,0.2,1) forwards;
  opacity: 1; pointer-events: auto;
}
@keyframes dustAway {
  0%   { opacity:1; clip-path: polygon(0 0,100% 0,100% 100%,0 100%); }
  30%  { clip-path: polygon(0 0,100% 0,100% 100%,8% 100%); }
  60%  { clip-path: polygon(0 0,100% 0,100% 60%,30% 100%); }
  100% { opacity:0; clip-path: polygon(100% 0,100% 0,100% 0,100% 0); }
}
@keyframes dustIn {
  0%   { opacity:0; clip-path: polygon(100% 0,100% 0,100% 100%,100% 100%); }
  40%  { clip-path: polygon(20% 0,100% 0,100% 100%,0 100%); }
  70%  { clip-path: polygon(0 0,100% 0,100% 100%,0 100%); }
  100% { opacity:1; clip-path: polygon(0 0,100% 0,100% 100%,0 100%); }
}
.slide-bg {
  position: absolute; inset: 0; width: 100%; height: 100%;
  object-fit: cover;
  animation: kenburns 14s ease-in-out infinite alternate;
}
@keyframes kenburns {
  from { transform: scale(1.0) translate(0,0); }
  to   { transform: scale(1.07) translate(-1%,-0.5%); }
}
.slide-grain {
  position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
  opacity: 0.5; pointer-events: none;
}
.slide-leak {
  position: absolute; top: -40%; left: -20%;
  width: 70%; height: 80%;
  background: radial-gradient(ellipse, rgba(212,168,83,0.06) 0%, transparent 70%);
  pointer-events: none;
}
.slide-leak2 {
  position: absolute; bottom: -20%; right: -10%;
  width: 50%; height: 60%;
  background: radial-gradient(ellipse, rgba(46,111,212,0.08) 0%, transparent 70%);
  pointer-events: none;
}
.slide-grad {
  position: absolute; inset: 0;
  background: linear-gradient(
    to right,
    rgba(6,13,20,0.88) 0%,
    rgba(6,13,20,0.65) 45%,
    rgba(6,13,20,0.20) 70%,
    rgba(6,13,20,0.45) 100%
  );
}
.slide-content {
  position: absolute; inset: 0;
  display: flex; align-items: flex-end;
  padding: 0 60px 80px;
  gap: 60px;
}
.slide-left { flex: 1; max-width: 620px; }
.slide-kicker {
  display: flex; align-items: center; gap: 10px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; letter-spacing: 0.12em; color: var(--gold);
  margin-bottom: 20px;
}
.kicker-line { display: block; width: 32px; height: 1px; background: var(--gold); }
.kicker-dot { opacity: 0.4; }
.slide-headline {
  font-family: 'DM Serif Display', serif;
  font-size: clamp(32px, 4vw, 58px);
  line-height: 1.08;
  color: var(--cream);
  margin-bottom: 20px;
}
.slide-deck {
  font-size: 15px; color: var(--w55);
  line-height: 1.65; margin-bottom: 32px;
  max-width: 500px;
}
.slide-actions { display: flex; align-items: center; gap: 24px; }
.btn-read {
  display: inline-block;
  background: var(--gold); color: var(--navy);
  padding: 12px 28px; border-radius: 3px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; text-decoration: none;
  transition: opacity 0.2s;
}
.btn-read:hover { opacity: 0.85; }
.slide-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px; color: var(--w35); letter-spacing: 0.05em;
}
.slide-strip {
  width: 340px; flex-shrink: 0;
  display: flex; flex-direction: column; gap: 0;
}
.strip-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; letter-spacing: 0.14em;
  color: var(--w35); text-transform: uppercase;
  margin-bottom: 16px;
}
.strip-item {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 14px 0;
  border-top: 1px solid rgba(255,255,255,0.06);
  cursor: pointer; transition: opacity 0.2s;
}
.strip-item:hover { opacity: 0.75; }
.strip-num {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; color: var(--gold); flex-shrink: 0; margin-top: 2px;
}
.strip-meta { display: flex; flex-direction: column; gap: 4px; }
.strip-kicker {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; letter-spacing: 0.1em;
  color: var(--w35); text-transform: uppercase;
}
.strip-title-s { font-size: 13px; color: var(--cream); line-height: 1.4; }

/* Carousel dots */
.carousel-dots {
  position: absolute; bottom: 32px; left: 60px;
  display: flex; gap: 8px; z-index: 10;
}
.dot {
  width: 28px; height: 3px; border-radius: 2px;
  background: rgba(255,255,255,0.2);
  cursor: pointer; transition: background 0.3s, width 0.3s;
}
.dot.active { background: var(--gold); width: 44px; }

/* ══════════════════════════════════════════
   CONTENT AREA
══════════════════════════════════════════ */
.content-area { background: var(--navy); }

/* Topic pills */
.topics-strip {
  border-bottom: 1px solid rgba(255,255,255,0.06);
  padding: 20px 60px;
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.topic-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; letter-spacing: 0.12em;
  color: var(--w35); text-transform: uppercase;
  margin-right: 6px; flex-shrink: 0;
}
.topic-pill {
  padding: 6px 16px; border-radius: 50px;
  border: 1px solid rgba(255,255,255,0.12);
  font-size: 12px; color: var(--w55); cursor: pointer;
  text-decoration: none;
  transition: all 0.2s;
}
.topic-pill:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.3);
  color: var(--cream);
}

/* ══════════════════════════════════════════
   LATEST INTELLIGENCE (Liquid Glassmorphism)
══════════════════════════════════════════ */
.glass-section {
  padding: 80px 60px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  background: linear-gradient(180deg, rgba(10,21,32,0.0) 0%, rgba(10,21,32,0.3) 100%);
}
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 40px;
}
.section-title {
  font-family: 'DM Serif Display', serif;
  font-size: 28px; color: var(--cream);
}
.section-link {
  font-size: 13px; color: var(--blue-light); text-decoration: none;
  display: flex; align-items: center; gap: 6px;
  transition: color 0.2s;
}
.section-link:hover { color: #90c0ff; }
.li-grid {
  display: grid;
  grid-template-columns: 1.6fr 1.1fr 0.9fr;
  grid-template-rows: 200px 160px 180px;
  gap: 12px;
}
.li-card {
  position: relative; overflow: hidden; border-radius: 12px;
  text-decoration: none; display: block;
  border: 1px solid rgba(255,255,255,0.06);
  transition: transform 0.3s, border-color 0.3s;
}
.li-card:hover { transform: translateY(-3px); border-color: rgba(255,255,255,0.15); }
.li-card:nth-child(1) { grid-column:1/2; grid-row:1/4; }
.li-card:nth-child(2) { grid-column:2/3; grid-row:1/3; }
.li-card:nth-child(3) { grid-column:3/4; grid-row:1/2; }
.li-card:nth-child(4) { grid-column:2/4; grid-row:3/4; }
.li-card:nth-child(5) { grid-column:3/4; grid-row:2/3; }
.li-img-wrap { position: absolute; inset: 0; overflow: hidden; }
.li-img-wrap img { width:100%; height:100%; object-fit:cover; transition: transform 0.6s; }
.li-card:hover .li-img-wrap img { transform: scale(1.04); }
.li-img-grad {
  position: absolute; inset: 0;
  background: linear-gradient(to top, rgba(6,13,20,0.92) 0%, rgba(6,13,20,0.3) 50%, transparent 100%);
}
.li-body {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 20px; z-index: 2;
}
.li-badge {
  position: absolute; top: 16px; left: 16px;
  font-size: 9px; font-weight: 700; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--cream);
  background: rgba(46,111,212,0.7); backdrop-filter: blur(8px);
  padding: 4px 10px; border-radius: 3px;
}
.li-cat {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--blue-light); display: block; margin-bottom: 6px;
}
.li-title {
  font-family: 'DM Serif Display', serif;
  color: var(--cream); line-height: 1.3;
  overflow: hidden; display: -webkit-box;
  -webkit-line-clamp: 3; -webkit-box-orient: vertical;
}
.li-card:nth-child(1) .li-title { font-size: 22px; }
.li-card:nth-child(2) .li-title { font-size: 17px; -webkit-line-clamp: 2; }
.li-card:nth-child(3) .li-title { font-size: 15px; -webkit-line-clamp: 2; }
.li-card:nth-child(4) .li-title { font-size: 16px; -webkit-line-clamp: 2; }
.li-card:nth-child(5) .li-title { font-size: 15px; -webkit-line-clamp: 2; }
.li-desc { font-size: 13px; color: rgba(242,237,230,0.55); line-height: 1.5; margin-top: 6px; }
.li-meta {
  font-size: 11px; color: var(--w35); margin-top: 6px; display: block;
}

/* Glass overlays per card */
.li-card:nth-child(1) .li-img-grad {
  background: linear-gradient(to top, rgba(6,13,20,0.95) 0%, rgba(6,13,20,0.2) 60%, transparent 100%);
}
.li-card:nth-child(2) .li-img-wrap::after {
  content:''; position:absolute; inset:0;
  backdrop-filter: blur(1px);
  background: rgba(212,168,83,0.04);
}
.li-card:nth-child(3) .li-img-wrap::after {
  content:''; position:absolute; inset:0;
  backdrop-filter: blur(3px);
  background: rgba(46,111,212,0.12);
  box-shadow: inset 0 0 30px rgba(46,111,212,0.15);
}
.li-card:nth-child(5) .li-img-wrap::after {
  content:''; position:absolute; inset:0;
  backdrop-filter: blur(6px);
  background: rgba(10,21,32,0.2);
}

/* ══════════════════════════════════════════
   KBLI SECTION
══════════════════════════════════════════ */
.kbli-section {
  display: grid; grid-template-columns: 1fr 1fr;
  min-height: 440px;
  border-top: 1px solid rgba(255,255,255,0.05);
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.kbli-left {
  padding: 70px 60px;
  background: linear-gradient(135deg, rgba(10,21,32,0.8) 0%, rgba(6,13,20,0.9) 100%);
  display: flex; flex-direction: column; justify-content: center;
  position: relative; overflow: hidden;
}
.kbli-left::before {
  content: ''; position: absolute; top: -50%; left: -20%;
  width: 80%; height: 140%;
  background: radial-gradient(ellipse, rgba(46,111,212,0.12) 0%, transparent 70%);
}
.kbli-badge {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; letter-spacing: 0.15em; color: var(--blue-light);
  text-transform: uppercase; margin-bottom: 16px;
}
.kbli-title {
  font-family: 'DM Serif Display', serif;
  font-size: 42px; line-height: 1.1;
  color: var(--cream); margin-bottom: 16px;
}
.kbli-desc {
  font-size: 15px; color: var(--w55);
  line-height: 1.65; margin-bottom: 32px; max-width: 420px;
}
.kbli-features {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 32px;
}
.kbli-feat {
  font-size: 11px; color: var(--w55);
  border: 1px solid rgba(255,255,255,0.1);
  padding: 4px 12px; border-radius: 3px;
}
.kbli-btn {
  display: inline-flex; align-items: center; gap: 10px;
  background: var(--blue); color: #fff;
  padding: 13px 28px; border-radius: 5px;
  font-size: 13px; font-weight: 600; text-decoration: none;
  border: none; cursor: pointer;
  transition: background 0.2s; align-self: flex-start;
}
.kbli-btn:hover { background: var(--blue-light); }
.kbli-right {
  background: rgba(10,21,32,0.5);
  display: flex; align-items: center; justify-content: center;
  padding: 40px;
  position: relative;
}
.kbli-search-box {
  width: 100%; max-width: 420px;
}
.kbli-search-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px; letter-spacing: 0.12em;
  color: var(--w35); text-transform: uppercase;
  margin-bottom: 12px; display: block;
}
.kbli-input {
  width: 100%; padding: 14px 18px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 8px; color: var(--cream);
  font-size: 14px; font-family: inherit;
  outline: none; transition: border-color 0.2s;
}
.kbli-input::placeholder { color: var(--w35); }
.kbli-input:focus { border-color: var(--blue); }
.kbli-tags {
  display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap;
}
.kbli-tag {
  font-size: 11px; padding: 4px 10px; border-radius: 20px;
  background: rgba(46,111,212,0.12);
  border: 1px solid rgba(46,111,212,0.2);
  color: var(--blue-light); cursor: pointer; transition: background 0.2s;
}
.kbli-tag:hover { background: rgba(46,111,212,0.2); }

/* ══════════════════════════════════════════
   SERVICES
══════════════════════════════════════════ */
.services-section {
  padding: 80px 60px;
  border-top: 1px solid rgba(255,255,255,0.06);
  background: rgba(3,8,14,0.5);
}
.services-top {
  display: flex; align-items: flex-end; justify-content: space-between;
  margin-bottom: 48px;
}
.services-title {
  font-family: 'DM Serif Display', serif;
  font-size: 32px; color: var(--cream); margin-bottom: 8px;
}
.services-sub { font-size: 14px; color: var(--w55); }
.services-view { font-size: 13px; color: var(--blue-light); text-decoration: none; }
.services-view:hover { color: #90c0ff; }
.services-grid {
  display: grid; grid-template-columns: repeat(4,1fr); gap: 16px;
}
.service-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px; padding: 28px 24px;
  transition: background 0.2s, border-color 0.2s, transform 0.2s;
}
.service-card:hover {
  background: rgba(255,255,255,0.06);
  border-color: rgba(255,255,255,0.12);
  transform: translateY(-3px);
}
.service-icon {
  width: 44px; height: 44px; border-radius: 10px;
  background: rgba(46,111,212,0.12); border: 1px solid rgba(46,111,212,0.2);
  display: flex; align-items: center; justify-content: center;
  color: var(--blue-light); margin-bottom: 18px;
}
.service-name {
  font-family: 'DM Serif Display', serif;
  font-size: 18px; color: var(--cream); margin-bottom: 8px;
}
.service-desc { font-size: 13px; color: var(--w55); line-height: 1.55; }

/* ══════════════════════════════════════════
   FOOTER
══════════════════════════════════════════ */
.site-footer {
  background: rgba(3,6,10,0.95);
  border-top: 1px solid rgba(255,255,255,0.06);
  padding: 60px 60px 32px;
}
.footer-top {
  display: grid; grid-template-columns: 1.4fr 1fr 1fr 1fr;
  gap: 48px; margin-bottom: 48px;
}
.footer-brand { display: flex; flex-direction: column; gap: 14px; }
.footer-logo-wrap { display: flex; align-items: center; gap: 12px; }
.footer-logo-img { width: 72px; height: 72px; border-radius: 50%; object-fit: cover; }
.footer-logo-text {
  font-family: 'DM Serif Display', serif;
  font-size: 16px; color: var(--cream);
}
.footer-logo-text em { color: var(--gold); font-style: normal; }
.footer-desc { font-size: 13px; color: var(--w35); line-height: 1.6; max-width: 240px; }
.footer-col h4 {
  font-size: 11px; font-weight: 600; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--w55); margin-bottom: 16px;
}
.footer-col a {
  display: block; font-size: 13px; color: var(--w35);
  text-decoration: none; margin-bottom: 10px; transition: color 0.2s;
}
.footer-col a:hover { color: var(--cream); }
.footer-bottom {
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: 24px;
  display: flex; align-items: center; justify-content: space-between;
}
.footer-copy { font-size: 12px; color: var(--w35); }
.footer-links { display: flex; gap: 20px; }
.footer-links a { font-size: 12px; color: var(--w35); text-decoration: none; transition: color 0.2s; }
.footer-links a:hover { color: var(--cream); }

/* ══════════════════════════════════════════
   ASK ZANTARA FAB
══════════════════════════════════════════ */
.ask-zantara-fab {
  position: fixed; bottom: 24px; right: 24px; z-index: 999;
  display: flex; align-items: center; gap: 8px;
  background: var(--blue); color: #fff;
  border: none; border-radius: 50px; padding: 12px 20px;
  font-size: 14px; font-weight: 600; cursor: pointer;
  box-shadow: 0 8px 32px rgba(46,111,212,0.4);
  transition: transform 0.2s, box-shadow 0.2s;
  font-family: 'Inter', sans-serif;
}
.ask-zantara-fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 44px rgba(46,111,212,0.55);
}
.fab-icon { font-size: 18px; }

/* Spotlight cursor effect */
body::after {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background: radial-gradient(
    600px circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
    rgba(46,111,212,0.04) 0%,
    transparent 70%
  );
}
`,
        }}
      />
      <HomepageStaticContent
        html={`
<!-- ════════ NAVBAR ════════ -->
<nav>
  <a class="logo-wrap" href="/">
    <img class="logo-img" src="/static/homepage/bali-zero-logo.png" alt="Bali Zero logo">
  </a>
  <div class="nav-links">
    <div class="nav-dropdown">
      <a class="nav-drop-trigger" href="/news">News <span class="nav-arrow">↓</span></a>
      <div class="nav-dropdown-menu">
        <a href="/news?category=visas">Visas</a>
        <a href="/news?category=business">Business</a>
        <a href="/news?category=taxes">Taxes</a>
        <a href="/news?category=property">Property</a>
        <a href="/news">All Intelligence</a>
      </div>
    </div>
    <div class="nav-dropdown">
      <a class="nav-drop-trigger" href="/services">Services <span class="nav-arrow">↓</span></a>
      <div class="nav-dropdown-menu">
        <a href="/services#visa">Visa &amp; Immigration</a>
        <a href="/services#company">Company Setup</a>
        <a href="/services#tax">Tax &amp; Compliance</a>
        <a href="/services#property">Property</a>
      </div>
    </div>
    <a class="nav-simple" href="/team">Team</a>
    <a class="nav-simple" href="/contact">Contact</a>
    <div class="nav-divider"></div>
    <a class="nav-simple" href="/kbli" style="font-size:11px;letter-spacing:0.05em;color:var(--blue-light);">KBLI</a>
    <a class="btn-consult" href="/contact">Consultation</a>
  </div>
</nav>

<!-- ════════ BRAND ENTRANCE ════════ -->
<div class="brand-entrance">
  <div class="brand-inner">
    <div class="brand-left">
      <div class="brand-text">
        <h2 class="brand-tagline">Your <img class="brand-logo-3-img" src="/assets/logo/balizero-3-red.png" alt="B" width="600" height="660"/>ali, from Zer<span class="brand-om-circle"></span></h2>
        <p class="brand-sub">Visa · Company · Tax · Property · Intelligence</p>
      </div>
    </div>
    <div class="brand-right">
      <span class="brand-stat">5,000+ clients</span>
      <span class="brand-stat-sep">·</span>
      <span class="brand-stat">Since 2020</span>
      <span class="brand-stat-sep">·</span>
      <span class="brand-stat">Bali, Indonesia</span>
    </div>
  </div>
</div>

<!-- ════════ HERO CAROUSEL ════════ -->
<div id="carousel" class="hero-carousel">

    <div class="slide active" data-index="0">
      <img class="slide-bg" src="/static/homepage/bali-defies-global-headwinds-with-70-occupancy-and-rising-fo.jpg" alt="Bali Defies Global Headwinds with 70% Occupancy and Rising Foreign Investment">
      <div class="slide-grain"></div>
      <div class="slide-leak"></div>
      <div class="slide-leak2"></div>
      <div class="slide-grad"></div>
      <div class="slide-content">
        <div class="slide-left">
          <div class="slide-kicker">
            <span class="kicker-line"></span>
            <span>FDI · INVESTMENT</span>
            <span class="kicker-dot">·</span>
            <span>Apr 2, 2026</span>
          </div>
          <h1 class="slide-headline">Bali Defies Global Headwinds with 70% Occupancy and <em>Rising</em> Foreign Investment</h1>
          <p class="slide-deck">Foreign capital inflows reach a post-pandemic peak as institutional investors pivot from Southeast Asian competitors to Bali's proven asset classes.</p>
          <div class="slide-actions">
            <a href="/news/bali-defies-global-headwinds-with-70-occupancy-and-rising-foreign-investment" class="btn-read">READ STORY</a>
            <span class="slide-num">01 / 05</span>
          </div>
        </div>
        <div class="slide-strip">
          <p class="strip-label">ALSO IN TODAY'S EDITION</p>
          
              <div class="strip-item" onclick="goTo(1)">
                <span class="strip-num">02</span>
                <div class="strip-meta">
                  <span class="strip-kicker">REGULATION · STR</span>
                  <span class="strip-title-s">Bali's 2026 Short-Term Rental Rules: What Owners Must D...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(2)">
                <span class="strip-num">03</span>
                <div class="strip-meta">
                  <span class="strip-kicker">TAX 2026 · EXPATS</span>
                  <span class="strip-title-s">Indonesia Tax for Expats: Who Owes What in 2026</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(3)">
                <span class="strip-num">04</span>
                <div class="strip-meta">
                  <span class="strip-kicker">GOLDEN VISA</span>
                  <span class="strip-title-s">Indonesia's Golden Visa: What the 2026 Rules Mean for H...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(4)">
                <span class="strip-num">05</span>
                <div class="strip-meta">
                  <span class="strip-kicker">BUSINESS CLIMATE</span>
                  <span class="strip-title-s">Bali Business Climate 2026: What Foreigners Actually Fa...</span>
                </div>
              </div>
        </div>
      </div>
    </div>

    <div class="slide " data-index="1">
      <img class="slide-bg" src="/static/homepage/balis-2026-short-term-rental-rules-what-owners-must-do-now.jpg" alt="Bali's 2026 Short-Term Rental Rules: What Owners Must Do Now">
      <div class="slide-grain"></div>
      <div class="slide-leak"></div>
      <div class="slide-leak2"></div>
      <div class="slide-grad"></div>
      <div class="slide-content">
        <div class="slide-left">
          <div class="slide-kicker">
            <span class="kicker-line"></span>
            <span>REGULATION · STR</span>
            <span class="kicker-dot">·</span>
            <span>Apr 2, 2026</span>
          </div>
          <h1 class="slide-headline">Bali's 2026 Short-Term Rental Rules: <em>What Owners</em> Must Do Now</h1>
          <p class="slide-deck">New licensing frameworks, occupancy caps, and environmental levies reshape the short-term rental market.</p>
          <div class="slide-actions">
            <a href="/news/balis-2026-short-term-rental-rules-what-owners-must-do-now" class="btn-read">READ STORY</a>
            <span class="slide-num">02 / 05</span>
          </div>
        </div>
        <div class="slide-strip">
          <p class="strip-label">ALSO IN TODAY'S EDITION</p>
          
              <div class="strip-item" onclick="goTo(0)">
                <span class="strip-num">01</span>
                <div class="strip-meta">
                  <span class="strip-kicker">FDI · INVESTMENT</span>
                  <span class="strip-title-s">Bali Defies Global Headwinds with 70% Occupancy and Ris...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(2)">
                <span class="strip-num">03</span>
                <div class="strip-meta">
                  <span class="strip-kicker">TAX 2026 · EXPATS</span>
                  <span class="strip-title-s">Indonesia Tax for Expats: Who Owes What in 2026</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(3)">
                <span class="strip-num">04</span>
                <div class="strip-meta">
                  <span class="strip-kicker">GOLDEN VISA</span>
                  <span class="strip-title-s">Indonesia's Golden Visa: What the 2026 Rules Mean for H...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(4)">
                <span class="strip-num">05</span>
                <div class="strip-meta">
                  <span class="strip-kicker">BUSINESS CLIMATE</span>
                  <span class="strip-title-s">Bali Business Climate 2026: What Foreigners Actually Fa...</span>
                </div>
              </div>
        </div>
      </div>
    </div>

    <div class="slide " data-index="2">
      <img class="slide-bg" src="/static/homepage/indonesia-tax-for-expats-who-owes-what-in-2026.jpg" alt="Indonesia Tax for Expats: Who Owes What in 2026">
      <div class="slide-grain"></div>
      <div class="slide-leak"></div>
      <div class="slide-leak2"></div>
      <div class="slide-grad"></div>
      <div class="slide-content">
        <div class="slide-left">
          <div class="slide-kicker">
            <span class="kicker-line"></span>
            <span>TAX 2026 · EXPATS</span>
            <span class="kicker-dot">·</span>
            <span>Apr 2, 2026</span>
          </div>
          <h1 class="slide-headline">Indonesia Tax for Expats: <em>Who Owes</em> What in 2026</h1>
          <p class="slide-deck">The new DGT guidelines clarify residency triggers, worldwide income rules, and the 183-day threshold.</p>
          <div class="slide-actions">
            <a href="/news/indonesia-tax-for-expats-who-owes-what-in-2026" class="btn-read">READ STORY</a>
            <span class="slide-num">03 / 05</span>
          </div>
        </div>
        <div class="slide-strip">
          <p class="strip-label">ALSO IN TODAY'S EDITION</p>
          
              <div class="strip-item" onclick="goTo(0)">
                <span class="strip-num">01</span>
                <div class="strip-meta">
                  <span class="strip-kicker">FDI · INVESTMENT</span>
                  <span class="strip-title-s">Bali Defies Global Headwinds with 70% Occupancy and Ris...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(1)">
                <span class="strip-num">02</span>
                <div class="strip-meta">
                  <span class="strip-kicker">REGULATION · STR</span>
                  <span class="strip-title-s">Bali's 2026 Short-Term Rental Rules: What Owners Must D...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(3)">
                <span class="strip-num">04</span>
                <div class="strip-meta">
                  <span class="strip-kicker">GOLDEN VISA</span>
                  <span class="strip-title-s">Indonesia's Golden Visa: What the 2026 Rules Mean for H...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(4)">
                <span class="strip-num">05</span>
                <div class="strip-meta">
                  <span class="strip-kicker">BUSINESS CLIMATE</span>
                  <span class="strip-title-s">Bali Business Climate 2026: What Foreigners Actually Fa...</span>
                </div>
              </div>
        </div>
      </div>
    </div>

    <div class="slide " data-index="3">
      <img class="slide-bg" src="/static/homepage/indonesias-golden-visa-what-the-2026-rules-mean-for-hnw-inve.jpg" alt="Indonesia's Golden Visa: What the 2026 Rules Mean for HNW Investors">
      <div class="slide-grain"></div>
      <div class="slide-leak"></div>
      <div class="slide-leak2"></div>
      <div class="slide-grad"></div>
      <div class="slide-content">
        <div class="slide-left">
          <div class="slide-kicker">
            <span class="kicker-line"></span>
            <span>GOLDEN VISA · HNW</span>
            <span class="kicker-dot">·</span>
            <span>Apr 2, 2026</span>
          </div>
          <h1 class="slide-headline">Indonesia's Golden Visa: <em>What the 2026 Rules</em> Mean for HNW Investors</h1>
          <p class="slide-deck">Updated capital thresholds, asset class eligibility, and new fast-track processing reshape Indonesia's premium residency program.</p>
          <div class="slide-actions">
            <a href="/news/indonesias-golden-visa-what-the-2026-rules-mean-for-high-net-worth-investors" class="btn-read">READ STORY</a>
            <span class="slide-num">04 / 05</span>
          </div>
        </div>
        <div class="slide-strip">
          <p class="strip-label">ALSO IN TODAY'S EDITION</p>
          
              <div class="strip-item" onclick="goTo(0)">
                <span class="strip-num">01</span>
                <div class="strip-meta">
                  <span class="strip-kicker">FDI · INVESTMENT</span>
                  <span class="strip-title-s">Bali Defies Global Headwinds with 70% Occupancy and Ris...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(1)">
                <span class="strip-num">02</span>
                <div class="strip-meta">
                  <span class="strip-kicker">REGULATION · STR</span>
                  <span class="strip-title-s">Bali's 2026 Short-Term Rental Rules: What Owners Must D...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(2)">
                <span class="strip-num">03</span>
                <div class="strip-meta">
                  <span class="strip-kicker">TAX 2026 · EXPATS</span>
                  <span class="strip-title-s">Indonesia Tax for Expats: Who Owes What in 2026</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(4)">
                <span class="strip-num">05</span>
                <div class="strip-meta">
                  <span class="strip-kicker">BUSINESS CLIMATE</span>
                  <span class="strip-title-s">Bali Business Climate 2026: What Foreigners Actually Fa...</span>
                </div>
              </div>
        </div>
      </div>
    </div>

    <div class="slide " data-index="4">
      <img class="slide-bg" src="/static/homepage/bali-business-climate-2026-what-foreigners-actually-face.jpg" alt="Bali Business Climate 2026: What Foreigners Actually Face">
      <div class="slide-grain"></div>
      <div class="slide-leak"></div>
      <div class="slide-leak2"></div>
      <div class="slide-grad"></div>
      <div class="slide-content">
        <div class="slide-left">
          <div class="slide-kicker">
            <span class="kicker-line"></span>
            <span>BUSINESS · CLIMATE</span>
            <span class="kicker-dot">·</span>
            <span>Apr 2, 2026</span>
          </div>
          <h1 class="slide-headline">Bali Business Climate 2026: <em>What Foreigners</em> Actually Face</h1>
          <p class="slide-deck">Bureaucratic friction, cultural complexity, and regulatory opacity versus real returns.</p>
          <div class="slide-actions">
            <a href="/news/bali-business-climate-2026-what-foreigners-actually-face" class="btn-read">READ STORY</a>
            <span class="slide-num">05 / 05</span>
          </div>
        </div>
        <div class="slide-strip">
          <p class="strip-label">ALSO IN TODAY'S EDITION</p>
          
              <div class="strip-item" onclick="goTo(0)">
                <span class="strip-num">01</span>
                <div class="strip-meta">
                  <span class="strip-kicker">FDI · INVESTMENT</span>
                  <span class="strip-title-s">Bali Defies Global Headwinds with 70% Occupancy and Ris...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(1)">
                <span class="strip-num">02</span>
                <div class="strip-meta">
                  <span class="strip-kicker">REGULATION · STR</span>
                  <span class="strip-title-s">Bali's 2026 Short-Term Rental Rules: What Owners Must D...</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(2)">
                <span class="strip-num">03</span>
                <div class="strip-meta">
                  <span class="strip-kicker">TAX 2026 · EXPATS</span>
                  <span class="strip-title-s">Indonesia Tax for Expats: Who Owes What in 2026</span>
                </div>
              </div>
              <div class="strip-item" onclick="goTo(3)">
                <span class="strip-num">04</span>
                <div class="strip-meta">
                  <span class="strip-kicker">GOLDEN VISA</span>
                  <span class="strip-title-s">Indonesia's Golden Visa: What the 2026 Rules Mean for H...</span>
                </div>
              </div>
        </div>
      </div>
    </div>
  <div class="carousel-dots">
    <div class="dot active" onclick="goTo(0)"></div>
    <div class="dot" onclick="goTo(1)"></div>
    <div class="dot" onclick="goTo(2)"></div>
    <div class="dot" onclick="goTo(3)"></div>
    <div class="dot" onclick="goTo(4)"></div>
  </div>
</div>

<!-- ════════ CONTENT AREA ════════ -->
<div class="content-area">

  <!-- Topic Pills -->
  <div class="topics-strip">
    <span class="topic-label">Latest</span>
    <a href="/news?category=trends" class="topic-pill">AI &amp; Tech</a>
    <a href="/news?category=visas" class="topic-pill">Visas</a>
    <a href="/news?category=visas&q=golden+visa" class="topic-pill">Golden Visa</a>
    <a href="/news?category=business&q=pt+pma" class="topic-pill">PT PMA</a>
    <a href="/news?category=taxes" class="topic-pill">Tax 2026</a>
    <a href="/news?category=visas&q=kitas" class="topic-pill">KITAS</a>
    <a href="/news?category=living" class="topic-pill">Digital Nomad</a>
    <a href="/news?category=property" class="topic-pill">Property</a>
    <a href="/news?category=visas&q=work+permit" class="topic-pill">Work Permits</a>
  </div>

`}
      />

      {/* ── Latest Intelligence (client-side, always fresh) ── */}
      <LatestIntelligence />

      {/* ── KBLI Navigator ── */}
      <div className="kbli-section">
        <div className="kbli-left">
          <span className="kbli-badge">Featured Intelligence Tool</span>
          <h2 className="kbli-title">
            KBLI 2025
            <br />
            Navigator
          </h2>
          <p className="kbli-desc">
            Instant access to all 1,563 KBLI 2025 codes with intelligent search,
            4-level risk assessment, PMA status tracking, and AI-powered
            guidance.
          </p>
          <div className="kbli-features">
            <span className="kbli-feat">Smart bilingual search</span>
            <span className="kbli-feat">4-level risk system</span>
            <span className="kbli-feat">PMA status tracking</span>
            <span className="kbli-feat">AI assistant</span>
          </div>
          <a href="/kbli" className="kbli-btn">
            ▶ Explore Navigator
          </a>
        </div>
        <div className="kbli-right">
          <KbliSearchBox />
        </div>
      </div>

      <HomepageStaticContent
        html={`
  <!-- Services -->
  <div class="services-section">
    <div class="services-top">
      <div>
        <h2 class="services-title">Our Services</h2>
        <p class="services-sub">Expert assistance for your Indonesia journey</p>
      </div>
      <a href="/contact" class="services-view">View all services →</a>
    </div>
    <div class="services-grid">
      <div class="service-card">
        <div class="service-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
        </div>
        <h3 class="service-name">Visa &amp; Immigration</h3>
        <p class="service-desc">KITAS, KITAP, Golden Visa, and all permit types</p>
      </div>
      <div class="service-card">
        <div class="service-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
        </div>
        <h3 class="service-name">Company Setup</h3>
        <p class="service-desc">PT PMA, PT Local, and business licensing</p>
      </div>
      <div class="service-card">
        <div class="service-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/></svg>
        </div>
        <h3 class="service-name">Tax &amp; Compliance</h3>
        <p class="service-desc">Personal and corporate tax services</p>
      </div>
      <div class="service-card">
        <div class="service-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        </div>
        <h3 class="service-name">Property</h3>
        <p class="service-desc">Leasehold, freehold, and investment guidance</p>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <footer class="site-footer">
    <div class="footer-top">
      <div class="footer-brand">
        <div class="footer-logo-wrap">
          <img class="footer-logo-img" src="/static/homepage/bali-zero-logo.png" alt="Bali Zero">
        </div>
        <p class="footer-desc">Your trusted partner for business, immigration, and investment in Indonesia since 2020. Trusted by 5,000+ clients.</p>
      </div>
      <div class="footer-col">
        <h4>Services</h4>
        <a href="/services#visa">Visa &amp; Immigration</a>
        <a href="/services#company">Company Setup</a>
        <a href="/services#tax">Tax &amp; Compliance</a>
        <a href="/services#property">Property</a>
        <a href="/news?category=visas&q=golden+visa">Golden Visa</a>
      </div>
      <div class="footer-col">
        <h4>News</h4>
        <a href="/news?category=visas">Visas</a>
        <a href="/news?category=business">Business</a>
        <a href="/news?category=taxes">Taxes</a>
        <a href="/news?category=property">Property</a>
        <a href="/news?category=living">Living</a>
      </div>
      <div class="footer-col">
        <h4>Contact</h4>
        <a href="mailto:info@balizero.com">info@balizero.com</a>
        <a href="tel:+6285904260571">+62 859 0426 0571</a>
        <a href="/contact">Bali, Indonesia</a>
        <a href="https://wa.me/6285904260571" target="_blank" rel="noopener">WhatsApp</a>
        <a href="https://t.me/Balizerobot" target="_blank" rel="noopener">Telegram</a>
      </div>
    </div>
    <div class="footer-bottom">
      <span class="footer-copy">© 2026 Bali Zero. All rights reserved.</span>
      <div class="footer-links">
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
        <a href="/cookies">Cookies</a>
      </div>
    </div>
  </footer>
</div>

`}
      />
      <ZantaraWidget />
      <Script id="balizero-homepage-js" strategy="afterInteractive">{`
// ════════ CAROUSEL ENGINE ════════
(function() {
  var slides = document.querySelectorAll('.slide');
  var dots = document.querySelectorAll('.dot');
  if (!slides.length) return;
  var current = 0;
  var timer = null;

  function goTo(n) {
    if (n === current) return;
    var prev = current;
    current = n;
    slides[prev].classList.remove('active');
    slides[prev].classList.add('leaving');
    slides[current].classList.add('entering');
    setTimeout(function() {
      slides[prev].classList.remove('leaving');
      slides[current].classList.remove('entering');
      slides[current].classList.add('active');
    }, 850);
    dots.forEach(function(d, i) { d.classList.toggle('active', i === current); });
  }

  // Expose globally for onclick handlers in static HTML
  window.goTo = function(n) { goTo(n); resetTimer(); };

  function nextSlide() {
    goTo((current + 1) % slides.length);
  }

  function resetTimer() {
    if (timer) clearInterval(timer);
    timer = setInterval(nextSlide, 6000);
  }

  function startTimer() {
    resetTimer();
  }

  var carousel = document.getElementById('carousel');
  if (carousel) {
    carousel.addEventListener('mouseenter', function() { clearInterval(timer); });
    carousel.addEventListener('mouseleave', startTimer);
  }

  dots.forEach(function(dot, i) {
    dot.addEventListener('click', function() { goTo(i); resetTimer(); });
  });

  startTimer();
})();

// ════════ MOUSE SPOTLIGHT ════════
document.addEventListener('mousemove', function(e) {
  document.body.style.setProperty('--mouse-x', e.clientX + 'px');
  document.body.style.setProperty('--mouse-y', e.clientY + 'px');
});
`}</Script>
    </>
  );
}
