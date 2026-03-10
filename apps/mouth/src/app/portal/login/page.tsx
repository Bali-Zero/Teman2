"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

export default function PortalLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [pin, setPin] = useState("");
  const [step, setStep] = useState<"email" | "pin">("email");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmitEmail = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) setStep("pin");
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      await api.login(email, pin);
      router.push("/portal");
    } catch {
      toast.error("Login failed", { description: "Invalid email or PIN" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className="min-h-screen relative overflow-hidden flex flex-col"
      style={{ background: "#000000" }}
    >
      {/* ─────────────────────────────────────────────
          LAYER 0 — Pure black starfield background
      ───────────────────────────────────────────── */}
      <div className="absolute inset-0">
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 1440 900"
          preserveAspectRatio="xMidYMid slice"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            {/* Pure black sky — no color tint */}
            <linearGradient id="skyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#000000" />
              <stop offset="70%" stopColor="#000000" />
              <stop offset="100%" stopColor="#050507" />
            </linearGradient>

            {/* Gold stroke gradients — bright at top, fading down */}
            <linearGradient id="goldEdge" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#f5e098" stopOpacity="1" />
              <stop offset="30%" stopColor="#e8c96a" stopOpacity="0.95" />
              <stop offset="70%" stopColor="#c9a96e" stopOpacity="0.7" />
              <stop offset="100%" stopColor="#8a6030" stopOpacity="0.35" />
            </linearGradient>

            {/* Inner side gold for pillar faces */}
            <linearGradient id="goldInner" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#ffd97a" stopOpacity="0.6" />
              <stop offset="40%" stopColor="#c9a96e" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#8a6030" stopOpacity="0.1" />
            </linearGradient>

            {/* Gate ambient glow — deep gold pool at base */}
            <radialGradient id="gateGlow" cx="50%" cy="80%" r="45%">
              <stop offset="0%" stopColor="#c9a96e" stopOpacity="0.28" />
              <stop offset="50%" stopColor="#c9a96e" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#c9a96e" stopOpacity="0" />
            </radialGradient>

            {/* Passage inner glow — light coming through */}
            <radialGradient id="passageGlow" cx="50%" cy="40%" r="50%">
              <stop offset="0%" stopColor="#1a1008" stopOpacity="1" />
              <stop offset="60%" stopColor="#0a0806" stopOpacity="1" />
              <stop offset="100%" stopColor="#000000" stopOpacity="1" />
            </radialGradient>

            {/* Halo behind logo */}
            <radialGradient id="logoHalo" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#c9a96e" stopOpacity="0.35" />
              <stop offset="60%" stopColor="#c9a96e" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#c9a96e" stopOpacity="0" />
            </radialGradient>

            {/* Glow filter for gold edges */}
            <filter id="goldGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Strong glow for ornament tips */}
            <filter id="tipGlow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            {/* Soft pillar glow */}
            <filter id="pillarGlow" x="-5%" y="-2%" width="110%" height="104%">
              <feGaussianBlur stdDeviation="1.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* ── BACKGROUND ── */}
          <rect width="1440" height="900" fill="url(#skyGrad)" />

          {/* ── STARS — layered density ── */}
          {/* Distant tiny stars */}
          {[
            [88,45],[144,72],[201,28],[267,91],[312,55],[389,38],[445,82],[501,19],[563,66],
            [618,33],[674,77],[729,44],[785,88],[841,22],[897,67],[953,41],[1009,79],[1065,31],
            [1121,58],[1177,84],[1233,47],[1289,73],[1345,26],[1401,62],[1430,89],
            [110,140],[178,163],[244,128],[310,157],[376,134],[442,169],[508,142],[574,118],
            [640,155],[706,131],[772,148],[838,122],[904,159],[970,136],[1036,152],[1102,127],
            [1168,144],[1234,161],[1300,129],[1366,156],[1420,143],
            [55,220],[123,248],[191,235],[259,212],[327,244],[395,228],[463,241],[531,217],
            [599,238],[667,223],[735,245],[803,219],[871,236],[939,251],[1007,224],[1075,242],
            [1143,229],[1211,246],[1279,213],[1347,240],[1415,227],
          ].map(([x, y], i) => (
            <circle key={`s1-${i}`} cx={x} cy={y} r={0.5 + (i % 3) * 0.2}
              fill="#ffffff" opacity={0.15 + (i % 7) * 0.06} />
          ))}

          {/* Mid stars — slightly brighter */}
          {[
            [170,52],[320,38],[470,62],[620,29],[820,51],[970,35],[1120,58],[1290,42],
            [245,155],[415,131],[565,168],[715,144],[915,162],[1065,138],[1215,155],[1385,169],
            [140,285],[380,271],[580,294],[780,268],[980,289],[1180,275],[1380,292],
          ].map(([x, y], i) => (
            <circle key={`s2-${i}`} cx={x} cy={y} r={0.8 + (i % 2) * 0.4}
              fill="#f5e8c0" opacity={0.25 + (i % 5) * 0.08} />
          ))}

          {/* Bright foreground stars with cross-glint */}
          {[
            [180,88],[520,45],[860,72],[1200,55],[350,195],[750,168],[1100,182],
          ].map(([x, y], i) => (
            <g key={`sg-${i}`}>
              <circle cx={x} cy={y} r={1.4} fill="#fffbe8" opacity={0.7} />
              <line x1={x - 4} y1={y} x2={x + 4} y2={y} stroke="#fffbe8" strokeWidth="0.4" opacity={0.4} />
              <line x1={x} y1={y - 4} x2={x} y2={y + 4} stroke="#fffbe8" strokeWidth="0.4" opacity={0.4} />
            </g>
          ))}

          {/* ── MOON — crescent, upper left ── */}
          <circle cx="200" cy="110" r="48" fill="#0a0a0a" />
          <circle cx="218" cy="96" r="48" fill="#000000" />
          <circle cx="200" cy="110" r="47" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.3" />

          {/* ── AMBIENT GATE GLOW ── */}
          <ellipse cx="720" cy="820" rx="380" ry="160" fill="url(#gateGlow)" />

          {/* ═══════════════════════════════════════════
              AUTHENTIC CANDI BENTAR (BALINESE SPLIT GATE)
              Based on Pura Besakih / Tanah Lot proportions
              Two mirrored halves split down the center
          ═══════════════════════════════════════════ */}

          {/* ── LEFT HALF OF GATE ── */}
          <g filter="url(#pillarGlow)">

            {/* Main body — left tower */}
            <path
              d="M 510 780
                 L 510 430
                 L 535 410
                 L 535 390
                 L 545 375
                 L 560 365
                 L 620 365
                 L 640 380
                 L 640 780
                 Z"
              fill="#0a0804"
              stroke="url(#goldEdge)"
              strokeWidth="1.5"
            />

            {/* Left tower — outer edge bright gold line */}
            <line x1="510" y1="430" x2="510" y2="780"
              stroke="#f5e098" strokeWidth="2" opacity="0.85" />

            {/* Left tower — inner edge (facing center gap) */}
            <line x1="640" y1="380" x2="640" y2="780"
              stroke="#e8c96a" strokeWidth="1.5" opacity="0.7" />

            {/* Horizontal bands — Balinese paras stone layers */}
            {[410, 445, 480, 515, 550, 585, 620, 655, 690, 725, 760].map((y, i) => (
              <g key={`lb-${i}`}>
                <rect x="510" y={y} width="130" height="2"
                  fill="#c9a96e" opacity={0.18 + (i % 3) * 0.06} />
                <line x1="510" y1={y} x2="640" y2={y}
                  stroke="#e8c96a" strokeWidth="0.5" opacity={0.12} />
              </g>
            ))}

            {/* Left tower — decorative carved panels (pepalihan) */}
            <rect x="518" y="440" width="114" height="90" rx="1"
              fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.25" />
            <rect x="518" y="545" width="114" height="90" rx="1"
              fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.25" />
            <rect x="518" y="650" width="114" height="90" rx="1"
              fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.25" />

            {/* Lotus petal relief on panels */}
            <path d="M 575 465 Q 565 480 575 495 Q 585 480 575 465 Z"
              fill="#c9a96e" opacity="0.2" />
            <path d="M 575 570 Q 565 585 575 600 Q 585 585 575 570 Z"
              fill="#c9a96e" opacity="0.2" />
            <path d="M 575 675 Q 565 690 575 700 Q 585 690 575 675 Z"
              fill="#c9a96e" opacity="0.2" />

            {/* ── LEFT ARCH — stepped Meru tiers going up ── */}

            {/* Tier 1 — base of arch (widest) */}
            <path d="M 500 390 L 640 390 L 640 375 L 555 375 L 545 360 L 500 360 Z"
              fill="#0c0a05"
              stroke="#e8c96a" strokeWidth="1.2" opacity="0.9" />
            <line x1="500" y1="360" x2="500" y2="390"
              stroke="#f5e098" strokeWidth="2" opacity="0.9" />

            {/* Tier 2 */}
            <path d="M 508 360 L 640 360 L 640 346 L 562 346 L 552 332 L 508 332 Z"
              fill="#0c0a05"
              stroke="#e8c96a" strokeWidth="1.1" opacity="0.85" />
            <line x1="508" y1="332" x2="508" y2="360"
              stroke="#f5e098" strokeWidth="1.8" opacity="0.85" />

            {/* Tier 3 */}
            <path d="M 516 332 L 640 332 L 640 319 L 569 319 L 559 306 L 516 306 Z"
              fill="#0c0a05"
              stroke="#c9a96e" strokeWidth="1" opacity="0.8" />
            <line x1="516" y1="306" x2="516" y2="332"
              stroke="#f5e098" strokeWidth="1.6" opacity="0.8" />

            {/* Tier 4 */}
            <path d="M 524 306 L 638 306 L 638 294 L 575 294 L 566 282 L 524 282 Z"
              fill="#0c0a05"
              stroke="#c9a96e" strokeWidth="0.9" opacity="0.75" />
            <line x1="524" y1="282" x2="524" y2="306"
              stroke="#e8c96a" strokeWidth="1.4" opacity="0.75" />

            {/* Tier 5 */}
            <path d="M 531 282 L 636 282 L 636 270 L 581 270 L 573 259 L 531 259 Z"
              fill="#0c0a05"
              stroke="#c9a96e" strokeWidth="0.8" opacity="0.7" />
            <line x1="531" y1="259" x2="531" y2="282"
              stroke="#e8c96a" strokeWidth="1.2" opacity="0.7" />

            {/* Tier 6 */}
            <path d="M 538 259 L 635 259 L 635 248 L 587 248 L 580 238 L 538 238 Z"
              fill="#0c0a05"
              stroke="#c9a96e" strokeWidth="0.7" opacity="0.65" />
            <line x1="538" y1="238" x2="538" y2="259"
              stroke="#e8c96a" strokeWidth="1" opacity="0.65" />

            {/* Tier 7 */}
            <path d="M 545 238 L 634 238 L 634 228 L 592 228 L 586 219 L 545 219 Z"
              fill="#0c0a05"
              stroke="#c9a96e" strokeWidth="0.6" opacity="0.6" />
            <line x1="545" y1="219" x2="545" y2="238"
              stroke="#e8c96a" strokeWidth="0.9" opacity="0.6" />

            {/* ── KARANG (head ornament) left ── */}
            <path d="M 550 219 C 555 200 570 185 590 175 C 605 168 615 165 622 162
                     L 630 175 C 622 178 613 183 602 191 C 586 202 574 215 568 228
                     L 550 228 Z"
              fill="#0c0a05"
              stroke="#e8c96a" strokeWidth="1.2"
              filter="url(#goldGlow)" />

            {/* ── MERU TUMPANG (stacked pavilions) — left ── */}
            {/* Pavilion 1 */}
            <path d="M 590 162 L 638 162 L 638 152 L 614 148 L 590 152 Z"
              fill="#0c0a05" stroke="#e8c96a" strokeWidth="1" opacity="0.9" />
            {/* Pavilion 2 */}
            <path d="M 596 148 L 636 148 L 636 139 L 616 135 L 596 139 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.8" opacity="0.85" />
            {/* Pavilion 3 */}
            <path d="M 601 135 L 634 135 L 634 127 L 617 123 L 601 127 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.7" opacity="0.8" />
            {/* Pavilion 4 */}
            <path d="M 606 123 L 632 123 L 632 116 L 619 112 L 606 116 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.6" opacity="0.75" />
            {/* Pavilion 5 */}
            <path d="M 611 112 L 630 112 L 630 106 L 620 102 L 611 106 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.5" opacity="0.7" />
            {/* Pavilion 6 */}
            <path d="M 614 102 L 628 102 L 628 97 L 621 94 L 614 97 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.4" opacity="0.65" />

            {/* Top finial — padmasana spike */}
            <path d="M 617 94 L 623 94 L 621 72 L 619 72 Z"
              fill="#c9a96e" opacity="0.9" filter="url(#tipGlow)" />
            <ellipse cx="620" cy="70" rx="4" ry="4"
              fill="#f5e098" opacity="0.95" filter="url(#tipGlow)" />
            <ellipse cx="620" cy="70" rx="2" ry="2"
              fill="#ffffff" opacity="0.9" />

          </g>

          {/* ── RIGHT HALF OF GATE (mirrored) ── */}
          <g filter="url(#pillarGlow)">

            {/* Main body — right tower */}
            <path
              d="M 930 780
                 L 930 430
                 L 905 410
                 L 905 390
                 L 895 375
                 L 880 365
                 L 820 365
                 L 800 380
                 L 800 780
                 Z"
              fill="#0a0804"
              stroke="url(#goldEdge)"
              strokeWidth="1.5"
            />

            {/* Right tower — outer edge bright gold line */}
            <line x1="930" y1="430" x2="930" y2="780"
              stroke="#f5e098" strokeWidth="2" opacity="0.85" />

            {/* Right tower — inner edge */}
            <line x1="800" y1="380" x2="800" y2="780"
              stroke="#e8c96a" strokeWidth="1.5" opacity="0.7" />

            {/* Horizontal bands */}
            {[410, 445, 480, 515, 550, 585, 620, 655, 690, 725, 760].map((y, i) => (
              <g key={`rb-${i}`}>
                <rect x="800" y={y} width="130" height="2"
                  fill="#c9a96e" opacity={0.18 + (i % 3) * 0.06} />
                <line x1="800" y1={y} x2="930" y2={y}
                  stroke="#e8c96a" strokeWidth="0.5" opacity={0.12} />
              </g>
            ))}

            {/* Decorative carved panels */}
            <rect x="808" y="440" width="114" height="90" rx="1"
              fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.25" />
            <rect x="808" y="545" width="114" height="90" rx="1"
              fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.25" />
            <rect x="808" y="650" width="114" height="90" rx="1"
              fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.25" />

            {/* Lotus relief */}
            <path d="M 865 465 Q 855 480 865 495 Q 875 480 865 465 Z"
              fill="#c9a96e" opacity="0.2" />
            <path d="M 865 570 Q 855 585 865 600 Q 875 585 865 570 Z"
              fill="#c9a96e" opacity="0.2" />
            <path d="M 865 675 Q 855 690 865 700 Q 875 690 865 675 Z"
              fill="#c9a96e" opacity="0.2" />

            {/* Right arch tiers */}
            <path d="M 940 390 L 800 390 L 800 375 L 885 375 L 895 360 L 940 360 Z"
              fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.2" opacity="0.9" />
            <line x1="940" y1="360" x2="940" y2="390"
              stroke="#f5e098" strokeWidth="2" opacity="0.9" />

            <path d="M 932 360 L 800 360 L 800 346 L 878 346 L 888 332 L 932 332 Z"
              fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.1" opacity="0.85" />
            <line x1="932" y1="332" x2="932" y2="360"
              stroke="#f5e098" strokeWidth="1.8" opacity="0.85" />

            <path d="M 924 332 L 800 332 L 800 319 L 871 319 L 881 306 L 924 306 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="1" opacity="0.8" />
            <line x1="924" y1="306" x2="924" y2="332"
              stroke="#f5e098" strokeWidth="1.6" opacity="0.8" />

            <path d="M 916 306 L 802 306 L 802 294 L 865 294 L 874 282 L 916 282 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.9" opacity="0.75" />
            <line x1="916" y1="282" x2="916" y2="306"
              stroke="#e8c96a" strokeWidth="1.4" opacity="0.75" />

            <path d="M 909 282 L 804 282 L 804 270 L 859 270 L 867 259 L 909 259 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.8" opacity="0.7" />
            <line x1="909" y1="259" x2="909" y2="282"
              stroke="#e8c96a" strokeWidth="1.2" opacity="0.7" />

            <path d="M 902 259 L 805 259 L 805 248 L 853 248 L 860 238 L 902 238 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.7" opacity="0.65" />
            <line x1="902" y1="238" x2="902" y2="259"
              stroke="#e8c96a" strokeWidth="1" opacity="0.65" />

            <path d="M 895 238 L 806 238 L 806 228 L 848 228 L 854 219 L 895 219 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.6" opacity="0.6" />
            <line x1="895" y1="219" x2="895" y2="238"
              stroke="#e8c96a" strokeWidth="0.9" opacity="0.6" />

            {/* Karang right */}
            <path d="M 890 219 C 885 200 870 185 850 175 C 835 168 825 165 818 162
                     L 810 175 C 818 178 827 183 838 191 C 854 202 866 215 872 228
                     L 890 228 Z"
              fill="#0c0a05"
              stroke="#e8c96a" strokeWidth="1.2"
              filter="url(#goldGlow)" />

            {/* Meru tumpang right */}
            <path d="M 802 162 L 850 162 L 850 152 L 826 148 L 802 152 Z"
              fill="#0c0a05" stroke="#e8c96a" strokeWidth="1" opacity="0.9" />
            <path d="M 804 148 L 844 148 L 844 139 L 824 135 L 804 139 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.8" opacity="0.85" />
            <path d="M 806 135 L 839 135 L 839 127 L 823 123 L 806 127 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.7" opacity="0.8" />
            <path d="M 808 123 L 834 123 L 834 116 L 821 112 L 808 116 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.6" opacity="0.75" />
            <path d="M 810 112 L 831 112 L 831 106 L 820 102 L 810 106 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.5" opacity="0.7" />
            <path d="M 812 102 L 828 102 L 828 97 L 820 94 L 812 97 Z"
              fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.4" opacity="0.65" />

            {/* Top finial right */}
            <path d="M 817 94 L 823 94 L 821 72 L 819 72 Z"
              fill="#c9a96e" opacity="0.9" filter="url(#tipGlow)" />
            <ellipse cx="820" cy="70" rx="4" ry="4"
              fill="#f5e098" opacity="0.95" filter="url(#tipGlow)" />
            <ellipse cx="820" cy="70" rx="2" ry="2"
              fill="#ffffff" opacity="0.9" />

          </g>

          {/* ── CENTRAL PASSAGE ── */}
          {/* The void between the two halves — pure black with subtle warm breath */}
          <rect x="640" y="365" width="160" height="415"
            fill="url(#passageGlow)" />
          {/* Passage left edge bright gold */}
          <line x1="640" y1="365" x2="640" y2="780"
            stroke="#f5e098" strokeWidth="1.5" opacity="0.6" />
          {/* Passage right edge bright gold */}
          <line x1="800" y1="365" x2="800" y2="780"
            stroke="#f5e098" strokeWidth="1.5" opacity="0.6" />

          {/* ── BASE PLATFORM — stepped paduraksa base ── */}
          {/* Top step */}
          <rect x="480" y="780" width="480" height="12" rx="1"
            fill="#0a0804" stroke="#e8c96a" strokeWidth="1" opacity="0.7" />
          <line x1="480" y1="780" x2="960" y2="780"
            stroke="#f5e098" strokeWidth="1.5" opacity="0.7" />
          {/* Middle step */}
          <rect x="460" y="792" width="520" height="10" rx="1"
            fill="#080602" stroke="#c9a96e" strokeWidth="0.8" opacity="0.5" />
          {/* Base step */}
          <rect x="440" y="802" width="560" height="10" rx="1"
            fill="#060401" stroke="#8a6030" strokeWidth="0.6" opacity="0.3" />

          {/* ── GROUND PLANE ── */}
          <rect x="0" y="812" width="1440" height="88" fill="#000000" />
          <line x1="0" y1="812" x2="1440" y2="812"
            stroke="#c9a96e" strokeWidth="0.5" opacity="0.12" />

          {/* ── TROPICAL FOLIAGE — authentic Balinese palm silhouettes ── */}
          {/* Left cluster */}
          <path d="M 0 900 L 0 680
               Q 30 620 80 580 Q 50 650 100 630
               Q 60 700 130 680 Q 80 750 160 740
               Q 120 800 220 790 L 180 900 Z"
            fill="#000000" />
          <path d="M 80 900 Q 110 800 180 760 Q 150 830 230 810 L 200 900 Z"
            fill="#000000" />
          {/* Palm fronds left — thin curving lines */}
          <path d="M 120 680 Q 80 600 160 540" fill="none"
            stroke="#050502" strokeWidth="8" />
          <path d="M 120 680 Q 200 630 240 560" fill="none"
            stroke="#050502" strokeWidth="6" />
          <path d="M 120 680 Q 50 640 20 590" fill="none"
            stroke="#050502" strokeWidth="6" />

          {/* Right cluster */}
          <path d="M 1440 900 L 1440 680
               Q 1410 620 1360 580 Q 1390 650 1340 630
               Q 1380 700 1310 680 Q 1360 750 1280 740
               Q 1320 800 1220 790 L 1260 900 Z"
            fill="#000000" />
          <path d="M 1360 900 Q 1330 800 1260 760 Q 1290 830 1210 810 L 1240 900 Z"
            fill="#000000" />
          {/* Palm fronds right */}
          <path d="M 1320 680 Q 1360 600 1280 540" fill="none"
            stroke="#050502" strokeWidth="8" />
          <path d="M 1320 680 Q 1240 630 1200 560" fill="none"
            stroke="#050502" strokeWidth="6" />
          <path d="M 1320 680 Q 1390 640 1420 590" fill="none"
            stroke="#050502" strokeWidth="6" />

          {/* ── FIREFLIES / temple oil lamps glow ── */}
          {[
            [280, 620, 0.55], [340, 570, 0.4], [200, 680, 0.45],
            [1160, 615, 0.5], [1100, 660, 0.4], [1220, 575, 0.55],
            [680, 430, 0.35], [760, 410, 0.3],
          ].map(([x, y, op], i) => (
            <g key={`ff-${i}`}>
              <circle cx={x} cy={y} r="3" fill="#c9a96e" opacity={op as number} />
              <circle cx={x} cy={y} r="8" fill="#c9a96e"
                opacity={(op as number) * 0.12} />
              <circle cx={x} cy={y} r="16" fill="#c9a96e"
                opacity={(op as number) * 0.04} />
            </g>
          ))}

        </svg>

        {/* Gradient overlay — keep top & bottom dark, gate center bright */}
        <div className="absolute inset-0" style={{
          background: `
            linear-gradient(to bottom,
              rgba(0,0,0,0.45) 0%,
              rgba(0,0,0,0.05) 25%,
              rgba(0,0,0,0.0) 45%,
              rgba(0,0,0,0.4) 72%,
              rgba(0,0,0,0.97) 100%
            )
          `,
        }} />
      </div>

      {/* ─────────────────────────────────────────────
          LAYER 1 — BZ Logo centered in gate opening
      ───────────────────────────────────────────── */}
      <div
        className="absolute inset-x-0 flex justify-center pointer-events-none"
        style={{ top: "14%" }}
      >
        <div className="relative flex items-center justify-center">
          {/* Multi-ring halo */}
          <div style={{
            position: "absolute",
            width: "200px", height: "200px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(201,169,110,0.28) 0%, rgba(201,169,110,0.08) 45%, rgba(201,169,110,0) 70%)",
            filter: "blur(16px)",
          }} />
          <div style={{
            position: "absolute",
            width: "120px", height: "120px",
            borderRadius: "50%",
            border: "1px solid rgba(201,169,110,0.2)",
          }} />
          <Image
            src="/static/balizero-logo-clean.png"
            alt="Bali Zero"
            width={96}
            height={96}
            className="rounded-full relative"
            style={{
              opacity: 0.97,
              filter: "drop-shadow(0 0 18px rgba(201,169,110,0.5))",
            }}
            priority
          />
        </div>
      </div>

      {/* ─────────────────────────────────────────────
          LAYER 2 — Content
      ───────────────────────────────────────────── */}
      <div className="relative z-10 flex flex-col min-h-screen">

        {/* Top-right workspace link */}
        <div className="flex items-center justify-end px-8 pt-6">
          <a
            href="/login"
            className="text-[11px] transition-colors"
            style={{ color: "rgba(237,234,228,0.2)" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#c9a96e")}
            onMouseLeave={e => (e.currentTarget.style.color = "rgba(237,234,228,0.2)")}
          >
            Team workspace →
          </a>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* ── BOTTOM SECTION ── */}
        <div className="px-6 pb-10 max-w-[420px] w-full mx-auto">

          {/* Slogan */}
          <div className="mb-7 text-center">
            <h1
              className="text-[22px] font-light leading-snug tracking-[0.08em] uppercase"
              style={{ color: "#edeae4" }}
            >
              Where Bali Begins.
            </h1>
          </div>

          {/* ── LIQUID GLASS FORM CARD ── */}
          {/*
            Apple-style liquid glass 2025:
            - Multi-layer background (dark base + translucent frost)
            - Gradient border (bright top, fading bottom) via outline trick
            - Inner top highlight (specular reflection)
            - Subtle inner shadow for depth/thickness
            - Soft outer glow
          */}
          <div
            className="relative rounded-2xl overflow-visible"
            style={{
              /* Outer glow — golden aura */
              filter: "drop-shadow(0 0 32px rgba(201,169,110,0.12)) drop-shadow(0 8px 40px rgba(0,0,0,0.7))",
            }}
          >
            {/* Gradient border — drawn as pseudo via absolute inset */}
            <div
              className="absolute inset-0 rounded-2xl pointer-events-none"
              style={{
                padding: "1px",
                background: "linear-gradient(160deg, rgba(245,224,152,0.55) 0%, rgba(201,169,110,0.25) 35%, rgba(138,96,48,0.08) 70%, rgba(138,96,48,0.04) 100%)",
                WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
                WebkitMaskComposite: "xor",
                maskComposite: "exclude",
              }}
            />

            {/* Main glass surface */}
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: "linear-gradient(160deg, rgba(28,22,14,0.92) 0%, rgba(12,10,6,0.96) 100%)",
                backdropFilter: "blur(32px) saturate(1.4)",
                WebkitBackdropFilter: "blur(32px) saturate(1.4)",
                /* Inner glass depth */
                boxShadow: `
                  inset 0 1px 0 rgba(245,224,152,0.18),
                  inset 0 -1px 0 rgba(0,0,0,0.5),
                  inset 1px 0 0 rgba(201,169,110,0.06),
                  inset -1px 0 0 rgba(201,169,110,0.06)
                `,
              }}
            >
              {/* Specular top reflection — liquid glass shine */}
              <div
                className="absolute inset-x-0 top-0 h-[1px] rounded-t-2xl"
                style={{
                  background: "linear-gradient(90deg, transparent 0%, rgba(245,224,152,0.6) 30%, rgba(255,248,200,0.8) 50%, rgba(245,224,152,0.6) 70%, transparent 100%)",
                }}
              />

              {step === "email" ? (
                <form onSubmit={handleSubmitEmail} className="p-6 space-y-4">
                  <div className="space-y-1.5">
                    <label
                      className="block text-[10px] font-medium uppercase tracking-[1.8px]"
                      style={{ color: "rgba(201,169,110,0.55)" }}
                    >
                      Email
                    </label>
                    <div className="relative">
                      <input
                        type="email"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        placeholder="your@email.com"
                        required
                        autoFocus
                        className="w-full rounded-xl px-4 py-3 text-[13px] outline-none transition-all"
                        style={{
                          background: "rgba(255,255,255,0.04)",
                          border: "1px solid rgba(201,169,110,0.15)",
                          color: "#edeae4",
                          /* Glass input inner glow on focus via JS */
                        }}
                        onFocus={e => {
                          e.currentTarget.style.borderColor = "rgba(201,169,110,0.45)";
                          e.currentTarget.style.boxShadow = "inset 0 0 0 1px rgba(201,169,110,0.1), 0 0 16px rgba(201,169,110,0.08)";
                          e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                        }}
                        onBlur={e => {
                          e.currentTarget.style.borderColor = "rgba(201,169,110,0.15)";
                          e.currentTarget.style.boxShadow = "none";
                          e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                        }}
                      />
                    </div>
                  </div>

                  {/* Liquid glass CTA button */}
                  <button
                    type="submit"
                    className="w-full py-3 rounded-xl text-[13px] font-medium tracking-[0.05em] transition-all relative overflow-hidden"
                    style={{
                      background: "linear-gradient(135deg, #d4b578 0%, #c9a96e 40%, #a8813f 100%)",
                      color: "#0c0a04",
                      boxShadow: "0 1px 0 rgba(255,248,180,0.5) inset, 0 -1px 0 rgba(0,0,0,0.3) inset, 0 4px 20px rgba(201,169,110,0.25)",
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.boxShadow = "0 1px 0 rgba(255,248,180,0.5) inset, 0 -1px 0 rgba(0,0,0,0.3) inset, 0 4px 28px rgba(201,169,110,0.38)";
                      e.currentTarget.style.transform = "translateY(-1px)";
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.boxShadow = "0 1px 0 rgba(255,248,180,0.5) inset, 0 -1px 0 rgba(0,0,0,0.3) inset, 0 4px 20px rgba(201,169,110,0.25)";
                      e.currentTarget.style.transform = "translateY(0)";
                    }}
                  >
                    {/* Button specular top shine */}
                    <span
                      className="absolute inset-x-0 top-0 h-[1px]"
                      style={{
                        background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent)",
                      }}
                    />
                    Pass the Gate →
                  </button>
                </form>
              ) : (
                <form onSubmit={handleLogin} className="p-6 space-y-4">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label
                        className="block text-[10px] font-medium uppercase tracking-[1.8px]"
                        style={{ color: "rgba(201,169,110,0.55)" }}
                      >
                        Access PIN
                      </label>
                      <button
                        type="button"
                        onClick={() => setStep("email")}
                        className="text-[11px] transition-colors"
                        style={{ color: "rgba(201,169,110,0.5)" }}
                        onMouseEnter={e => (e.currentTarget.style.color = "#c9a96e")}
                        onMouseLeave={e => (e.currentTarget.style.color = "rgba(201,169,110,0.5)")}
                      >
                        ← {email.split("@")[0]}
                      </button>
                    </div>
                    <input
                      type="password"
                      value={pin}
                      onChange={e => setPin(e.target.value)}
                      placeholder="• • • • • •"
                      required
                      autoFocus
                      maxLength={6}
                      className="w-full rounded-xl px-4 py-3 text-[20px] text-center tracking-[12px] outline-none transition-all"
                      style={{
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(201,169,110,0.15)",
                        color: "#edeae4",
                      }}
                      onFocus={e => {
                        e.currentTarget.style.borderColor = "rgba(201,169,110,0.45)";
                        e.currentTarget.style.boxShadow = "inset 0 0 0 1px rgba(201,169,110,0.1), 0 0 16px rgba(201,169,110,0.08)";
                        e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                      }}
                      onBlur={e => {
                        e.currentTarget.style.borderColor = "rgba(201,169,110,0.15)";
                        e.currentTarget.style.boxShadow = "none";
                        e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                      }}
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-3 rounded-xl text-[13px] font-medium tracking-[0.05em] transition-all flex items-center justify-center gap-2 relative overflow-hidden"
                    style={{
                      background: "linear-gradient(135deg, #d4b578 0%, #c9a96e 40%, #a8813f 100%)",
                      color: "#0c0a04",
                      opacity: isLoading ? 0.7 : 1,
                      boxShadow: "0 1px 0 rgba(255,248,180,0.5) inset, 0 -1px 0 rgba(0,0,0,0.3) inset, 0 4px 20px rgba(201,169,110,0.25)",
                    }}
                  >
                    <span
                      className="absolute inset-x-0 top-0 h-[1px]"
                      style={{
                        background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent)",
                      }}
                    />
                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enter"}
                  </button>
                </form>
              )}

              <div
                className="px-6 pb-5 text-center text-[10px]"
                style={{ color: "rgba(140,136,132,0.5)" }}
              >
                No PIN? Check your invitation email or contact support.
              </div>
            </div>
          </div>

          {/* Footer mark */}
          <p
            className="text-center mt-5 text-[9px] tracking-[2.5px] uppercase"
            style={{ color: "rgba(201,169,110,0.2)" }}
          >
            Bali Zero · Private Client Portal
          </p>
        </div>
      </div>
    </div>
  );
}
