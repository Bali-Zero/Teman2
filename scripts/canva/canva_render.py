#!/usr/bin/env python3
"""
canva_render.py — KBLI 2025 Carousel Slides Generator
Generates 6 x 1080×1350px PNG slides using Playwright + inline HTML/CSS.
"""

from playwright.sync_api import sync_playwright
from pathlib import Path

OUTPUT = Path(__file__).parent / "output" / "kbli_2025"
OUTPUT.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# SLIDE 1 — HOOK
# ─────────────────────────────────────────────
html_slide_1 = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: 1080px; height: 1350px; overflow: hidden; font-family: 'Poppins', sans-serif; }
  .slide {
    width: 1080px;
    height: 1350px;
    background: linear-gradient(160deg, #1a1f24 0%, #2d3f4a 50%, #1a1f24 100%);
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  /* Noise/texture overlay */
  .slide::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
    pointer-events: none;
    z-index: 1;
  }
  /* Top decorative line */
  .top-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    background: linear-gradient(90deg, transparent, #d4a574, #e8c547, #d4a574, transparent);
    z-index: 10;
  }
  /* Image zone — golden Ganesh-vibe radial gradient */
  .image-zone {
    width: 680px;
    height: 780px;
    border-radius: 12px;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 60px rgba(0,0,0,0.7), 0 0 120px rgba(212,165,116,0.15);
    flex-shrink: 0;
  }
  .image-zone-inner {
    width: 100%;
    height: 100%;
    background:
      radial-gradient(ellipse 60% 70% at 50% 30%, rgba(232,197,71,0.25) 0%, transparent 60%),
      radial-gradient(ellipse 80% 60% at 50% 60%, rgba(212,165,116,0.18) 0%, transparent 55%),
      linear-gradient(180deg, #2a2010 0%, #1a1208 40%, #0d0d0d 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
  }
  /* Ganesh silhouette via layered CSS art */
  .ganesh {
    position: relative;
    width: 300px;
    height: 480px;
  }
  /* Head/halo */
  .ganesh-halo {
    position: absolute;
    top: 10px;
    left: 50%;
    transform: translateX(-50%);
    width: 200px;
    height: 200px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(232,197,71,0.6) 0%, rgba(212,165,116,0.3) 40%, transparent 70%);
    box-shadow: 0 0 60px rgba(232,197,71,0.4), 0 0 120px rgba(212,165,116,0.2);
  }
  .ganesh-head {
    position: absolute;
    top: 30px;
    left: 50%;
    transform: translateX(-50%);
    width: 130px;
    height: 145px;
    border-radius: 50% 50% 48% 48%;
    background: linear-gradient(160deg, #c8924a 0%, #8b5e2a 50%, #5a3510 100%);
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
  }
  /* Trunk */
  .ganesh-trunk {
    position: absolute;
    top: 145px;
    left: 50%;
    transform: translateX(-50%) rotate(-15deg);
    width: 38px;
    height: 100px;
    border-radius: 20px 20px 30px 30px;
    background: linear-gradient(160deg, #b8823a 0%, #7a4e1a 100%);
    transform-origin: top center;
  }
  /* Body */
  .ganesh-body {
    position: absolute;
    top: 155px;
    left: 50%;
    transform: translateX(-50%);
    width: 200px;
    height: 220px;
    border-radius: 40% 40% 48% 48%;
    background: linear-gradient(160deg, #b8823a 0%, #7a4e1a 60%, #4a2a08 100%);
    box-shadow: 0 4px 30px rgba(0,0,0,0.4);
  }
  /* Arms */
  .ganesh-arm-left {
    position: absolute;
    top: 175px;
    left: 20px;
    width: 55px;
    height: 130px;
    border-radius: 30px;
    background: linear-gradient(160deg, #c8924a 0%, #8b5e2a 100%);
    transform: rotate(25deg);
  }
  .ganesh-arm-right {
    position: absolute;
    top: 175px;
    right: 20px;
    width: 55px;
    height: 130px;
    border-radius: 30px;
    background: linear-gradient(160deg, #c8924a 0%, #8b5e2a 100%);
    transform: rotate(-25deg);
  }
  /* Gold ornament dots */
  .ornament {
    position: absolute;
    border-radius: 50%;
    background: #e8c547;
    box-shadow: 0 0 8px rgba(232,197,71,0.8);
  }
  /* Bottom gradient overlay on image */
  .image-overlay {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60%;
    background: linear-gradient(to top, rgba(26,31,36,0.95) 0%, rgba(26,31,36,0.6) 40%, transparent 100%);
  }
  /* Text overlay on image */
  .image-text {
    position: absolute;
    bottom: 40px;
    left: 40px;
    right: 40px;
    z-index: 5;
    text-align: left;
  }
  .eyebrow {
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 4px;
    color: #c84c5c;
    text-transform: uppercase;
    margin-bottom: 12px;
  }
  .main-title {
    font-size: 88px;
    font-weight: 900;
    color: #ffffff;
    line-height: 0.9;
    letter-spacing: -2px;
    text-shadow: 0 4px 30px rgba(0,0,0,0.8);
    margin-bottom: 20px;
  }
  .sub-title {
    font-size: 22px;
    font-weight: 500;
    color: #d4a574;
    line-height: 1.5;
    max-width: 540px;
  }
  /* Bottom section below image */
  .bottom-section {
    width: 100%;
    padding: 24px 60px 0;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    position: relative;
    z-index: 5;
  }
  .slide-num {
    font-size: 13px;
    font-weight: 600;
    color: #4a5a66;
    letter-spacing: 2px;
  }
  /* Bali Zero logo */
  .bz-logo {
    position: absolute;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%);
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    z-index: 20;
  }
  .bz-text-top {
    font-family: 'Poppins', sans-serif;
    font-size: 8.5px;
    font-weight: 800;
    color: #1a1f24;
    letter-spacing: 1px;
    line-height: 1;
  }
  .bz-divider {
    width: 28px;
    height: 1px;
    background: #2d3f4a;
    margin: 2px 0;
  }
  .bz-text-bottom {
    font-family: 'Poppins', sans-serif;
    font-size: 8.5px;
    font-weight: 800;
    color: #1a1f24;
    letter-spacing: 1px;
    line-height: 1;
  }
</style>
</head>
<body>
<div class="slide">
  <div class="top-bar"></div>

  <div class="image-zone">
    <div class="image-zone-inner">
      <div class="ganesh">
        <div class="ganesh-halo"></div>
        <div class="ganesh-head">
          <!-- ears -->
          <div style="position:absolute;top:30px;left:-22px;width:26px;height:42px;border-radius:50%;background:linear-gradient(160deg,#c8924a,#8b5e2a);"></div>
          <div style="position:absolute;top:30px;right:-22px;width:26px;height:42px;border-radius:50%;background:linear-gradient(160deg,#c8924a,#8b5e2a);"></div>
          <!-- crown -->
          <div style="position:absolute;top:-18px;left:50%;transform:translateX(-50%);width:80px;height:28px;background:linear-gradient(180deg,#e8c547,#c8924a);border-radius:6px 6px 0 0;"></div>
          <!-- eyes -->
          <div style="position:absolute;top:45px;left:24px;width:18px;height:18px;border-radius:50%;background:#1a1208;box-shadow:0 0 6px rgba(232,197,71,0.6);"></div>
          <div style="position:absolute;top:45px;right:24px;width:18px;height:18px;border-radius:50%;background:#1a1208;box-shadow:0 0 6px rgba(232,197,71,0.6);"></div>
          <!-- third eye -->
          <div style="position:absolute;top:38px;left:50%;transform:translateX(-50%);width:12px;height:12px;border-radius:50%;background:#e8c547;box-shadow:0 0 10px rgba(232,197,71,0.9);"></div>
        </div>
        <div class="ganesh-trunk"></div>
        <div class="ganesh-body">
          <!-- belly jewel -->
          <div style="position:absolute;top:60px;left:50%;transform:translateX(-50%);width:40px;height:40px;border-radius:50%;background:radial-gradient(circle,#e8c547,#c8924a);box-shadow:0 0 16px rgba(232,197,71,0.5);"></div>
        </div>
        <div class="ganesh-arm-left"></div>
        <div class="ganesh-arm-right"></div>
        <!-- lotus base -->
        <div style="position:absolute;bottom:0;left:50%;transform:translateX(-50%);width:240px;height:40px;border-radius:50%;background:linear-gradient(180deg,rgba(212,165,116,0.3),transparent);"></div>
      </div>
      <!-- ornament dots -->
      <div class="ornament" style="width:6px;height:6px;top:60px;left:80px;"></div>
      <div class="ornament" style="width:4px;height:4px;top:120px;right:90px;"></div>
      <div class="ornament" style="width:8px;height:8px;bottom:180px;left:60px;"></div>
      <div class="ornament" style="width:5px;height:5px;bottom:220px;right:70px;"></div>
    </div>
    <div class="image-overlay"></div>
    <div class="image-text">
      <div class="eyebrow">KBLI 2025</div>
      <div class="main-title">SLOW<br>PARALYSIS</div>
      <div class="sub-title">YOUR COMPANY WON'T DIE TODAY.<br>IT WILL JUST STOP MOVING.</div>
    </div>
  </div>

  <div class="bottom-section">
    <span class="slide-num">01 / 06</span>
    <span style="font-size:12px;font-weight:500;color:#4a5a66;letter-spacing:1px;">KBLI 2025 TRANSITION GUIDE</span>
  </div>

  <div class="bz-logo">
    <span class="bz-text-top">BALI</span>
    <div class="bz-divider"></div>
    <span class="bz-text-bottom">ZERO</span>
  </div>
</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# SLIDE 2 — NOT A CLIFF. A SWAMP.
# ─────────────────────────────────────────────
html_slide_2 = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: 1080px; height: 1350px; overflow: hidden; font-family: 'Poppins', sans-serif; }
  .slide {
    width: 1080px;
    height: 1350px;
    background: #2d3f4a;
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 60px 60px 80px;
    overflow: hidden;
  }
  /* Subtle background texture */
  .slide::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 80% 50% at 100% 0%, rgba(212,165,116,0.06) 0%, transparent 60%),
      radial-gradient(ellipse 60% 40% at 0% 100%, rgba(26,31,36,0.5) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
  }
  .top-bar {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, transparent, #c84c5c, transparent);
    z-index: 10;
  }
  .content { position: relative; z-index: 5; flex: 1; display: flex; flex-direction: column; }
  .label {
    display: inline-block;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 3px;
    color: #c84c5c;
    text-transform: uppercase;
    border: 1.5px solid rgba(200,76,92,0.4);
    padding: 6px 16px;
    border-radius: 4px;
    background: rgba(200,76,92,0.08);
    align-self: flex-start;
    margin-bottom: 28px;
  }
  .title {
    font-size: 38px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.2;
    margin-bottom: 50px;
    max-width: 780px;
    letter-spacing: -0.5px;
  }
  .bullets {
    display: flex;
    flex-direction: column;
    gap: 22px;
    flex: 1;
  }
  .bullet {
    display: flex;
    align-items: stretch;
    gap: 0;
    border-radius: 6px;
    background: rgba(255,255,255,0.03);
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    transition: all 0.2s;
  }
  .bullet-bar {
    width: 5px;
    background: linear-gradient(180deg, #e8c547, #d4a574);
    flex-shrink: 0;
  }
  .bullet-inner {
    padding: 26px 30px;
    flex: 1;
  }
  .bullet-text {
    font-size: 20px;
    font-weight: 500;
    color: #e8e8e8;
    line-height: 1.5;
    letter-spacing: 0.2px;
  }
  .bullet-text.highlight {
    color: #d4a574;
    font-weight: 700;
    font-size: 21px;
  }
  .bullet-number {
    font-size: 12px;
    font-weight: 700;
    color: #d4a574;
    letter-spacing: 1px;
    margin-bottom: 8px;
    opacity: 0.7;
  }
  .bz-logo {
    position: absolute;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%);
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    z-index: 20;
  }
  .bz-text-top { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .bz-divider { width: 28px; height: 1px; background: #2d3f4a; margin: 2px 0; }
  .bz-text-bottom { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .slide-num {
    position: absolute;
    bottom: 38px;
    right: 60px;
    font-size: 13px;
    font-weight: 600;
    color: #3d5060;
    letter-spacing: 2px;
    z-index: 20;
  }
</style>
</head>
<body>
<div class="slide">
  <div class="top-bar"></div>
  <div class="content">
    <div class="label">NOT A CLIFF. A SWAMP.</div>
    <div class="title">THE KBLI 2025 TRANSITION ISN'T A SUDDEN SHUTDOWN.</div>

    <div class="bullets">
      <div class="bullet">
        <div class="bullet-bar"></div>
        <div class="bullet-inner">
          <div class="bullet-number">01</div>
          <div class="bullet-text">BKPM HAS CONFIRMED: EXISTING PERMITS STAY VALID FOR NOW.</div>
        </div>
      </div>

      <div class="bullet">
        <div class="bullet-bar"></div>
        <div class="bullet-inner">
          <div class="bullet-number">02</div>
          <div class="bullet-text">BUT 'VALID' DOESN'T MEAN 'FUNCTIONAL'.</div>
        </div>
      </div>

      <div class="bullet">
        <div class="bullet-bar"></div>
        <div class="bullet-inner">
          <div class="bullet-number">03</div>
          <div class="bullet-text">THE OPERATIONAL BLOCKS ARE ALREADY STACKING UP. IT'S NOT A CRASH.</div>
        </div>
      </div>

      <div class="bullet">
        <div class="bullet-bar" style="background: linear-gradient(180deg, #d4a574, #c8924a);"></div>
        <div class="bullet-inner" style="background: rgba(212,165,116,0.06);">
          <div class="bullet-number" style="color:#e8c547;">04</div>
          <div class="bullet-text highlight">IT'S A SLOW, SILENT WITHDRAWAL OF YOUR ABILITY TO OPERATE.</div>
        </div>
      </div>
    </div>
  </div>

  <div class="bz-logo">
    <span class="bz-text-top">BALI</span>
    <div class="bz-divider"></div>
    <span class="bz-text-bottom">ZERO</span>
  </div>
  <div class="slide-num">02 / 06</div>
</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# SLIDE 3 — THE SYMPTOMS
# ─────────────────────────────────────────────
html_slide_3 = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: 1080px; height: 1350px; overflow: hidden; font-family: 'Poppins', sans-serif; }
  .slide {
    width: 1080px;
    height: 1350px;
    background: #1a1f24;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 70px 60px 90px;
    overflow: hidden;
  }
  .slide::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 70% 40% at 50% 0%, rgba(200,76,92,0.08) 0%, transparent 60%),
      radial-gradient(ellipse 60% 40% at 50% 100%, rgba(26,31,36,0.8) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
  }
  .top-bar {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, transparent, #c84c5c, #d4a574, #c84c5c, transparent);
    z-index: 10;
  }
  .content {
    position: relative;
    z-index: 5;
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .title-wrap {
    text-align: center;
    margin-bottom: 52px;
  }
  .eyebrow-label {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 4px;
    color: #c84c5c;
    text-transform: uppercase;
    margin-bottom: 12px;
  }
  .title {
    font-size: 56px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -1px;
    line-height: 1;
  }
  .title-underline {
    width: 80px;
    height: 4px;
    background: linear-gradient(90deg, #c84c5c, #d4a574);
    border-radius: 2px;
    margin: 18px auto 0;
  }
  .symptoms {
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 18px;
    flex: 1;
  }
  .symptom-row {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 8px;
    padding: 28px 32px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    position: relative;
    overflow: hidden;
  }
  .symptom-row::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%;
    height: 2px;
    background: linear-gradient(90deg, rgba(200,76,92,0.6), transparent);
  }
  .symptom-keyword {
    font-size: 14px;
    font-weight: 800;
    color: #c84c5c;
    letter-spacing: 3px;
    text-transform: uppercase;
  }
  .symptom-desc {
    font-size: 22px;
    font-weight: 600;
    color: #ffffff;
    line-height: 1.3;
    letter-spacing: 0.3px;
  }
  .symptom-icon {
    position: absolute;
    right: 28px;
    top: 50%;
    transform: translateY(-50%);
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: rgba(200,76,92,0.12);
    border: 1.5px solid rgba(200,76,92,0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
  }
  .bottom-punch {
    margin-top: 32px;
    text-align: center;
    font-size: 26px;
    font-weight: 700;
    color: #d4a574;
    letter-spacing: 1px;
    padding: 20px 40px;
    border-top: 1px solid rgba(212,165,116,0.2);
    width: 100%;
  }
  .bz-logo {
    position: absolute;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%);
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    z-index: 20;
  }
  .bz-text-top { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .bz-divider { width: 28px; height: 1px; background: #2d3f4a; margin: 2px 0; }
  .bz-text-bottom { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .slide-num {
    position: absolute;
    bottom: 38px;
    right: 60px;
    font-size: 13px;
    font-weight: 600;
    color: #3d5060;
    letter-spacing: 2px;
    z-index: 20;
  }
</style>
</head>
<body>
<div class="slide">
  <div class="top-bar"></div>
  <div class="content">
    <div class="title-wrap">
      <div class="eyebrow-label">WHAT YOU WILL EXPERIENCE</div>
      <div class="title">THE SYMPTOMS</div>
      <div class="title-underline"></div>
    </div>

    <div class="symptoms">
      <div class="symptom-row">
        <div class="symptom-keyword">NIB STATUS:</div>
        <div class="symptom-desc">FLAGGED AS 'INCOMPATIBLE' WITH 2025 CODES</div>
        <div class="symptom-icon">⚠</div>
      </div>

      <div class="symptom-row">
        <div class="symptom-keyword">LICENSE RENEWALS:</div>
        <div class="symptom-desc">BLOCKED. YOUR KBLI REFERENCE NO LONGER EXISTS.</div>
        <div class="symptom-icon">✕</div>
      </div>

      <div class="symptom-row">
        <div class="symptom-keyword">KITAS PERMITS:</div>
        <div class="symptom-desc">STUCK. OSS-IMMIGRATION SYNC FAILS.</div>
        <div class="symptom-icon">⏸</div>
      </div>

      <div class="symptom-row">
        <div class="symptom-keyword">LKPM REPORTS:</div>
        <div class="symptom-desc">REJECTED. CODE MISMATCH.</div>
        <div class="symptom-icon">✕</div>
      </div>
    </div>

    <div class="bottom-punch">THEY JUST STOP PROCESSING.</div>
  </div>

  <div class="bz-logo">
    <span class="bz-text-top">BALI</span>
    <div class="bz-divider"></div>
    <span class="bz-text-bottom">ZERO</span>
  </div>
  <div class="slide-num">03 / 06</div>
</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# SLIDE 4 — THE REAL TIMELINE
# ─────────────────────────────────────────────
html_slide_4 = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: 1080px; height: 1350px; overflow: hidden; font-family: 'Poppins', sans-serif; }
  .slide {
    width: 1080px;
    height: 1350px;
    background: #2d3f4a;
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 60px 60px 90px;
    overflow: hidden;
  }
  .slide::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 80% 50% at 0% 100%, rgba(26,31,36,0.6) 0%, transparent 60%),
      radial-gradient(ellipse 60% 40% at 100% 0%, rgba(232,197,71,0.04) 0%, transparent 60%);
    pointer-events: none;
    z-index: 0;
  }
  .top-bar {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, transparent, #e8c547, transparent);
    z-index: 10;
  }
  /* Vertical timeline line */
  .timeline-line {
    position: absolute;
    left: 117px;
    top: 195px;
    bottom: 200px;
    width: 2px;
    background: linear-gradient(180deg, rgba(232,197,71,0.8) 0%, rgba(212,165,116,0.3) 80%, transparent 100%);
    z-index: 2;
  }
  .content {
    position: relative;
    z-index: 5;
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .header {
    margin-bottom: 44px;
  }
  .eyebrow-label {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 4px;
    color: #e8c547;
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .title {
    font-size: 46px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -1px;
    line-height: 1;
  }
  .timeline {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0;
    padding-left: 0;
  }
  .timeline-item {
    display: flex;
    align-items: flex-start;
    gap: 0;
    position: relative;
    padding-bottom: 30px;
  }
  .timeline-left {
    width: 110px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 4px;
  }
  .timeline-dot {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: linear-gradient(135deg, #e8c547, #d4a574);
    box-shadow: 0 0 16px rgba(232,197,71,0.5);
    flex-shrink: 0;
    z-index: 3;
  }
  .timeline-month {
    font-size: 10px;
    font-weight: 800;
    color: #e8c547;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-top: 6px;
    text-align: center;
  }
  .timeline-right {
    flex: 1;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 8px;
    padding: 20px 24px;
    margin-left: 20px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  }
  .timeline-text {
    font-size: 18px;
    font-weight: 500;
    color: #e0e0e0;
    line-height: 1.4;
    letter-spacing: 0.2px;
  }
  .bottom-punch {
    margin-top: 18px;
    padding: 22px 30px;
    background: rgba(200,76,92,0.1);
    border: 1.5px solid rgba(200,76,92,0.3);
    border-radius: 8px;
    text-align: center;
    font-size: 30px;
    font-weight: 800;
    color: #c84c5c;
    letter-spacing: 2px;
    box-shadow: 0 4px 20px rgba(200,76,92,0.15);
  }
  .bz-logo {
    position: absolute;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%);
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    z-index: 20;
  }
  .bz-text-top { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .bz-divider { width: 28px; height: 1px; background: #2d3f4a; margin: 2px 0; }
  .bz-text-bottom { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .slide-num {
    position: absolute;
    bottom: 38px;
    right: 60px;
    font-size: 13px;
    font-weight: 600;
    color: #3d5060;
    letter-spacing: 2px;
    z-index: 20;
  }
</style>
</head>
<body>
<div class="slide">
  <div class="top-bar"></div>
  <div class="timeline-line"></div>
  <div class="content">
    <div class="header">
      <div class="eyebrow-label">WHAT ACTUALLY HAPPENS</div>
      <div class="title">THE REAL TIMELINE</div>
    </div>

    <div class="timeline">
      <div class="timeline-item">
        <div class="timeline-left">
          <div class="timeline-dot"></div>
          <div class="timeline-month">MONTH<br>1</div>
        </div>
        <div class="timeline-right">
          <div class="timeline-text">YOU TRY TO RENEW YOUR ALCOHOL LICENSE.<br>SYSTEM SAYS <span style="color:#e8c547;font-weight:700;">'PENDING'.</span></div>
        </div>
      </div>

      <div class="timeline-item">
        <div class="timeline-left">
          <div class="timeline-dot"></div>
          <div class="timeline-month">MONTH<br>2</div>
        </div>
        <div class="timeline-right">
          <div class="timeline-text">YOUR ACCOUNTANT SUBMITS LKPM.<br><span style="color:#c84c5c;font-weight:700;">REJECTED. CODE MISMATCH.</span></div>
        </div>
      </div>

      <div class="timeline-item">
        <div class="timeline-left">
          <div class="timeline-dot"></div>
          <div class="timeline-month">MONTH<br>3</div>
        </div>
        <div class="timeline-right">
          <div class="timeline-text">HR APPLIES FOR STAFF KITAS RENEWAL.<br><span style="color:#c84c5c;font-weight:700;">PORTAL RETURNS ERROR.</span></div>
        </div>
      </div>

      <div class="timeline-item" style="padding-bottom:0;">
        <div class="timeline-left">
          <div class="timeline-dot" style="background: linear-gradient(135deg, #c84c5c, #9a2a3a); box-shadow: 0 0 16px rgba(200,76,92,0.5);"></div>
          <div class="timeline-month" style="color:#c84c5c;">MONTH<br>5</div>
        </div>
        <div class="timeline-right" style="border-color: rgba(200,76,92,0.2); background: rgba(200,76,92,0.05);">
          <div class="timeline-text">YOU CALL YOUR LAWYER.<br><span style="color:#c84c5c;font-weight:700;">THE AMENDMENT QUEUE IS 8 WEEKS.</span></div>
        </div>
      </div>
    </div>

    <div class="bottom-punch">THIS IS SLOW PARALYSIS.</div>
  </div>

  <div class="bz-logo">
    <span class="bz-text-top">BALI</span>
    <div class="bz-divider"></div>
    <span class="bz-text-bottom">ZERO</span>
  </div>
  <div class="slide-num">04 / 06</div>
</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# SLIDE 5 — THE DOMINO YOU DON'T SEE
# ─────────────────────────────────────────────
html_slide_5 = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: 1080px; height: 1350px; overflow: hidden; font-family: 'Poppins', sans-serif; }
  .slide {
    width: 1080px;
    height: 1350px;
    background: #1a1f24;
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 60px 60px 90px;
    overflow: hidden;
  }
  .slide::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 70% 40% at 50% 100%, rgba(232,197,71,0.05) 0%, transparent 60%),
      radial-gradient(ellipse 80% 40% at 0% 0%, rgba(26,31,36,0.6) 0%, transparent 50%);
    pointer-events: none;
    z-index: 0;
  }
  .top-bar {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, transparent, #e8c547, transparent);
    z-index: 10;
  }
  .content {
    position: relative;
    z-index: 5;
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .header {
    margin-bottom: 40px;
  }
  .eyebrow-label {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 4px;
    color: #d4a574;
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .title {
    font-size: 44px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -1px;
    line-height: 1.1;
    max-width: 700px;
  }
  /* Domino chain */
  .domino-chain {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    margin: 36px 0;
    flex-wrap: nowrap;
  }
  .domino-box {
    background: rgba(255,255,255,0.06);
    border: 1.5px solid rgba(232,197,71,0.25);
    border-radius: 8px;
    padding: 18px 16px;
    text-align: center;
    min-width: 185px;
    flex: 1;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4), 0 0 20px rgba(232,197,71,0.06);
  }
  .domino-num {
    font-size: 11px;
    font-weight: 700;
    color: #e8c547;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .domino-label {
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 0.5px;
    line-height: 1.2;
  }
  .domino-arrow {
    color: #d4a574;
    font-size: 26px;
    font-weight: 300;
    flex-shrink: 0;
    padding: 0 6px;
    align-self: center;
  }
  .subtitle-line {
    font-size: 20px;
    font-weight: 400;
    color: #a0a0a0;
    text-align: center;
    margin-bottom: 36px;
    font-style: italic;
  }
  .big-action {
    background: rgba(232,197,71,0.08);
    border: 2px solid rgba(232,197,71,0.3);
    border-radius: 10px;
    padding: 32px 36px;
    margin-bottom: 28px;
    box-shadow: 0 4px 30px rgba(232,197,71,0.1);
  }
  .action-step {
    display: flex;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 18px;
  }
  .action-step:last-child { margin-bottom: 0; }
  .step-badge {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: rgba(232,197,71,0.2);
    border: 1.5px solid rgba(232,197,71,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 800;
    color: #e8c547;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .action-text {
    font-size: 21px;
    font-weight: 700;
    color: #e8c547;
    line-height: 1.3;
    letter-spacing: 0.3px;
  }
  .bottom-conclusion {
    background: rgba(255,255,255,0.03);
    border-left: 4px solid #d4a574;
    border-radius: 0 6px 6px 0;
    padding: 20px 24px;
    font-size: 17px;
    font-weight: 500;
    color: #c0c0c0;
    line-height: 1.5;
    flex: 1;
  }
  .bz-logo {
    position: absolute;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%);
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    z-index: 20;
  }
  .bz-text-top { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .bz-divider { width: 28px; height: 1px; background: #2d3f4a; margin: 2px 0; }
  .bz-text-bottom { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .slide-num {
    position: absolute;
    bottom: 38px;
    right: 60px;
    font-size: 13px;
    font-weight: 600;
    color: #3d5060;
    letter-spacing: 2px;
    z-index: 20;
  }
</style>
</head>
<body>
<div class="slide">
  <div class="top-bar"></div>
  <div class="content">
    <div class="header">
      <div class="eyebrow-label">THE CHAIN REACTION</div>
      <div class="title">THE DOMINO YOU DON'T SEE</div>
    </div>

    <div class="domino-chain">
      <div class="domino-box">
        <div class="domino-num">STEP 1</div>
        <div class="domino-label">NOTARIAL<br>DEED</div>
      </div>
      <div class="domino-arrow">→</div>
      <div class="domino-box">
        <div class="domino-num">STEP 2</div>
        <div class="domino-label">AHU<br>FILING</div>
      </div>
      <div class="domino-arrow">→</div>
      <div class="domino-box">
        <div class="domino-num">STEP 3</div>
        <div class="domino-label">OSS<br>SYNC</div>
      </div>
      <div class="domino-arrow">→</div>
      <div class="domino-box">
        <div class="domino-num">STEP 4</div>
        <div class="domino-label">LICENSE<br>CHECK</div>
      </div>
    </div>

    <div class="subtitle-line">EACH STEP HAS A QUEUE. EACH QUEUE HAS A BOTTLENECK.</div>

    <div class="big-action">
      <div class="action-step">
        <div class="step-badge">1</div>
        <div class="action-text">AUDITING YOUR CODES</div>
      </div>
      <div style="width:100%;height:1px;background:rgba(232,197,71,0.15);margin: 8px 0 18px 52px;"></div>
      <div class="action-step">
        <div class="step-badge">2</div>
        <div class="action-text">AMENDING YOUR AKTA</div>
      </div>
      <div style="margin-top:16px;margin-left:52px;">
        <span style="font-size:17px;font-weight:600;color:rgba(232,197,71,0.7);">CAN START RIGHT NOW.</span>
      </div>
    </div>

    <div class="bottom-conclusion">
      THE BUSINESSES THAT PREPARE <span style="color:#ffffff;font-weight:700;">BEFORE THE SWITCH</span> WILL MIGRATE IN <span style="color:#e8c547;font-weight:700;">DAYS</span>.<br>THE REST WILL <span style="color:#c84c5c;font-weight:700;">WAIT MONTHS</span>.
    </div>
  </div>

  <div class="bz-logo">
    <span class="bz-text-top">BALI</span>
    <div class="bz-divider"></div>
    <span class="bz-text-bottom">ZERO</span>
  </div>
  <div class="slide-num">05 / 06</div>
</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# SLIDE 6 — CTA
# ─────────────────────────────────────────────
html_slide_6 = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { width: 1080px; height: 1350px; overflow: hidden; font-family: 'Poppins', sans-serif; }
  .slide {
    width: 1080px;
    height: 1350px;
    background: #1a1f24;
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 70px 60px 100px;
    overflow: hidden;
  }
  /* Gold top gradient accent */
  .slide::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 300px;
    background: linear-gradient(180deg,
      rgba(232,197,71,0.12) 0%,
      rgba(212,165,116,0.06) 40%,
      transparent 100%
    );
    pointer-events: none;
    z-index: 0;
  }
  .slide::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 200px;
    background: linear-gradient(0deg, rgba(0,0,0,0.4) 0%, transparent 100%);
    pointer-events: none;
    z-index: 0;
  }
  .top-bar {
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: linear-gradient(90deg, transparent, #e8c547, #d4a574, #e8c547, transparent);
    z-index: 10;
  }
  .content {
    position: relative;
    z-index: 5;
    width: 100%;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .title-section {
    text-align: center;
    margin-bottom: 18px;
  }
  .eyebrow-label {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 4px;
    color: #e8c547;
    text-transform: uppercase;
    margin-bottom: 16px;
  }
  .title {
    font-size: 52px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -1px;
    line-height: 1.1;
    text-align: center;
  }
  .subtitle {
    font-size: 24px;
    font-weight: 400;
    color: #a0a0a0;
    text-align: center;
    margin-top: 14px;
    margin-bottom: 44px;
  }
  /* URL Button */
  .url-button {
    border: 2.5px solid #d4a574;
    border-radius: 10px;
    padding: 28px 48px;
    text-align: center;
    width: 100%;
    margin-bottom: 44px;
    background: rgba(212,165,116,0.07);
    box-shadow: 0 4px 40px rgba(212,165,116,0.15), inset 0 1px 0 rgba(255,255,255,0.05);
    position: relative;
    overflow: hidden;
  }
  .url-button::before {
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(232,197,71,0.06), transparent);
    animation: shimmer 3s infinite;
  }
  @keyframes shimmer { to { left: 200%; } }
  .url-label {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 3px;
    color: #d4a574;
    text-transform: uppercase;
    margin-bottom: 10px;
    opacity: 0.7;
  }
  .url-text {
    font-size: 30px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 1px;
  }
  /* Mock App Card */
  .app-card {
    width: 100%;
    background: #242c33;
    border-radius: 12px;
    padding: 28px 30px;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05);
    margin-bottom: 16px;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  .app-card-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  .app-card-badge {
    display: inline-block;
    background: rgba(200,76,92,0.2);
    border: 1px solid rgba(200,76,92,0.4);
    color: #c84c5c;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 5px 12px;
    border-radius: 4px;
    text-transform: uppercase;
  }
  .app-card-stars {
    display: flex;
    gap: 3px;
    align-items: center;
  }
  .star {
    color: #e8c547;
    font-size: 18px;
  }
  .star-count {
    font-size: 13px;
    color: #a0a0a0;
    margin-left: 4px;
    font-weight: 500;
  }
  .app-card-title {
    font-size: 28px;
    font-weight: 800;
    color: #ffffff;
    line-height: 1.2;
    margin-bottom: 12px;
  }
  .app-card-desc {
    font-size: 16px;
    font-weight: 400;
    color: #7a8a96;
    line-height: 1.5;
  }
  .app-card-bottom {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 24px;
    padding-top: 20px;
    border-top: 1px solid rgba(255,255,255,0.06);
  }
  .app-tag {
    background: rgba(232,197,71,0.1);
    border: 1px solid rgba(232,197,71,0.25);
    color: #d4a574;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 14px;
    border-radius: 20px;
    letter-spacing: 0.5px;
  }
  .app-cta-btn {
    background: linear-gradient(135deg, #d4a574, #c8924a);
    color: #1a1208;
    font-size: 14px;
    font-weight: 800;
    padding: 10px 22px;
    border-radius: 6px;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .bz-logo {
    position: absolute;
    bottom: 32px;
    left: 50%;
    transform: translateX(-50%);
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    z-index: 20;
  }
  .bz-text-top { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .bz-divider { width: 28px; height: 1px; background: #2d3f4a; margin: 2px 0; }
  .bz-text-bottom { font-size: 8.5px; font-weight: 800; color: #1a1f24; letter-spacing: 1px; line-height: 1; }
  .slide-num {
    position: absolute;
    bottom: 38px;
    right: 60px;
    font-size: 13px;
    font-weight: 600;
    color: #3d5060;
    letter-spacing: 2px;
    z-index: 20;
  }
</style>
</head>
<body>
<div class="slide">
  <div class="top-bar"></div>
  <div class="content">
    <div class="title-section">
      <div class="eyebrow-label">FREE TOOL — ACT NOW</div>
      <div class="title">IS YOUR KBLI CODE<br>STILL VALID?</div>
    </div>

    <div class="subtitle">WE BUILT A FREE APP FOR YOU.</div>

    <div class="url-button">
      <div class="url-label">CHECK NOW AT</div>
      <div class="url-text">BALIZERO.COM/KBLI-NAVIGATOR</div>
    </div>

    <div class="app-card">
      <div>
        <div class="app-card-top">
          <div class="app-card-badge">KBLI 2025</div>
          <div class="app-card-stars">
            <span class="star">★</span>
            <span class="star">★</span>
            <span class="star">★</span>
            <span class="star">★</span>
            <span class="star">★</span>
            <span class="star-count">4.9 (128 reviews)</span>
          </div>
        </div>
        <div class="app-card-title">YOUR GUIDE TO INDONESIAN<br>BUSINESS CODES</div>
        <div class="app-card-desc">
          Search any KBLI code. Instant 2025 compliance check.<br>
          Know if your NIB is at risk — before OSS flags it.
        </div>
      </div>

      <div style="margin-top:20px;">
        <!-- Fake search bar -->
        <div style="background:#1a1f24;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:14px 20px;display:flex;align-items:center;gap:12px;margin-bottom:14px;">
          <div style="width:20px;height:20px;border-radius:50%;border:2px solid #4a5a66;flex-shrink:0;"></div>
          <div style="font-size:15px;color:#4a5a66;font-weight:400;letter-spacing:0.5px;">Search KBLI code or business type...</div>
        </div>
        <!-- Fake result pill -->
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          <div style="background:rgba(232,197,71,0.1);border:1px solid rgba(232,197,71,0.2);border-radius:6px;padding:8px 16px;font-size:13px;color:#d4a574;font-weight:600;">55110 — Hotel</div>
          <div style="background:rgba(200,76,92,0.1);border:1px solid rgba(200,76,92,0.2);border-radius:6px;padding:8px 16px;font-size:13px;color:#c84c5c;font-weight:600;">47911 — E-commerce</div>
          <div style="background:rgba(212,165,116,0.08);border:1px solid rgba(212,165,116,0.15);border-radius:6px;padding:8px 16px;font-size:13px;color:#a0a0a0;font-weight:500;">68100 — Real Estate</div>
        </div>
      </div>

      <div class="app-card-bottom">
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <div class="app-tag">FREE TOOL</div>
          <div class="app-tag">1,563 CODES</div>
          <div class="app-tag">UPDATED 2025</div>
        </div>
        <div class="app-cta-btn">TRY NOW →</div>
      </div>
    </div>
  </div>

  <div class="bz-logo">
    <span class="bz-text-top">BALI</span>
    <div class="bz-divider"></div>
    <span class="bz-text-bottom">ZERO</span>
  </div>
  <div class="slide-num">06 / 06</div>
</div>
</body>
</html>"""

# ─────────────────────────────────────────────
# SLIDES MANIFEST
# ─────────────────────────────────────────────
SLIDES = [
    ("slide_01", html_slide_1),
    ("slide_02", html_slide_2),
    ("slide_03", html_slide_3),
    ("slide_04", html_slide_4),
    ("slide_05", html_slide_5),
    ("slide_06", html_slide_6),
]


def render_slides() -> None:
    print(f"\nRendering {len(SLIDES)} slides to: {OUTPUT}\n")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for name, html in SLIDES:
            page.set_content(html, wait_until="networkidle")
            path = OUTPUT / f"{name}.png"
            page.screenshot(path=str(path), full_page=False)
            print(f"  {name}.png  ->  {path}")
        browser.close()
    print(f"\nDone. {len(SLIDES)} slides saved to {OUTPUT}\n")


if __name__ == "__main__":
    render_slides()
