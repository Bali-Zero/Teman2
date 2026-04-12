.pv-doc .title { font-size: 13px; font-weight: 600; color: var(--bz-text-primary); }
.pv-doc .meta { font-size: 11px; color: var(--bz-text-muted); margin-top: 2px; font-family: var(--bz-font-mono); }

.bz-btn.ghost {
  background: transparent; color: var(--bz-text-muted);
}
.bz-btn.ghost:hover { color: var(--bz-primary); }

/* =========================================================
 *  [7] KBLI · CODE DETAIL
 * ========================================================= */
.kd-crumb {
  display: flex; align-items: center; gap: 8px;
  padding: 14px 18px;
  background: color-mix(in srgb, var(--bz-surface) 55%, transparent);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255,255,255,.08);
  border-radius: var(--bz-radius-full);
  font-size: 12px;
  margin-bottom: 24px;
  max-width: fit-content;
}
.kd-crumb a {
  color: var(--bz-text-secondary);
  display: inline-flex; align-items: center; gap: 6px;
  transition: color .2s;
}
.kd-crumb a:hover { color: var(--cat-tax); }
.kd-crumb a .i { font-family: var(--bz-font-mono); opacity: .7; }
.kd-crumb .sep { color: var(--bz-text-faint); }
.kd-crumb .current {
  font-family: var(--bz-font-mono);
  color: var(--cat-tax);
  font-weight: 700;
}

.kd-hero {
  position: relative;
  border-radius: var(--bz-radius-3xl);
  overflow: hidden;
  padding: 80px 48px 48px;
  min-height: 380px;
  isolation: isolate;
  background: var(--bz-base-cinematic);
}
.kd-hero__bg {
  position: absolute; inset: 0;
  background-size: cover;
  background-position: center;
  filter: saturate(1.15);
}
.kd-hero__overlay {
  position: absolute; inset: 0;
  background:
    linear-gradient(135deg, rgba(184,154,64,.3) 0%, transparent 50%),
    linear-gradient(to bottom, transparent 20%, rgba(10,10,10,.85) 100%);
}
.kd-hero__grain {
  position: absolute; inset: 0;
  filter: url(#bz-grain);
  mix-blend-mode: overlay;
  opacity: .35;
  pointer-events: none;
}
.kd-hero__content {
  position: relative;
  z-index: 1;
}
.kd-code-pill {
  display: inline-flex; align-items: center;
  padding: 8px 16px;
  font-family: var(--bz-font-mono); font-weight: 800; font-size: 14px;
  letter-spacing: 0.04em;
  background: rgba(184,154,64,.2);
  color: var(--cat-tax);
  border: 1px solid rgba(184,154,64,.45);
  border-radius: var(--bz-radius-full);
  backdrop-filter: blur(12px);
}
.kd-title {
  font-size: clamp(32px, 5vw, 48px);
  font-weight: 900;
  letter-spacing: -0.035em;
  line-height: 1.05;
  color: var(--bz-text-pure);
  text-shadow: 0 2px 12px rgba(0,0,0,.6);
  margin-bottom: 8px;
}
.kd-title-id {
  font-size: 18px;
  color: rgba(255,255,255,.6);
  text-shadow: 0 1px 4px rgba(0,0,0,.5);
  margin-bottom: 16px;
}
.kd-section {
  font-size: 12px;
  color: rgba(255,255,255,.5);
  font-family: var(--bz-font-mono);
  letter-spacing: 0.05em;
  margin-bottom: 24px;
}
.kd-badges {
  display: flex; gap: 10px; flex-wrap: wrap;
}
.kd-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px;
  font-size: 12px; font-weight: 600;
  border-radius: var(--bz-radius-full);
  backdrop-filter: blur(12px);
}
.kd-badge--open {
  background: rgba(34,197,94,.18);
  color: var(--st-done);
  border: 1px solid rgba(34,197,94,.4);
}
.kd-badge--risk-low {
  background: rgba(92,184,138,.16);
  color: var(--cat-business);
  border: 1px solid rgba(92,184,138,.35);
}
.kd-badge--risk-low .dot {

codex
[Pro] Sto incrociando il CSS reale con qualche metrica oggettiva di contrasto, così non ti do un parere “a gusto”. Poi chiudo con una proposta di token set pronta da usare.
exec
js_repl in /Users/nuzantara/Desktop/nuzantara
 succeeded in 128ms:
exec
js_repl in /Users/nuzantara/Desktop/nuzantara
 succeeded in 1ms:
[
  {
    "fg": "#ffffff",
    "bg": "#0a0a0a",
    "contrast": "19.80"
  },
  {
    "fg": "#ffffff",
    "bg": "#121212",
    "contrast": "18.73"
  },
  {
    "fg": "#ffffff",
    "bg": "#161616",
    "contrast": "18.10"
  },
  {
    "fg": "#ffffff",
    "bg": "#1a1a1a",
    "contrast": "17.40"
  },
  {
    "fg": "#ffffff",
    "bg": "#1c1c1e",
    "contrast": "17.01"
  },
  {
    "fg": "#f5f5f5",
    "bg": "#242428",
    "contrast": "14.18"
  },
  {
    "fg": "#f5f5f5",
    "bg": "#1f1f23",
    "contrast": "15.07"
  },
  {
    "fg": "#f5f5f5",
    "bg": "#202226",
    "contrast": "14.61"
  },
  {
    "fg": "#ff2d4c",
    "bg": "#0a0a0a",
    "contrast": "5.40"
  },
  {
    "fg": "#ff2d4c",
    "bg": "#121212",
    "contrast": "5.11"
  },
  {
    "fg": "#ff2d4c",
    "bg": "#161616",
    "contrast": "4.94"
  },
  {
    "fg": "#ff2d4c",
    "bg": "#1a1a1a",
    "contrast": "4.75"
  },
  {
    "fg": "#ff3356",
    "bg": "#161616",
    "contrast": "5.05"
  },
  {
    "fg": "#e62140",
    "bg": "#161616",
    "contrast": "4.01"
  },
  {
    "fg": "#f01946",
    "bg": "#161616",
    "contrast": "4.25"
  },
  {
    "fg": "#4a8ec4",
    "bg": "#161616",
    "contrast": "5.13"
  },
  {
    "fg": "#5cb88a",
    "bg": "#161616",
    "contrast": "7.48"
  },
  {
    "fg": "#b89a40",
    "bg": "#161616",
    "contrast": "6.66"
  },
  {
    "fg": "#9880d8",
    "bg": "#161616",
    "contrast": "5.53"
  },
  {
    "fg": "#4ab8c4",
    "bg": "#161616",
    "contrast": "7.71"
  },
  {
    "fg": "#facc15",
    "bg": "#161616",
    "contrast": "11.82"
  },
  {
    "fg": "#22c55e",
    "bg": "#161616",
    "contrast": "7.94"
  },
  {
    "fg": "#3b82f6",
    "bg": "#161616",
    "contrast": "4.92"
  },
  {
    "fg": "#ef4444",
    "bg": "#161616",
    "contrast": "4.81"
  }
]
web search: 
web search: https://linear.app/
exec
js_repl in /Users/nuzantara/Desktop/nuzantara
 succeeded in 1ms:
[
  {
    "fg": "#ff2d4c",
    "bg": "#ffffff",
    "contrast": "3.66"
  },
  {
    "fg": "#ff3356",
    "bg": "#ffffff",
    "contrast": "3.58"
  },
  {
    "fg": "#e62140",
    "bg": "#ffffff",
    "contrast": "4.51"
  },
  {
    "fg": "#f01946",
    "bg": "#ffffff",
    "contrast": "4.26"
  },
  {
    "fg": "#4a8ec4",
    "bg": "#ffffff",
    "contrast": "3.52"
  },
  {
    "fg": "#5cb88a",
    "bg": "#ffffff",
    "contrast": "2.42"
  },
  {
    "fg": "#b89a40",
    "bg": "#ffffff",
    "contrast": "2.72"
  },
  {
    "fg": "#9880d8",
    "bg": "#ffffff",
    "contrast": "3.27"
  },
  {
    "fg": "#4ab8c4",
    "bg": "#ffffff",
    "contrast": "2.35"
  }
]
web search: 
web search: Linear app homepage official
web search: 
web search: https://linear.app/homepage
web search: 
web search: https://stripe.com/
codex
[Pro] Mi manca solo il contesto del hero marketing, perché lì il trattamento giusto non è lo stesso del dashboard. Poi chiudo con una risposta numerata e valori esatti.
exec
/bin/zsh -lc "sed -n '500,640p' /tmp/bz-draft-share.html" in /Users/nuzantara/Desktop/nuzantara
 succeeded in 0ms:
}
.mk-btn-consult:hover { background: var(--bz-primary); color: var(--bz-text-pure); }

/* Brand entrance strip */
.brand-entrance {
  border-bottom: 1px solid var(--bz-border);
  padding: 24px 60px;
  display: flex; align-items: center; justify-content: space-between;
  background: var(--bz-base);
}
.brand-entrance .logo-lg {
  width: 88px; height: 88px; border-radius: 50%;
  object-fit: cover; flex-shrink: 0;
}
.brand-entrance .brand-sub {
  font-family: var(--bz-font-mono); font-size: 10px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--bz-text-muted);
  margin-top: 8px;
  display: block;
}
.brand-entrance .brand-stats {
  display: flex; gap: 8px; align-items: center;
  font-family: var(--bz-font-mono); font-size: 10px;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--bz-text-muted);
}
.brand-entrance .brand-stats .sep { color: var(--bz-primary); opacity: 0.4; }

/* Hero carousel — single slide variant */
.hero-carousel {
  position: relative;
  height: 600px;
  background: var(--bz-base-cinematic);
  overflow: hidden;
  border-bottom: 1px solid var(--bz-border);
}
.hero-carousel .slide-bg {
  position: absolute; inset: 0;
  background-image: url('./hero-images/Bali_zero_hq_Long_queue_outside_Indonesian_immigration_office_at_5am,_people_s_713d52e9-a2ff-4245-8961-8e845f6f4d05.png');
  background-size: cover;
  background-position: center right;
  animation: kenburns 18s ease-in-out infinite alternate;
}
@keyframes kenburns {
  from { transform: scale(1.0); }
  to   { transform: scale(1.06) translate(-1%, -0.5%); }
}
.hero-carousel .slide-bg::before {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(to right,
    rgba(10,10,10,.92) 0%,
    rgba(10,10,10,.75) 35%,
    rgba(10,10,10,.35) 65%,
    rgba(10,10,10,.7) 100%);
}
.hero-carousel .slide-bg::after {
  content: ''; position: absolute; inset: 0;
  background:
    radial-gradient(ellipse at 15% 85%, var(--bz-primary-glow), transparent 50%),
    radial-gradient(ellipse at 85% 20%, rgba(59,130,246,.15), transparent 55%);
  mix-blend-mode: screen;
}
.hero-carousel .slide-content {
  position: absolute; inset: 0;
  display: flex; align-items: flex-end;
  padding: 0 60px 80px;
  gap: 60px;
}
.hero-carousel .slide-left { flex: 1; max-width: 680px; }
.hero-carousel .slide-kicker {
  display: flex; align-items: center; gap: 10px;
  font-family: var(--bz-font-mono); font-size: 11px;
  letter-spacing: 0.12em; color: var(--bz-primary);
  text-transform: uppercase;
  margin-bottom: 24px;
}
.hero-carousel .slide-kicker::before {
  content: ''; display: block; width: 36px; height: 1px;
  background: var(--bz-primary);
}
.hero-carousel .slide-headline {
  font-weight: 800;
  font-size: clamp(34px, 5vw, 64px);
  line-height: 1.03;
  letter-spacing: -0.035em;
  color: var(--bz-text-pure);
  margin-bottom: 24px;
  max-width: 620px;
}
.hero-carousel .slide-headline em { color: var(--bz-primary); }
.hero-carousel .slide-deck {
  font-size: 16px; color: var(--bz-text-secondary);
  line-height: 1.65; margin-bottom: 36px;
  max-width: 520px;
}
.hero-carousel .slide-actions { display: flex; align-items: center; gap: 20px; }
.hero-carousel .slide-num {
  font-family: var(--bz-font-mono); font-size: 13px;
  color: var(--bz-text-muted); letter-spacing: 0.05em;
}
.hero-carousel .slide-strip {
  width: 340px; flex-shrink: 0;
  display: flex; flex-direction: column;
}
.hero-carousel .strip-label {
  font-family: var(--bz-font-mono); font-size: 9px;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--bz-text-muted);
  margin-bottom: 16px;
}
.hero-carousel .strip-item {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 14px 0;
  border-top: 1px solid var(--bz-border);
}
.hero-carousel .strip-item .num {
  font-family: var(--bz-font-mono); font-size: 11px;
  color: var(--bz-primary);
}
.hero-carousel .strip-item .meta .kicker {
  font-family: var(--bz-font-mono); font-size: 9px;
  letter-spacing: 0.1em; color: var(--bz-text-muted);
  text-transform: uppercase; display: block; margin-bottom: 4px;
}
.hero-carousel .strip-item .meta .title {
  font-size: 13px; color: var(--bz-text-primary);
  line-height: 1.4;
}
.hero-carousel .carousel-dots {
  position: absolute; bottom: 32px; left: 60px;
  display: flex; gap: 8px; z-index: 5;
}
.hero-carousel .dot {
  width: 28px; height: 3px; border-radius: 2px;
  background: var(--bz-border-strong);
}
.hero-carousel .dot.active { background: var(--bz-primary); width: 44px; }

/* Topic pills strip */
.topics-strip {

exec
/bin/zsh -lc "sed -n '1048,1110p' /tmp/bz-draft-share.html" in /Users/nuzantara/Desktop/nuzantara
 succeeded in 0ms:
.services-section {
  padding: 80px 60px;
  border-bottom: 1px solid var(--bz-border);
  background: var(--bz-base);
}
.services-top {
  display: flex; align-items: flex-end; justify-content: space-between;
  margin-bottom: 48px;
}
.services-top h2 {
  font-size: 36px; font-weight: 800; letter-spacing: -0.03em;
  color: var(--bz-text-pure); margin-bottom: 6px;
}
.services-top .sub {
  font-size: 14px; color: var(--bz-text-secondary);
}
.services-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
}
.service-card {
  position: relative;
  background: var(--bz-surface);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,.08);
  border-radius: var(--bz-radius-2xl);
  padding: 28px 24px;
  transition: var(--bz-transition-base);
  overflow: hidden;
  box-shadow:
    0 4px 16px rgba(0,0,0,.3),
    inset 0 1px 0 rgba(255,255,255,.05);
}
.service-card::before {
  content: ''; position: absolute;
  top: -50%; right: -30%;
  width: 200px; height: 200px;
  border-radius: 50%;
  filter: blur(40px);
  opacity: 0.5;
  pointer-events: none;
  transition: opacity var(--bz-transition-base);
}
.service-card:hover::before { opacity: 0.9; }
.service-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 16px 40px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.1);
}
.service-card:nth-child(1)::before { background: var(--hue-visa); }
.service-card:nth-child(2)::before { background: var(--hue-business); }
.service-card:nth-child(3)::before { background: var(--hue-tax); }
.service-card:nth-child(4)::before { background: var(--hue-property); }
.service-card:nth-child(1):hover { border-color: var(--hue-visa); }
.service-card:nth-child(2):hover { border-color: var(--hue-business); }
.service-card:nth-child(3):hover { border-color: var(--hue-tax); }
.service-card:nth-child(4):hover { border-color: var(--hue-property); }
.service-card .icon {
  position: relative;
  width: 48px; height: 48px;
  border-radius: var(--bz-radius-lg);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 20px;
  font-family: var(--bz-font-mono); font-weight: 700; font-size: 14px;
  backdrop-filter: blur(10px);

exec
/bin/zsh -lc "sed -n '2188,2315p' /tmp/bz-draft-share.html" in /Users/nuzantara/Desktop/nuzantara
 succeeded in 0ms:
/* =========================================================
 *  [4] PORTAL — my.balizero.com
 *  Source: apps/mouth/src/app/portal/(authenticated)/page.tsx
 * ========================================================= */
#page-portal { padding: 40px 48px; }
.portal-wrap { max-width: 1200px; margin: 0 auto; }

.portal-welcome {
  margin-bottom: 40px;
}
.portal-welcome h1 {
  font-size: 36px; font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--bz-text-pure);
  margin-bottom: 6px;
}
.portal-welcome h1 em { color: var(--bz-primary); }
.portal-welcome p {
  font-size: 15px; color: var(--bz-text-secondary);
}

.portal-status-grid {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 16px; margin-bottom: 32px;
}
.portal-status {
  position: relative;
  background: var(--bz-surface);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255,255,255,.08);
  border-radius: var(--bz-radius-xl);
  padding: 24px;
  cursor: pointer;
  transition: var(--bz-transition-base);
  overflow: hidden;
  box-shadow:
    0 4px 16px rgba(0,0,0,.3),
    inset 0 1px 0 rgba(255,255,255,.05);
}
.portal-status::before {
  content: ''; position: absolute;
  top: -60%; right: -30%;
  width: 220px; height: 220px;
  border-radius: 50%;
  filter: blur(50px);
  opacity: 0.4;
  pointer-events: none;
  transition: opacity var(--bz-transition-base);
}
/* Portal status cards ← state grammar (on_process blue / completed green) */
.portal-status:nth-child(1)::before { background: var(--st-active); }   /* Immigration: pratica attiva */
.portal-status:nth-child(2)::before { background: var(--st-done); }     /* Company: completed */
.portal-status:nth-child(3)::before { background: var(--st-done); }     /* Tax: completed */
.portal-status:hover { transform: translateY(-3px); box-shadow: 0 12px 32px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.1); }
.portal-status:nth-child(1):hover { border-color: var(--st-active); }
.portal-status:nth-child(2):hover { border-color: var(--st-done); }
.portal-status:nth-child(3):hover { border-color: var(--st-done); }
.portal-status:hover::before { opacity: 0.7; }
.portal-status .head {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 16px;
  position: relative;
}
.portal-status .head { gap: 14px; margin-bottom: 18px; }
.portal-status .head .title { font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--bz-text-primary); }
.portal-status .label, .portal-status .sub { position: relative; }
.portal-status .head .title {
  font-size: 11px; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase;
  color: var(--bz-text-muted);
}
.portal-status .label {
  font-size: 19px; font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--bz-text-pure);
  margin-bottom: 4px;
}
.portal-status .sub {
  font-size: 12px; color: var(--bz-text-secondary);
}
.portal-status .traffic {
  position: absolute; top: 24px; right: 24px;
  width: 10px; height: 10px; border-radius: 50%;
  box-shadow: 0 0 10px currentColor;
}
.portal-status.ok .traffic { background: var(--bz-success); color: var(--bz-success); }
.portal-status.warn .traffic { background: var(--bz-warning); color: var(--bz-warning); }
.portal-status.expired .traffic { background: var(--bz-primary); color: var(--bz-primary); }

.portal-quick-bar {
  display: flex; gap: 12px; flex-wrap: wrap;
  margin-bottom: 36px;
}
.portal-quick-bar .pill {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 18px;
  background: var(--bz-warning-muted);
  border: 1px solid rgba(245,158,11,.25);
  border-radius: var(--bz-radius-lg);
  font-size: 13px; font-weight: 500;
  color: var(--bz-warning);
  transition: var(--bz-transition-fast);
}
.portal-quick-bar .pill:hover { transform: scale(1.01); }
.portal-quick-bar .pill.info {
  background: var(--bz-info-muted);
  border-color: rgba(59,130,246,.25);
  color: var(--bz-info);
}

.portal-timeline {
  background: var(--bz-surface);
  border: 1px solid var(--bz-border);
  border-radius: var(--bz-radius-xl);
  padding: 28px 32px;
}
.portal-timeline h2 {
  font-size: 18px; font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--bz-text-pure);
  margin-bottom: 24px;
}
/* Portal timeline ← ProcessStepper.tsx grammar
   pending (current)=blue animated / done=green / neutral=grey */
.tl-entry {
  display: flex; gap: 18px;
  padding: 18px 0;
  border-top: 1px solid var(--bz-border);

codex
Ho letto [bz-draft-share.html](/tmp/bz-draft-share.html). Il sistema è già forte; il problema non è “più colore”, è separare meglio `brand red`, `category hues` e `state colors`, e togliere un po’ di rumore cromatico dal prodotto.

1. **Background darkness level.** `#1a1a1a` non è il punto giusto per il dashboard: è troppo “mid-charcoal”, abbassa la tensione del rosso e fa sembrare i vetri più fangosi. Tra le opzioni che hai testato, la direzione giusta è `#161616`, ma io andrei leggermente più freddo con `#151517`. `#121212` è troppo vicino al marketing black; `#1c1c1e` va già verso il soft graphite “consumer”. Per tono: Linear/Vercel/Raycast stanno più vicino a `#111`-`#161`; Stripe accetta lift più evidenti; Arc è il limite oltre cui qui diventerebbe troppo morbido.

2. **Gerarchia per superficie.** Ti darei questa scala:
   `body wrapper` `#0b0b0c`
   `dashboard root` `#151517`
   `dashboard main content` `#18191c`
   `sidebar` `#101113`
   `cards` `#1f2126`
   `elevated surfaces` `#26292f`
   `hover` `#2d3138`
   `active/pressed` `#20242a`
   La regola è: sidebar più scura del main, card un notch sopra il main, modal/dropdown un notch sopra le card. Nel file attuale il blocco test `#1a1a1a / #242428 / #2e2e32` è troppo compresso e sembra più Electron generico che SaaS premium.

3. **Card background per contesto.**
   `Workspace dashboard`: `#1e2025` con opacità alta; se vuoi glass, `background: rgba(30,32,37,.82)`. Qui la priorità è leggibilità di numeri, ring, sparkline e righe pipeline.
   `Portal`: `#23262b`, oppure `rgba(35,38,43,.68)`. Più arioso, meno “control room”, più friendly.
   `Marketing hero cards`: base quasi-black `#0c0c0e` con overlay `#0c0c0e80 -> #0c0c0ed9`. Qui il vetro deve sembrare editoriale, non UI kit.

4. **Signal red `#ff2d4c`.** Su dark è il migliore dei quattro: io lo terrei come `primary`. `#ff3356` è più rumoroso e più “consumer fintech”; `#e62140` funziona meglio su bianco ma perde energia su dark; `#f01946` scivola troppo verso il magenta e pesta i piedi al violet. La soluzione giusta non è cambiare il primary, ma sdoppiarlo:
   `dark primary` `#ff2d4c`
   `light primary` `#e62140`
   `hover` `#e51f41`
   `active` `#c91836`

5. **Category hue set.** È quasi buono, ma hai due collisioni. `living` non può essere lo stesso rosso del brand, e `emerging #4ab8c4` è troppo vicino a `visa #4a8ec4`. Io userei:
   `visa` `#5a93cb`
   `business` `#5dbb8d`
   `tax` `#c49c46`
   `property` `#9b85e4`
   `living` `#ff6a52`
   `emerging` `#42b8ad`
   Così il set resta sofisticato ma più bilanciato termicamente: oggi è un po’ troppo freddo.

6. **State colors.** Il livello di saturazione attuale va bene per `dot`, `badge`, `ring`, non per superfici estese. Soprattutto `#facc15` e `#ef4444` leggono “Tailwind default”, non “Bali Zero”. Io farei un notch più basso:
   `inquiry` `#98a1ad`
   `wait` `#f08a36`
   `invoice` `#e5be2e`
   `active` `#4c8cf0`
   `done` `#2fb56c`
   `fail` `#e35c5c`
   E sulle row surface userei `bg` al `6-8%`, `border` al `18-22%`, `badge` al `14-16%`. Nel file attuale `0.035` per i row bg è troppo timido.

7. **Aurora body gradient.** Così com’è è troppo per un business app. Su marketing e KBLI home va bene; su workspace e portal introduce “chroma soup” e toglie precisione al vetro. Alternativa:
   top-left `rgba(74,142,196,.10)`
   bottom-right `rgba(255,45,76,.08)`
   center wash `rgba(255,255,255,.03)`
   `blur: 96px`
   `overall opacity: .28`
   Toglierei verde e violet dal prodotto e li lascerei ai page hero.

8. **Tab bar da 7 item.** `overflow-x:auto` con `mask-image` è un fallback corretto per una demo, non la soluzione giusta per ship. Il problema vero è architetturale: `Portal · Visa` e `KBLI · 56101` non sono peer delle 5 top-level. Devono diventare contesto secondario: breadcrumb, subnav, o `More`. Se fai questo, le 5 tab vere entrano; solo dopo ha senso tenere lo scroll come fallback.

9. **Metallic text su `Rp 847M`.** In dashboard è un po’ cheesy. Non brutto, ma troppo “chrome effect” rispetto al resto del linguaggio. Se vuoi salvarlo, fallo più platinum e meno contrastato:
   `#fafafa 0%`
   `#d7d7d7 40%`
   `#f4f4f4 54%`
   `#9f9f9f 100%`
   e togli il `drop-shadow`. Meglio ancora: dashboard KPI in `#ffffff`, metallic solo in hero, premium card, o numeri editoriali.

10. **Colore/surface mancante.** Ti manca una famiglia `ink/cool neutral`, non semantica. Aggiungerei:
   `--bz-ink-1: #10151b`
   `--bz-ink-2: #151b22`
   `--bz-ink-border: rgba(120,160,200,.18)`
   Serve per input, tabelle, selected rows, sidebar dividers e superfici “operative” che oggi stanno tutte nel grigio neutro. È quello che porta il sistema da “good dark dashboard” a “can ship”.

Sintesi secca: tieni il marketing a `#0a0a0a`, porta il dashboard a `#151517`, separa `living` dal brand red, sposta `emerging` più verso teal-green, abbassa l’aurora nel prodotto, e demota le 2 tab di dettaglio. Lì fai il salto.

Riferimento di tono che ho usato: [Linear](https://linear.app), [Vercel](https://vercel.com), [Stripe](https://stripe.com), [Raycast](https://www.raycast.com), [Arc](https://arc.net).
tokens used
160.323
Ho letto [bz-draft-share.html](/tmp/bz-draft-share.html). Il sistema è già forte; il problema non è “più colore”, è separare meglio `brand red`, `category hues` e `state colors`, e togliere un po’ di rumore cromatico dal prodotto.

1. **Background darkness level.** `#1a1a1a` non è il punto giusto per il dashboard: è troppo “mid-charcoal”, abbassa la tensione del rosso e fa sembrare i vetri più fangosi. Tra le opzioni che hai testato, la direzione giusta è `#161616`, ma io andrei leggermente più freddo con `#151517`. `#121212` è troppo vicino al marketing black; `#1c1c1e` va già verso il soft graphite “consumer”. Per tono: Linear/Vercel/Raycast stanno più vicino a `#111`-`#161`; Stripe accetta lift più evidenti; Arc è il limite oltre cui qui diventerebbe troppo morbido.

2. **Gerarchia per superficie.** Ti darei questa scala:
   `body wrapper` `#0b0b0c`
   `dashboard root` `#151517`
   `dashboard main content` `#18191c`
   `sidebar` `#101113`
   `cards` `#1f2126`
   `elevated surfaces` `#26292f`
   `hover` `#2d3138`
   `active/pressed` `#20242a`
   La regola è: sidebar più scura del main, card un notch sopra il main, modal/dropdown un notch sopra le card. Nel file attuale il blocco test `#1a1a1a / #242428 / #2e2e32` è troppo compresso e sembra più Electron generico che SaaS premium.

3. **Card background per contesto.**
   `Workspace dashboard`: `#1e2025` con opacità alta; se vuoi glass, `background: rgba(30,32,37,.82)`. Qui la priorità è leggibilità di numeri, ring, sparkline e righe pipeline.
   `Portal`: `#23262b`, oppure `rgba(35,38,43,.68)`. Più arioso, meno “control room”, più friendly.
   `Marketing hero cards`: base quasi-black `#0c0c0e` con overlay `#0c0c0e80 -> #0c0c0ed9`. Qui il vetro deve sembrare editoriale, non UI kit.

4. **Signal red `#ff2d4c`.** Su dark è il migliore dei quattro: io lo terrei come `primary`. `#ff3356` è più rumoroso e più “consumer fintech”; `#e62140` funziona meglio su bianco ma perde energia su dark; `#f01946` scivola troppo verso il magenta e pesta i piedi al violet. La soluzione giusta non è cambiare il primary, ma sdoppiarlo:
   `dark primary` `#ff2d4c`
   `light primary` `#e62140`
   `hover` `#e51f41`
   `active` `#c91836`

5. **Category hue set.** È quasi buono, ma hai due collisioni. `living` non può essere lo stesso rosso del brand, e `emerging #4ab8c4` è troppo vicino a `visa #4a8ec4`. Io userei:
   `visa` `#5a93cb`
   `business` `#5dbb8d`
   `tax` `#c49c46`
   `property` `#9b85e4`
   `living` `#ff6a52`
   `emerging` `#42b8ad`
   Così il set resta sofisticato ma più bilanciato termicamente: oggi è un po’ troppo freddo.

6. **State colors.** Il livello di saturazione attuale va bene per `dot`, `badge`, `ring`, non per superfici estese. Soprattutto `#facc15` e `#ef4444` leggono “Tailwind default”, non “Bali Zero”. Io farei un notch più basso:
   `inquiry` `#98a1ad`
   `wait` `#f08a36`
   `invoice` `#e5be2e`
   `active` `#4c8cf0`
   `done` `#2fb56c`
   `fail` `#e35c5c`
   E sulle row surface userei `bg` al `6-8%`, `border` al `18-22%`, `badge` al `14-16%`. Nel file attuale `0.035` per i row bg è troppo timido.

7. **Aurora body gradient.** Così com’è è troppo per un business app. Su marketing e KBLI home va bene; su workspace e portal introduce “chroma soup” e toglie precisione al vetro. Alternativa:
   top-left `rgba(74,142,196,.10)`
   bottom-right `rgba(255,45,76,.08)`
   center wash `rgba(255,255,255,.03)`
   `blur: 96px`
   `overall opacity: .28`
   Toglierei verde e violet dal prodotto e li lascerei ai page hero.

8. **Tab bar da 7 item.** `overflow-x:auto` con `mask-image` è un fallback corretto per una demo, non la soluzione giusta per ship. Il problema vero è architetturale: `Portal · Visa` e `KBLI · 56101` non sono peer delle 5 top-level. Devono diventare contesto secondario: breadcrumb, subnav, o `More`. Se fai questo, le 5 tab vere entrano; solo dopo ha senso tenere lo scroll come fallback.

9. **Metallic text su `Rp 847M`.** In dashboard è un po’ cheesy. Non brutto, ma troppo “chrome effect” rispetto al resto del linguaggio. Se vuoi salvarlo, fallo più platinum e meno contrastato:
   `#fafafa 0%`
   `#d7d7d7 40%`
   `#f4f4f4 54%`
   `#9f9f9f 100%`
   e togli il `drop-shadow`. Meglio ancora: dashboard KPI in `#ffffff`, metallic solo in hero, premium card, o numeri editoriali.

10. **Colore/surface mancante.** Ti manca una famiglia `ink/cool neutral`, non semantica. Aggiungerei:
   `--bz-ink-1: #10151b`
   `--bz-ink-2: #151b22`
   `--bz-ink-border: rgba(120,160,200,.18)`
   Serve per input, tabelle, selected rows, sidebar dividers e superfici “operative” che oggi stanno tutte nel grigio neutro. È quello che porta il sistema da “good dark dashboard” a “can ship”.

Sintesi secca: tieni il marketing a `#0a0a0a`, porta il dashboard a `#151517`, separa `living` dal brand red, sposta `emerging` più verso teal-green, abbassa l’aurora nel prodotto, e demota le 2 tab di dettaglio. Lì fai il salto.

Riferimento di tono che ho usato: [Linear](https://linear.app), [Vercel](https://vercel.com), [Stripe](https://stripe.com), [Raycast](https://www.raycast.com), [Arc](https://arc.net).
