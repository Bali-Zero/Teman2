# Futuristic Dark UI/UX Elements - Pure CSS/JS Collection

## Project Context

**Palette D Monochrome Modern**

- Base: `#0a0a0a`
- Signal Red: `#ff2d4c`
- White: `#ffffff`
- Category Hues: Blue `#3b82f6`, Green `#10b981`, Gold `#f59e0b`, Violet `#8b5cf6`, Teal `#06b6d4`

---

## A. Backgrounds

### 1. Noise Grain Overlay

**What it looks like:** Subtle animated film grain texture over dark background

```css
.noise-bg {
  position: relative;
  background-color: #0a0a0a;
}

.noise-bg::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.15'/%3E%3C/svg%3E");
  opacity: 0.15;
  pointer-events: none;
  animation: grain 8s steps(10) infinite;
}

@keyframes grain {
  0%,
  100% {
    transform: translate(0, 0);
  }
  10% {
    transform: translate(-5%, -10%);
  }
  20% {
    transform: translate(-15%, 5%);
  }
  30% {
    transform: translate(7%, -25%);
  }
  40% {
    transform: translate(-5%, 25%);
  }
  50% {
    transform: translate(-15%, 10%);
  }
  60% {
    transform: translate(15%, 0%);
  }
  70% {
    transform: translate(0%, 15%);
  }
  80% {
    transform: translate(3%, 35%);
  }
  90% {
    transform: translate(-10%, 10%);
  }
}
```

**Browser support:** Chrome 79+, Safari 13.1+, Firefox 75+  
**Performance:** Low  
**Use:** Hero sections, card backgrounds

### 2. Gradient Mesh Background

**What it looks like:** Soft gradient mesh with subtle color intersections

```css
.gradient-mesh {
  background-color: #0a0a0a;
  background-image:
    radial-gradient(at 40% 20%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
    radial-gradient(at 80% 0%, rgba(255, 45, 76, 0.1) 0px, transparent 50%),
    radial-gradient(at 0% 50%, rgba(139, 92, 246, 0.1) 0px, transparent 50%),
    radial-gradient(at 80% 50%, rgba(6, 182, 212, 0.1) 0px, transparent 50%),
    radial-gradient(at 0% 100%, rgba(16, 185, 129, 0.1) 0px, transparent 50%),
    radial-gradient(at 80% 100%, rgba(245, 158, 11, 0.1) 0px, transparent 50%),
    radial-gradient(at 0% 0%, rgba(255, 255, 255, 0.05) 0px, transparent 50%);
  background-size: 200% 200%;
  animation: meshMove 20s ease infinite;
}

@keyframes meshMove {
  0%,
  100% {
    background-position: 0% 0%;
  }
  25% {
    background-position: 100% 0%;
  }
  50% {
    background-position: 100% 100%;
  }
  75% {
    background-position: 0% 100%;
  }
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 16+  
**Performance:** Low  
**Use:** Dashboard backgrounds, hero sections

### 3. Grid Overlay with Animation

**What it looks like:** Animated grid lines that subtly pulse

```css
.grid-overlay {
  position: relative;
  background-color: #0a0a0a;
}

.grid-overlay::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: linear-gradient(
    to bottom,
    transparent,
    black 10%,
    black 90%,
    transparent
  );
  animation: gridPulse 4s ease-in-out infinite;
}

@keyframes gridPulse {
  0%,
  100% {
    opacity: 0.3;
  }
  50% {
    opacity: 0.6;
  }
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 16+  
**Performance:** Low  
**Use:** Data visualization backgrounds, tech dashboards

### 4. Aurora Background Effect

**What it looks like:** Soft, flowing aurora-like gradients

```css
.aurora-bg {
  position: relative;
  background: linear-gradient(45deg, #0a0a0a 0%, #111 100%);
  overflow: hidden;
}

.aurora-bg::before,
.aurora-bg::after {
  content: "";
  position: absolute;
  width: 200%;
  height: 200%;
  background:
    radial-gradient(
      circle at 30% 30%,
      rgba(59, 130, 246, 0.2) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 70% 70%,
      rgba(255, 45, 76, 0.15) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 50% 20%,
      rgba(6, 182, 212, 0.1) 0%,
      transparent 50%
    );
  animation: auroraFloat 20s ease-in-out infinite;
  mix-blend-mode: screen;
}

.aurora-bg::after {
  animation-delay: -10s;
  opacity: 0.7;
}

@keyframes auroraFloat {
  0%,
  100% {
    transform: translate(0, 0) rotate(0deg);
  }
  33% {
    transform: translate(-5%, 5%) rotate(120deg);
  }
  66% {
    transform: translate(5%, -5%) rotate(240deg);
  }
}
```

**Browser support:** Chrome 41+, Safari 8+, Firefox 32+  
**Performance:** Medium  
**Use:** Feature sections, premium content areas

### 5. Parallax Dots Background

**What it looks like:** Floating dots with parallax scroll effect

```css
.parallax-dots {
  position: relative;
  background-color: #0a0a0a;
  overflow: hidden;
}

.parallax-dots::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(
      circle at 10% 20%,
      rgba(255, 255, 255, 0.1) 1px,
      transparent 1px
    ),
    radial-gradient(
      circle at 90% 40%,
      rgba(255, 255, 255, 0.08) 1px,
      transparent 1px
    ),
    radial-gradient(
      circle at 50% 80%,
      rgba(255, 255, 255, 0.06) 1px,
      transparent 1px
    );
  background-size:
    100px 100px,
    150px 150px,
    200px 200px;
  animation: parallaxDots 20s linear infinite;
}

@keyframes parallaxDots {
  0% {
    transform: translate(0, 0);
  }
  100% {
    transform: translate(-50px, -50px);
  }
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 16+  
**Performance:** Low  
**Use:** Background for long-scrolling content

### 6. Animated Conic Gradient

**What it looks like:** Rotating conic gradient with subtle color transitions

```css
.conic-gradient-bg {
  position: relative;
  background: #0a0a0a;
}

.conic-gradient-bg::before {
  content: "";
  position: absolute;
  inset: 0;
  background: conic-gradient(
    from 0deg at 50% 50%,
    transparent 0deg,
    rgba(255, 45, 76, 0.1) 60deg,
    rgba(59, 130, 246, 0.1) 120deg,
    rgba(16, 185, 129, 0.1) 180deg,
    rgba(245, 158, 11, 0.1) 240deg,
    rgba(139, 92, 246, 0.1) 300deg,
    transparent 360deg
  );
  animation: rotateConic 10s linear infinite;
  opacity: 0.3;
  filter: blur(20px);
}

@keyframes rotateConic {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
```

**Browser support:** Chrome 69+, Safari 12.1+, Firefox 83+  
**Performance:** Medium  
**Use:** Loading states, attention-grabbing sections

### 7. Subtle Scanlines

**What it looks like:** Very subtle moving scanlines like a high-end monitor

```css
.scanlines-bg {
  position: relative;
  background-color: #0a0a0a;
}

.scanlines-bg::before {
  content: "";
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 1px,
    rgba(255, 255, 255, 0.02) 1px,
    rgba(255, 255, 255, 0.02) 2px
  );
  background-size: 100% 4px;
  animation: scanlines 8s linear infinite;
  pointer-events: none;
}

@keyframes scanlines {
  from {
    background-position: 0 0;
  }
  to {
    background-position: 0 8px;
  }
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 16+  
**Performance:** Low  
**Use:** Terminal-like interfaces, code editors

---

## B. Glassmorphism Variants

### 8. Frosted Glass Effect

**What it looks like:** Realistic frosted glass with backdrop blur

```css
.frosted-glass {
  background: rgba(10, 10, 10, 0.7);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

/* Fallback for Firefox without backdrop-filter */
@supports not (backdrop-filter: blur(10px)) {
  .frosted-glass {
    background: rgba(20, 20, 20, 0.95);
  }
}
```

**Browser support:** Chrome 76+, Safari 9+, Firefox 103+  
**Performance:** Medium (GPU accelerated)  
**Use:** Modals, cards, navigation bars

### 9. Liquid Glass Effect

**What it looks like:** Glass with flowing liquid-like edges

```css
.liquid-glass {
  position: relative;
  background: rgba(10, 10, 10, 0.8);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  overflow: hidden;
}

.liquid-glass::before {
  content: "";
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: conic-gradient(
    transparent,
    rgba(255, 45, 76, 0.1),
    rgba(59, 130, 246, 0.1),
    rgba(16, 185, 129, 0.1),
    transparent
  );
  animation: liquidRotate 6s linear infinite;
  opacity: 0.3;
}

@keyframes liquidRotate {
  100% {
    transform: rotate(360deg);
  }
}
```

**Browser support:** Chrome 76+, Safari 9+, Firefox 103+  
**Performance:** Medium  
**Use:** Premium feature cards, status indicators

### 10. Refraction Effect

**What it looks like:** Glass that appears to refract light

```css
.refraction-glass {
  position: relative;
  background: linear-gradient(
    135deg,
    rgba(10, 10, 10, 0.9) 0%,
    rgba(20, 20, 20, 0.9) 100%
  );
  backdrop-filter: blur(15px);
  border: 1px solid rgba(255, 255, 255, 0.2);
}

.refraction-glass::after {
  content: "";
  position: absolute;
  top: 0;
  left: -100%;
  width: 50%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.1),
    transparent
  );
  transform: skewX(-15deg);
  animation: refractionShine 3s ease-in-out infinite;
}

@keyframes refractionShine {
  0%,
  100% {
    left: -100%;
  }
  50% {
    left: 150%;
  }
}
```

**Browser support:** Chrome 76+, Safari 9+, Firefox 103+  
**Performance:** Medium  
**Use:** Highlighted content, featured items

### 11. Chromatic Aberration Fake

**What it looks like:** Subtle color separation like lens aberration

```css
.chromatic-aberration {
  position: relative;
  color: white;
}

.chromatic-aberration::before,
.chromatic-aberration::after {
  content: attr(data-text);
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0.5;
}

.chromatic-aberration::before {
  color: #ff2d4c;
  transform: translate(0.5px, 0.5px);
  mix-blend-mode: screen;
}

.chromatic-aberration::after {
  color: #3b82f6;
  transform: translate(-0.5px, -0.5px);
  mix-blend-mode: screen;
}

/* Usage in HTML: <div class="chromatic-aberration" data-text="Your Text">Your Text</div> */
```

**Browser support:** Chrome 41+, Safari 8+, Firefox 32+  
**Performance:** Low  
**Use:** Headers, logos, important labels

### 12. Inner Light Leak

**What it looks like:** Soft light leaking from inside edges

```css
.inner-light-leak {
  position: relative;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.inner-light-leak::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    radial-gradient(
      circle at 20% 80%,
      rgba(255, 45, 76, 0.1) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 80% 20%,
      rgba(59, 130, 246, 0.1) 0%,
      transparent 50%
    );
  opacity: 0;
  transition: opacity 0.3s ease;
}

.inner-light-leak:hover::before {
  opacity: 1;
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 16+  
**Performance:** Low  
**Use:** Interactive cards, hover states

---

## C. Text Effects

### 13. Gradient Text with Animation

**What it looks like:** Text with animated gradient that sweeps across

```css
.gradient-text {
  background: linear-gradient(
    90deg,
    #ff2d4c,
    #3b82f6,
    #10b981,
    #f59e0b,
    #8b5cf6,
    #ff2d4c
  );
  background-size: 300% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: gradientFlow 4s linear infinite;
}

@keyframes gradientFlow {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 300% 50%;
  }
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 49+  
**Performance:** Low  
**Use:** Headers, call-to-action text

### 14. Tight Text Shadow Glow

**What it looks like:** Sharp text glow without blur for crisp edges

```css
.text-glow-tight {
  color: #ffffff;
  text-shadow:
    0 0 1px rgba(255, 45, 76, 0.8),
    0 0 2px rgba(255, 45, 76, 0.6),
    0 0 3px rgba(255, 45, 76, 0.4),
    0 0 4px rgba(255, 45, 76, 0.2);
  transition: text-shadow 0.3s ease;
}

.text-glow-tight:hover {
  text-shadow:
    0 0 2px rgba(255, 45, 76, 1),
    0 0 4px rgba(255, 45, 76, 0.8),
    0 0 6px rgba(255, 45, 76, 0.6),
    0 0 8px rgba(255, 45, 76, 0.4);
}
```

**Browser support:** Chrome 4+, Safari 3.1+, Firefox 3.5+  
**Performance:** Low  
**Use:** Important labels, status text

### 15. Metallic Sheen Text

**What it looks like:** Text with metallic reflection effect

```css
.metallic-text {
  color: #ffffff;
  background: linear-gradient(
    135deg,
    #ffffff 0%,
    #cccccc 25%,
    #ffffff 50%,
    #cccccc 75%,
    #ffffff 100%
  );
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: metallicShine 3s linear infinite;
}

@keyframes metallicShine {
  to {
    background-position: 200% center;
  }
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 49+  
**Performance:** Low  
**Use:** Premium features, pricing tiers

### 16. Typewriter Effect

**What it looks like:** Text appears character by character like typing

```css
.typewriter {
  overflow: hidden;
  border-right: 2px solid #ff2d4c;
  white-space: nowrap;
  animation:
    typing 3.5s steps(40, end),
    blink-caret 0.75s step-end infinite;
}

@keyframes typing {
  from {
    width: 0;
  }
  to {
    width: 100%;
  }
}

@keyframes blink-caret {
  from,
  to {
    border-color: transparent;
  }
  50% {
    border-color: #ff2d4c;
  }
}
```

**Browser support:** Chrome 43+, Safari 9+, Firefox 16+  
**Performance:** Low  
**Use:** Hero sections, loading states

### 17. Split-Letter Reveal

**What it looks like:** Letters slide in from opposite directions

```css
.split-reveal {
  display: inline-block;
  overflow: hidden;
}

.split-reveal span {
  display: inline-block;
  transform: translateY(100%);
  opacity: 0;
  animation: splitReveal 0.8s cubic-bezier(0.23, 1, 0.32, 1) forwards;
}

.split-reveal span:nth-child(odd) {
  animation-delay: 0.1s;
}

.split-reveal span:nth-child(even) {
  animation-delay: 0.2s;
}

@keyframes splitReveal {
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* HTML: <div class="split-reveal"><span>H</span><span>e</span><span>l</span><span>l</span><span>o</span></div> */
```

**Browser support:** Chrome 43+, Safari 9+, Firefox 16+  
**Performance:** Low  
**Use:** Page transitions, attention grabbers

### 18. Font Variation Axis Animation

**What it looks like:** Variable font weight/slant animates smoothly

```css
@font-face {
  font-family: "VariableFont";
  src: url("path-to-variable-font.woff2") format("woff2-variations");
  font-weight: 100 900;
  font-stretch: 75% 125%;
}

.variable-font-animation {
  font-family: "VariableFont", sans-serif;
  font-variation-settings:
    "wght" 100,
    "wdth" 100;
  animation: fontVariation 3s ease-in-out infinite alternate;
}

@keyframes fontVariation {
  0% {
    font-variation-settings:
      "wght" 100,
      "wdth" 100;
  }
  100% {
    font-variation-settings:
      "wght" 900,
      "wdth" 125;
  }
}
```

**Browser support:** Chrome 62+, Safari 11+, Firefox 62+  
**Performance:** Low  
**Use:** Dynamic headings, interactive text

---

## D. Borders

### 19. Rotating Conic Gradient Border

**What it looks like:** Border with rotating gradient colors

```css
.conic-border {
  position: relative;
  background: #0a0a0a;
  padding: 1px;
  border-radius: 8px;
}

.conic-border::before {
  content: "";
  position: absolute;
  inset: -1px;
  background: conic-gradient(
    #ff2d4c,
    #3b82f6,
    #10b981,
    #f59e0b,
    #8b5cf6,
    #ff2d4c
  );
  border-radius: 9px;
  animation: rotateConicBorder 3s linear infinite;
  z-index: -1;
}

@keyframes rotateConicBorder {
  100% {
    transform: rotate(360deg);
  }
}
```

**Browser support:** Chrome 69+, Safari 12.1+, Firefox 83+  
**Performance:** Medium  
**Use:** Featured cards, active states

### 20. Subtle Marching Ants Border

**What it looks like:** Animated dashed border that appears to march

```css
.marching-ants {
  position: relative;
  border: 1px dashed rgba(255, 255, 255, 0.3);
  background: #0a0a0a;
}

.marching-ants::before {
  content: "";
  position: absolute;
  inset: -1px;
  border: 1px dashed rgba(255, 255, 255, 0.6);
  border-radius: inherit;
  animation: marchAnts 1s linear infinite;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.marching-ants:hover::before {
  opacity: 1;
}

@keyframes marchAnts {
  0% {
    stroke-dashoffset: 0;
  }
  100% {
    stroke-dashoffset: 10;
  }
}
```

**Browser support:** Chrome 43+, Safari 9+, Firefox 16+  
**Performance:** Low  
**Use:** Selection states, drag targets

### 21. Glow Border on Hover

**What it looks like:** Border emits soft glow on hover

```css
.glow-border {
  position: relative;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  transition: all 0.3s ease;
}

.glow-border::before {
  content: "";
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  padding: 2px;
  background: linear-gradient(45deg, #ff2d4c, #3b82f6, #10b981);
  -webkit-mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  mask:
    linear-gradient(#fff 0 0) content-box,
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.glow-border:hover::before {
  opacity: 1;
}
```

**Browser support:** Chrome 120+, Safari 15.4+, Firefox 53+  
**Performance:** Medium  
**Use:** Interactive cards, buttons

### 22. Animated 1px Dashed Border

**What it looks like:** Ultra-thin dashed border with flowing animation

```css
.animated-dashed-border {
  position: relative;
  background: #0a0a0a;
}

.animated-dashed-border::before {
  content: "";
  position: absolute;
  inset: 0;
  border: 1px dashed transparent;
  border-radius: inherit;
  background:
    linear-gradient(90deg, #ff2d4c 50%, transparent 50%) 0 0/10px 1px,
    linear-gradient(90deg, #ff2d4c 50%, transparent 50%) 0 100%/10px 1px,
    linear-gradient(0deg, #ff2d4c 50%, transparent 50%) 0 0/1px 10px,
    linear-gradient(0deg, #ff2d4c 50%, transparent 50%) 100% 0/1px 10px;
  background-repeat: repeat-x, repeat-x, repeat-y, repeat-y;
  animation: dashMove 1s linear infinite;
}

@keyframes dashMove {
  0% {
    background-position:
      0 0,
      0 100%,
      0 0,
      100% 0;
  }
  100% {
    background-position:
      10px 0,
      -10px 100%,
      0 -10px,
      100% 10px;
  }
}
```

**Browser support:** Chrome 26+, Safari 6.1+, Firefox 16+  
**Performance:** Low  
**Use:** Progress indicators, loading containers

### 23. L-Shaped Corner Markers

**What it looks like:** Minimal L-shaped markers at corners

```css
.corner-markers {
  position: relative;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.corner-markers::before,
.corner-markers::after {
  content: "";
  position: absolute;
  width: 12px;
  height: 12px;
  border: 2px solid #ff2d4c;
}

.corner-markers::before {
  top: -2px;
  left: -2px;
  border-right: none;
  border-bottom: none;
}

.corner-markers::after {
  bottom: -2px;
  right: -2px;
  border-left: none;
  border-top: none;
}
```

**Browser support:** Chrome 4+, Safari 3.1+, Firefox 3.5+  
**Performance:** Low  
**Use:** Code blocks, terminal windows

---

## E. Cards

### 24. 3D Tilt on Mousemove

**What it looks like:** Card tilts in 3D space following cursor

```css
.tilt-card {
  transform-style: preserve-3d;
  perspective: 1000px;
  transition: transform 0.1s ease;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
}
```

```javascript
// Vanilla JS for tilt effect
document.querySelectorAll(".tilt-card").forEach((card) => {
  card.addEventListener("mousemove", (e) => {
    const rect = card.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateY = ((x - centerX) / centerX) * 5;
    const rotateX = ((centerY - y) / centerY) * 5;

    card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
  });

  card.addEventListener("mouseleave", () => {
    card.style.transform = "perspective(1000px) rotateX(0) rotateY(0)";
  });
});
```

**Browser support:** Chrome 36+, Safari 9+, Firefox 16+  
**Performance:** Medium (requires JS)  
**Use:** Product cards, portfolio items

### 25. Hover Lift + Glow

**What it looks like:** Card lifts and glows on hover

```css
.hover-lift-card {
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow:
    0 4px 6px rgba(0, 0, 0, 0.1),
    0 1px 3px rgba(0, 0, 0, 0.08);
}

.hover-lift-card:hover {
  transform: translateY(-4px);
  border-color: rgba(255, 45, 76, 0.3);
  box-shadow:
    0 20px 25px rgba(0, 0, 0, 0.2),
    0 8px 10px rgba(0, 0, 0, 0.1),
    0 0 0 1px rgba(255, 45, 76, 0.1);
}
```

**Browser support:** Chrome 4+, Safari 3.1+, Firefox 3.5+  
**Performance:** Low  
**Use:** Dashboard cards, feature tiles

### 26. Perspective Stack Effect

**What it looks like:** Cards appear stacked with depth

```css
.perspective-stack {
  position: relative;
  background: #0a0a0a;
  border-radius: 12px;
}

.perspective-stack::before,
.perspective-stack::after {
  content: "";
  position: absolute;
  inset: 0;
  background: inherit;
  border-radius: inherit;
  z-index: -1;
}

.perspective-stack::before {
  transform: translateY(4px) scale(0.98);
  opacity: 0.6;
  filter: blur(2px);
}

.perspective-stack::after {
  transform: translateY(8px) scale(0.96);
  opacity: 0.3;
  filter: blur(4px);
}
```

**Browser support:** Chrome 4+, Safari 3.1+, Firefox 3.5+  
**Performance:** Low  
**Use:** Notification cards, stacked items

### 27. Bento Grid Asymmetric

**What it looks like:** Asymmetric grid layout with varied card sizes

```css
.bento-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  grid-template-rows: repeat(6, 100px);
  gap: 16px;
}

.bento-card-large {
  grid-column: span 8;
  grid-row: span 3;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
}

.bento-card-medium {
  grid-column: span 4;
  grid-row: span 2;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
}

.bento-card-small {
  grid-column: span 3;
  grid-row: span 1;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
}
```

**Browser support:** Chrome 57+, Safari 10.1+, Firefox 52+  
**Performance:** Low  
**Use:** Dashboard layouts, data overview

### 28. Card Hover Reveal Details

**What it looks like:** Hidden details slide up on card hover

```css
.card-reveal {
  position: relative;
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
}

.card-reveal-content {
  padding: 24px;
}

.card-reveal-details {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(10, 10, 10, 0.95);
  backdrop-filter: blur(10px);
  padding: 24px;
  transform: translateY(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.card-reveal:hover .card-reveal-details {
  transform: translateY(0);
}
```

**Browser support:** Chrome 4+, Safari 3.1+, Firefox 3.5+  
**Performance:** Low  
**Use:** Product cards, image galleries

---

## F. Buttons

### 29. Shimmer Sweep Button

**What it looks like:** Shimmer effect sweeps across button on hover

```css
.shimmer-button {
  position: relative;
  background: #0a0a0a;
  color: white;
  border: 1px solid rgba(255, 255, 255, 0.2);
  padding: 12px 24px;
  border-radius: 8px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.shimmer-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.2),
    transparent
```
