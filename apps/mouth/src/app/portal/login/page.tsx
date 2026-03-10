"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

// Cormorant Garamond via Google Fonts
import { Cormorant_Garamond } from "next/font/google";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400"],
  display: "swap",
});

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
      {/* ── CSS animations ── */}
      <style>{`
        @keyframes twinkle {
          0%, 100% { opacity: var(--op-base); transform: scale(1); }
          50%       { opacity: var(--op-peak); transform: scale(1.5); }
        }
        /* Unidirectional left→right star drift — 3 speeds for parallax depth */
        @keyframes starDriftFast {
          0%   { transform: translateX(0px); }
          100% { transform: translateX(6px); }
        }
        @keyframes starDriftMid {
          0%   { transform: translateX(0px); }
          100% { transform: translateX(3.5px); }
        }
        @keyframes starDriftSlow {
          0%   { transform: translateX(0px); }
          100% { transform: translateX(1.8px); }
        }
        @keyframes glassShimmer {
          0%, 100% { opacity: 0.18; }
          50%       { opacity: 0.35; }
        }
        @keyframes firefly {
          0%, 100% { opacity: 0.1; }
          50%       { opacity: 0.55; }
        }
      `}</style>

      {/* ═══════════════════════════════════════
          LAYER 0 — STARFIELD + GATE SVG
      ═══════════════════════════════════════ */}
      <div className="absolute inset-0">
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 1440 900"
          preserveAspectRatio="xMidYMid slice"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="skyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#000000" />
              <stop offset="100%" stopColor="#030306" />
            </linearGradient>

            <linearGradient id="goldEdge" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%"   stopColor="#f8e89a" stopOpacity="1" />
              <stop offset="25%"  stopColor="#e8c96a" stopOpacity="0.95" />
              <stop offset="65%"  stopColor="#c9a96e" stopOpacity="0.7" />
              <stop offset="100%" stopColor="#7a5020" stopOpacity="0.3" />
            </linearGradient>

            <radialGradient id="gateGlow" cx="50%" cy="85%" r="40%">
              <stop offset="0%"   stopColor="#c9a96e" stopOpacity="0.22" />
              <stop offset="60%"  stopColor="#c9a96e" stopOpacity="0.06" />
              <stop offset="100%" stopColor="#c9a96e" stopOpacity="0" />
            </radialGradient>

            <radialGradient id="passageGlow" cx="50%" cy="40%" r="50%">
              <stop offset="0%"   stopColor="#1a1008" stopOpacity="1" />
              <stop offset="100%" stopColor="#000000" stopOpacity="1" />
            </radialGradient>

            <filter id="goldGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="tipGlow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="pillarGlow" x="-5%" y="-2%" width="110%" height="104%">
              <feGaussianBlur stdDeviation="1.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          {/* Sky */}
          <rect width="1440" height="900" fill="url(#skyGrad)" />

          {/* ── ANIMATED STARFIELD ── */}
          {/* Layer A — distant stars, slowest drift */}
          <g style={{ animation: "starDriftSlow 90s linear infinite" }}>
            {[
              [88,45,0.18,4.2],[144,72,0.22,6.1],[201,28,0.16,8.3],[267,91,0.25,5.0],
              [312,55,0.19,7.2],[389,38,0.14,3.8],[445,82,0.23,9.1],[501,19,0.17,6.7],
              [563,66,0.21,4.5],[618,33,0.15,7.9],[674,77,0.26,5.5],[785,88,0.18,8.8],
              [841,22,0.13,3.2],[897,67,0.22,6.4],[953,41,0.19,4.8],[1009,79,0.24,7.3],
              [1065,31,0.16,9.5],[1121,58,0.20,5.1],[1177,84,0.17,6.8],[1289,73,0.23,4.1],
              [1345,26,0.14,7.6],[1401,62,0.21,3.5],[1430,89,0.18,8.2],
              [110,140,0.16,5.4],[178,163,0.20,7.1],[244,128,0.13,4.0],[310,157,0.24,6.3],
              [376,134,0.17,8.9],[442,169,0.22,3.7],[508,142,0.15,5.8],[574,118,0.19,7.4],
              [640,155,0.23,4.6],[706,131,0.16,6.0],[772,148,0.20,8.5],[838,122,0.14,3.9],
              [904,159,0.25,5.2],[970,136,0.18,7.8],[1036,152,0.22,4.3],[1102,127,0.15,6.6],
              [1168,144,0.19,8.1],[1234,161,0.23,5.7],[1300,129,0.16,3.4],[1366,156,0.21,7.0],
            ].map(([x, y, op, dur], i) => (
              <circle
                key={`sa-${i}`} cx={x} cy={y} r={0.5 + (i % 3) * 0.2}
                fill="#ffffff"
                style={{
                  "--op-base": String(op),
                  "--op-peak": String(Math.min(1, (op as number) * 2.5)),
                  opacity: op as number,
                  animation: `twinkle ${dur}s ease-in-out infinite`,
                  animationDelay: `${(i * 0.37) % dur}s`,
                } as React.CSSProperties}
              />
            ))}
          </g>

          {/* Layer B — mid stars, medium drift */}
          <g style={{ animation: "starDriftMid 60s linear infinite" }}>
            {[
              [55,220,0.15,5.9],[123,248,0.19,7.2],[191,235,0.22,4.4],[259,212,0.13,8.6],
              [327,244,0.17,6.1],[395,228,0.24,3.8],[463,241,0.16,5.5],[531,217,0.20,7.7],
              [599,238,0.14,9.2],[667,223,0.23,4.9],[735,245,0.18,6.3],[803,219,0.21,8.0],
              [871,236,0.15,5.1],[939,251,0.25,7.4],[1007,224,0.17,3.6],[1075,242,0.22,6.8],
              [1143,229,0.19,8.4],[1211,246,0.14,4.7],[1279,213,0.23,5.9],[1347,240,0.16,7.1],
              [170,52,0.22,6.5],[320,38,0.18,8.3],[470,62,0.25,4.0],[620,29,0.19,7.6],
              [820,51,0.16,5.2],[970,35,0.23,3.7],[1120,58,0.20,8.9],[1290,42,0.17,6.1],
              [245,155,0.24,7.3],[415,131,0.15,4.8],[565,168,0.21,6.0],[715,144,0.18,8.5],
              [915,162,0.25,5.4],[1065,138,0.13,7.0],[1215,155,0.22,4.2],[1385,169,0.19,6.7],
            ].map(([x, y, op, dur], i) => (
              <circle
                key={`sb-${i}`} cx={x} cy={y} r={0.6 + (i % 2) * 0.3}
                fill="#f5e8c0"
                style={{
                  "--op-base": String(op),
                  "--op-peak": String(Math.min(1, (op as number) * 2.8)),
                  opacity: op as number,
                  animation: `twinkle ${dur}s ease-in-out infinite`,
                  animationDelay: `${(i * 0.53) % dur}s`,
                } as React.CSSProperties}
              />
            ))}
          </g>

          {/* Layer C — bright foreground stars, fastest drift */}
          <g style={{ animation: "starDriftFast 40s linear infinite" }}>
            {[
              [180,88,0.65,3.8],[520,45,0.7,5.1],[860,72,0.6,4.4],[1200,55,0.72,3.2],
              [350,195,0.58,6.2],[750,168,0.68,4.7],[1100,182,0.62,5.5],
              [140,285,0.55,7.1],[580,294,0.70,3.9],[980,289,0.63,5.8],[1380,292,0.67,4.3],
            ].map(([x, y, op, dur], i) => (
              <g key={`sc-${i}`}
                style={{
                  "--op-base": String((op as number) * 0.7),
                  "--op-peak": String(op),
                  animation: `twinkle ${dur}s ease-in-out infinite`,
                  animationDelay: `${(i * 0.7) % dur}s`,
                } as React.CSSProperties}
              >
                <circle cx={x} cy={y} r={1.4} fill="#fffbe8" />
                <line x1={(x as number) - 5} y1={y as number} x2={(x as number) + 5} y2={y as number}
                  stroke="#fffbe8" strokeWidth="0.4" opacity="0.4" />
                <line x1={x as number} y1={(y as number) - 5} x2={x as number} y2={(y as number) + 5}
                  stroke="#fffbe8" strokeWidth="0.4" opacity="0.4" />
              </g>
            ))}
          </g>

          {/* Moon — crescent upper left */}
          <circle cx="200" cy="110" r="48" fill="#0a0a0a" />
          <circle cx="218" cy="96"  r="48" fill="#000000" />
          <circle cx="200" cy="110" r="47" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.25" />

          {/* Ambient gate glow */}
          <ellipse cx="720" cy="830" rx="360" ry="150" fill="url(#gateGlow)" />

          {/* ═══════════════════════════════════════
              AUTHENTIC CANDI BENTAR
          ═══════════════════════════════════════ */}

          {/* ── LEFT HALF ── */}
          <g filter="url(#pillarGlow)">
            {/* Tower body */}
            <path d="M510 780 L510 430 L535 410 L535 390 L545 375 L560 365 L620 365 L640 380 L640 780 Z"
              fill="#0a0804" stroke="url(#goldEdge)" strokeWidth="1.5" />
            <line x1="510" y1="430" x2="510" y2="780" stroke="#f8e89a" strokeWidth="2" opacity="0.88" />
            <line x1="640" y1="380" x2="640" y2="780" stroke="#e8c96a" strokeWidth="1.5" opacity="0.7" />
            {/* Stone bands */}
            {[410,445,480,515,550,585,620,655,690,725,760].map((y,i) => (
              <g key={`lb-${i}`}>
                <rect x="510" y={y} width="130" height="2" fill="#c9a96e" opacity={0.16+(i%3)*0.06} />
                <line x1="510" y1={y} x2="640" y2={y} stroke="#e8c96a" strokeWidth="0.5" opacity={0.1} />
              </g>
            ))}
            {/* Carved panels */}
            <rect x="518" y="440" width="114" height="90" rx="1" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.22" />
            <rect x="518" y="545" width="114" height="90" rx="1" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.22" />
            <rect x="518" y="650" width="114" height="90" rx="1" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.22" />
            <path d="M575 465 Q565 480 575 495 Q585 480 575 465Z" fill="#c9a96e" opacity="0.18" />
            <path d="M575 570 Q565 585 575 600 Q585 585 575 570Z" fill="#c9a96e" opacity="0.18" />
            <path d="M575 675 Q565 690 575 700 Q585 690 575 675Z" fill="#c9a96e" opacity="0.18" />
            {/* Meru stepped arch tiers */}
            <path d="M500 390 L640 390 L640 375 L555 375 L545 360 L500 360Z" fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.2" opacity="0.92" />
            <line x1="500" y1="360" x2="500" y2="390" stroke="#f8e89a" strokeWidth="2.2" opacity="0.92" />
            <path d="M508 360 L640 360 L640 346 L562 346 L552 332 L508 332Z" fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.1" opacity="0.87" />
            <line x1="508" y1="332" x2="508" y2="360" stroke="#f8e89a" strokeWidth="2" opacity="0.87" />
            <path d="M516 332 L640 332 L640 319 L569 319 L559 306 L516 306Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="1" opacity="0.82" />
            <line x1="516" y1="306" x2="516" y2="332" stroke="#f8e89a" strokeWidth="1.7" opacity="0.82" />
            <path d="M524 306 L638 306 L638 294 L575 294 L566 282 L524 282Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.9" opacity="0.77" />
            <line x1="524" y1="282" x2="524" y2="306" stroke="#e8c96a" strokeWidth="1.5" opacity="0.77" />
            <path d="M531 282 L636 282 L636 270 L581 270 L573 259 L531 259Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.8" opacity="0.72" />
            <line x1="531" y1="259" x2="531" y2="282" stroke="#e8c96a" strokeWidth="1.3" opacity="0.72" />
            <path d="M538 259 L635 259 L635 248 L587 248 L580 238 L538 238Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.7" opacity="0.67" />
            <line x1="538" y1="238" x2="538" y2="259" stroke="#e8c96a" strokeWidth="1.1" opacity="0.67" />
            <path d="M545 238 L634 238 L634 228 L592 228 L586 219 L545 219Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.6" opacity="0.62" />
            <line x1="545" y1="219" x2="545" y2="238" stroke="#e8c96a" strokeWidth="0.9" opacity="0.62" />
            {/* Karang ornament */}
            <path d="M550 219 C555 200 570 185 590 175 C605 168 615 165 622 162 L630 175 C622 178 613 183 602 191 C586 202 574 215 568 228 L550 228Z"
              fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.2" filter="url(#goldGlow)" />
            {/* Meru tumpang pavilions */}
            <path d="M590 162 L638 162 L638 152 L614 148 L590 152Z" fill="#0c0a05" stroke="#e8c96a" strokeWidth="1" opacity="0.92" />
            <path d="M596 148 L636 148 L636 139 L616 135 L596 139Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.8" opacity="0.87" />
            <path d="M601 135 L634 135 L634 127 L617 123 L601 127Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.7" opacity="0.82" />
            <path d="M606 123 L632 123 L632 116 L619 112 L606 116Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.6" opacity="0.77" />
            <path d="M611 112 L630 112 L630 106 L620 102 L611 106Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.5" opacity="0.72" />
            <path d="M614 102 L628 102 L628 97 L621 94 L614 97Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.4" opacity="0.67" />
            {/* Finial */}
            <path d="M617 94 L623 94 L621 70 L619 70Z" fill="#c9a96e" opacity="0.92" filter="url(#tipGlow)" />
            <ellipse cx="620" cy="68" rx="4.5" ry="4.5" fill="#f8e89a" opacity="0.97" filter="url(#tipGlow)" />
            <ellipse cx="620" cy="68" rx="2" ry="2" fill="#ffffff" opacity="0.95" />
          </g>

          {/* ── RIGHT HALF (mirror) ── */}
          <g filter="url(#pillarGlow)">
            <path d="M930 780 L930 430 L905 410 L905 390 L895 375 L880 365 L820 365 L800 380 L800 780Z"
              fill="#0a0804" stroke="url(#goldEdge)" strokeWidth="1.5" />
            <line x1="930" y1="430" x2="930" y2="780" stroke="#f8e89a" strokeWidth="2" opacity="0.88" />
            <line x1="800" y1="380" x2="800" y2="780" stroke="#e8c96a" strokeWidth="1.5" opacity="0.7" />
            {[410,445,480,515,550,585,620,655,690,725,760].map((y,i) => (
              <g key={`rb-${i}`}>
                <rect x="800" y={y} width="130" height="2" fill="#c9a96e" opacity={0.16+(i%3)*0.06} />
                <line x1="800" y1={y} x2="930" y2={y} stroke="#e8c96a" strokeWidth="0.5" opacity={0.1} />
              </g>
            ))}
            <rect x="808" y="440" width="114" height="90" rx="1" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.22" />
            <rect x="808" y="545" width="114" height="90" rx="1" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.22" />
            <rect x="808" y="650" width="114" height="90" rx="1" fill="none" stroke="#c9a96e" strokeWidth="0.6" opacity="0.22" />
            <path d="M865 465 Q855 480 865 495 Q875 480 865 465Z" fill="#c9a96e" opacity="0.18" />
            <path d="M865 570 Q855 585 865 600 Q875 585 865 570Z" fill="#c9a96e" opacity="0.18" />
            <path d="M865 675 Q855 690 865 700 Q875 690 865 675Z" fill="#c9a96e" opacity="0.18" />
            <path d="M940 390 L800 390 L800 375 L885 375 L895 360 L940 360Z" fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.2" opacity="0.92" />
            <line x1="940" y1="360" x2="940" y2="390" stroke="#f8e89a" strokeWidth="2.2" opacity="0.92" />
            <path d="M932 360 L800 360 L800 346 L878 346 L888 332 L932 332Z" fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.1" opacity="0.87" />
            <line x1="932" y1="332" x2="932" y2="360" stroke="#f8e89a" strokeWidth="2" opacity="0.87" />
            <path d="M924 332 L800 332 L800 319 L871 319 L881 306 L924 306Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="1" opacity="0.82" />
            <line x1="924" y1="306" x2="924" y2="332" stroke="#f8e89a" strokeWidth="1.7" opacity="0.82" />
            <path d="M916 306 L802 306 L802 294 L865 294 L874 282 L916 282Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.9" opacity="0.77" />
            <line x1="916" y1="282" x2="916" y2="306" stroke="#e8c96a" strokeWidth="1.5" opacity="0.77" />
            <path d="M909 282 L804 282 L804 270 L859 270 L867 259 L909 259Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.8" opacity="0.72" />
            <line x1="909" y1="259" x2="909" y2="282" stroke="#e8c96a" strokeWidth="1.3" opacity="0.72" />
            <path d="M902 259 L805 259 L805 248 L853 248 L860 238 L902 238Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.7" opacity="0.67" />
            <line x1="902" y1="238" x2="902" y2="259" stroke="#e8c96a" strokeWidth="1.1" opacity="0.67" />
            <path d="M895 238 L806 238 L806 228 L848 228 L854 219 L895 219Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.6" opacity="0.62" />
            <line x1="895" y1="219" x2="895" y2="238" stroke="#e8c96a" strokeWidth="0.9" opacity="0.62" />
            <path d="M890 219 C885 200 870 185 850 175 C835 168 825 165 818 162 L810 175 C818 178 827 183 838 191 C854 202 866 215 872 228 L890 228Z"
              fill="#0c0a05" stroke="#e8c96a" strokeWidth="1.2" filter="url(#goldGlow)" />
            <path d="M802 162 L850 162 L850 152 L826 148 L802 152Z" fill="#0c0a05" stroke="#e8c96a" strokeWidth="1" opacity="0.92" />
            <path d="M804 148 L844 148 L844 139 L824 135 L804 139Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.8" opacity="0.87" />
            <path d="M806 135 L839 135 L839 127 L823 123 L806 127Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.7" opacity="0.82" />
            <path d="M808 123 L834 123 L834 116 L821 112 L808 116Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.6" opacity="0.77" />
            <path d="M810 112 L831 112 L831 106 L820 102 L810 106Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.5" opacity="0.72" />
            <path d="M812 102 L828 102 L828 97 L820 94 L812 97Z" fill="#0c0a05" stroke="#c9a96e" strokeWidth="0.4" opacity="0.67" />
            <path d="M817 94 L823 94 L821 70 L819 70Z" fill="#c9a96e" opacity="0.92" filter="url(#tipGlow)" />
            <ellipse cx="820" cy="68" rx="4.5" ry="4.5" fill="#f8e89a" opacity="0.97" filter="url(#tipGlow)" />
            <ellipse cx="820" cy="68" rx="2" ry="2" fill="#ffffff" opacity="0.95" />
          </g>

          {/* ── CENTRAL PASSAGE ── */}
          <rect x="640" y="365" width="160" height="415" fill="url(#passageGlow)" />
          <line x1="640" y1="365" x2="640" y2="780" stroke="#f8e89a" strokeWidth="1.8" opacity="0.55" />
          <line x1="800" y1="365" x2="800" y2="780" stroke="#f8e89a" strokeWidth="1.8" opacity="0.55" />

          {/* Base steps */}
          <rect x="480" y="780" width="480" height="12" rx="1" fill="#0a0804" stroke="#e8c96a" strokeWidth="1" opacity="0.7" />
          <line x1="480" y1="780" x2="960" y2="780" stroke="#f8e89a" strokeWidth="1.5" opacity="0.7" />
          <rect x="460" y="792" width="520" height="10" rx="1" fill="#080602" stroke="#c9a96e" strokeWidth="0.8" opacity="0.45" />
          <rect x="440" y="802" width="560" height="10" rx="1" fill="#060401" stroke="#8a6030" strokeWidth="0.6" opacity="0.25" />

          {/* Ground */}
          <rect x="0" y="812" width="1440" height="88" fill="#000000" />
          <line x1="0" y1="812" x2="1440" y2="812" stroke="#c9a96e" strokeWidth="0.4" opacity="0.1" />

          {/* Foliage silhouettes */}
          <path d="M0 900 L0 680 Q30 620 80 580 Q50 650 100 630 Q60 700 130 680 Q80 750 160 740 Q120 800 220 790 L180 900Z" fill="#000000" />
          <path d="M80 900 Q110 800 180 760 Q150 830 230 810 L200 900Z" fill="#000000" />
          <path d="M1440 900 L1440 680 Q1410 620 1360 580 Q1390 650 1340 630 Q1380 700 1310 680 Q1360 750 1280 740 Q1320 800 1220 790 L1260 900Z" fill="#000000" />
          <path d="M1360 900 Q1330 800 1260 760 Q1290 830 1210 810 L1240 900Z" fill="#000000" />

          {/* Animated fireflies */}
          {[
            [280,620,4.5,0.5,8],[340,570,5.2,0.4,11],[200,680,6.0,0.45,9],
            [1160,615,4.8,0.5,7],[1100,660,5.5,0.4,12],[1220,575,4.2,0.55,10],
            [680,430,6.5,0.35,8],[760,410,5.0,0.3,13],
          ].map(([x,y,dur,op,del],i) => (
            <g key={`ff-${i}`} style={{ animation: `firefly ${dur}s ease-in-out infinite`, animationDelay: `${del}s` }}>
              <circle cx={x} cy={y} r="3" fill="#c9a96e" opacity={op as number} />
              <circle cx={x} cy={y} r="9" fill="#c9a96e" opacity={(op as number)*0.1} />
            </g>
          ))}
        </svg>

        {/* Gradient vignette */}
        <div className="absolute inset-0" style={{
          background: `linear-gradient(to bottom,
            rgba(0,0,0,0.5) 0%,
            rgba(0,0,0,0.04) 22%,
            rgba(0,0,0,0.0) 42%,
            rgba(0,0,0,0.45) 72%,
            rgba(0,0,0,0.97) 100%
          )`,
        }} />
      </div>

      {/* ═══════════════════════════════════════
          LAYER 1 — BZ Logo (no halo ring)
      ═══════════════════════════════════════ */}
      <div
        className="absolute inset-x-0 flex justify-center pointer-events-none"
        style={{ top: "13%" }}
      >
        <Image
          src="/static/balizero-logo-clean.png"
          alt="Bali Zero"
          width={92}
          height={92}
          className="rounded-full"
          style={{
            opacity: 0.96,
            filter: "drop-shadow(0 0 22px rgba(201,169,110,0.55)) drop-shadow(0 0 6px rgba(201,169,110,0.3))",
          }}
          priority
        />
      </div>

      {/* ═══════════════════════════════════════
          LAYER 2 — Content
      ═══════════════════════════════════════ */}
      <div className="relative z-10 flex flex-col min-h-screen">

        {/* Top-right link */}
        <div className="flex items-center justify-end px-8 pt-6">
          <a
            href="/login"
            className="text-[11px] transition-colors"
            style={{ color: "rgba(237,234,228,0.18)" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#c9a96e")}
            onMouseLeave={e => (e.currentTarget.style.color = "rgba(237,234,228,0.18)")}
          >
            Team workspace →
          </a>
        </div>

        <div className="flex-1" />

        {/* ── BOTTOM SECTION ── */}
        <div className="px-6 pb-10 max-w-[420px] w-full mx-auto">

          {/* Slogan — Cormorant Garamond Light white */}
          <div className="mb-8 text-center">
            <p
              className={`${cormorant.className} text-[13px] uppercase tracking-[4px] mb-2`}
              style={{ color: "rgba(201,169,110,0.55)", fontWeight: 300 }}
            >
              Turn On
            </p>
            <h1
              className={`${cormorant.className} text-[42px] leading-tight tracking-[0.06em] uppercase`}
              style={{ color: "#ffffff", fontWeight: 300 }}
            >
              Your Bali Life.
            </h1>
          </div>

          {/* ══════════════════════════════════════
              LIQUID GLASS CARD — accentuated 2025
              Multi-layer:
              1. Outer glow aura
              2. Gradient border (gold top → transparent)
              3. Frosted dark base (backdrop-blur 40px)
              4. Inner top specular line
              5. Inner shadow for glass thickness
              6. Subtle noise texture overlay
          ══════════════════════════════════════ */}
          <div
            className="relative"
            style={{
              /* Outer golden aura */
              filter: "drop-shadow(0 0 40px rgba(201,169,110,0.18)) drop-shadow(0 12px 60px rgba(0,0,0,0.85))",
            }}
          >
            {/* Gradient border wrapper */}
            <div
              className="absolute inset-0 rounded-2xl pointer-events-none"
              style={{
                padding: "1px",
                background: "linear-gradient(155deg, rgba(248,232,154,0.7) 0%, rgba(220,185,100,0.35) 25%, rgba(180,140,70,0.12) 55%, rgba(100,70,20,0.05) 100%)",
                WebkitMask: "linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)",
                WebkitMaskComposite: "xor",
                maskComposite: "exclude",
                borderRadius: "16px",
              }}
            />

            {/* Glass surface */}
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: "linear-gradient(155deg, rgba(32,26,16,0.88) 0%, rgba(10,8,4,0.94) 60%, rgba(6,4,2,0.97) 100%)",
                backdropFilter: "blur(40px) saturate(1.6) brightness(1.1)",
                WebkitBackdropFilter: "blur(40px) saturate(1.6) brightness(1.1)",
                boxShadow: `
                  inset 0 1.5px 0 rgba(248,232,154,0.22),
                  inset 0 -1px 0 rgba(0,0,0,0.6),
                  inset 1px 0 0 rgba(201,169,110,0.07),
                  inset -1px 0 0 rgba(201,169,110,0.07),
                  inset 0 0 40px rgba(201,169,110,0.03)
                `,
              }}
            >
              {/* Top specular shine — the hallmark of liquid glass */}
              <div
                className="absolute inset-x-0 top-0 h-[1.5px] rounded-t-2xl"
                style={{
                  background: "linear-gradient(90deg, transparent 0%, rgba(248,232,154,0.0) 10%, rgba(255,248,200,0.75) 35%, rgba(255,255,255,0.9) 50%, rgba(255,248,200,0.75) 65%, rgba(248,232,154,0.0) 90%, transparent 100%)",
                  animation: "glassShimmer 6s ease-in-out infinite",
                }}
              />

              {step === "email" ? (
                <form onSubmit={handleSubmitEmail} className="p-7 space-y-5">
                  <div className="space-y-2">
                    <label
                      className={`${cormorant.className} block text-[10px] uppercase tracking-[2.5px]`}
                      style={{ color: "rgba(201,169,110,0.5)", fontWeight: 700 }}
                    >
                      Email
                    </label>
                    <input
                      type="email"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      placeholder="your@email.com"
                      required
                      autoFocus
                      className="w-full rounded-xl px-4 py-3.5 text-[13px] outline-none transition-all"
                      style={{
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(201,169,110,0.16)",
                        color: "#f0ece4",
                        letterSpacing: "0.02em",
                      }}
                      onFocus={e => {
                        e.currentTarget.style.borderColor = "rgba(201,169,110,0.5)";
                        e.currentTarget.style.background = "rgba(255,255,255,0.07)";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(201,169,110,0.07), inset 0 1px 0 rgba(248,232,154,0.08)";
                      }}
                      onBlur={e => {
                        e.currentTarget.style.borderColor = "rgba(201,169,110,0.16)";
                        e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>

                  {/* CTA button — liquid glass gold */}
                  <button
                    type="submit"
                    className="w-full py-3.5 rounded-xl text-[13px] tracking-[0.08em] uppercase transition-all relative overflow-hidden"
                    style={{
                      background: "linear-gradient(135deg, #d9bd7a 0%, #c9a96e 45%, #a07838 100%)",
                      color: "#0c0804",
                      fontWeight: 700,
                      fontFamily: cormorant.style.fontFamily,
                      boxShadow: `
                        inset 0 1.5px 0 rgba(255,248,180,0.55),
                        inset 0 -1.5px 0 rgba(0,0,0,0.35),
                        0 4px 24px rgba(201,169,110,0.32),
                        0 1px 4px rgba(0,0,0,0.5)
                      `,
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.transform = "translateY(-1.5px)";
                      e.currentTarget.style.boxShadow = `
                        inset 0 1.5px 0 rgba(255,248,180,0.55),
                        inset 0 -1.5px 0 rgba(0,0,0,0.35),
                        0 8px 32px rgba(201,169,110,0.45),
                        0 2px 6px rgba(0,0,0,0.5)
                      `;
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.transform = "translateY(0)";
                      e.currentTarget.style.boxShadow = `
                        inset 0 1.5px 0 rgba(255,248,180,0.55),
                        inset 0 -1.5px 0 rgba(0,0,0,0.35),
                        0 4px 24px rgba(201,169,110,0.32),
                        0 1px 4px rgba(0,0,0,0.5)
                      `;
                    }}
                  >
                    {/* Button top specular */}
                    <span className="absolute inset-x-0 top-0 h-[1px]"
                      style={{ background: "linear-gradient(90deg, transparent 5%, rgba(255,255,255,0.55) 50%, transparent 95%)" }} />
                    Pass the Portal →
                  </button>
                </form>
              ) : (
                <form onSubmit={handleLogin} className="p-7 space-y-5">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label
                        className={`${cormorant.className} block text-[10px] uppercase tracking-[2.5px]`}
                        style={{ color: "rgba(201,169,110,0.5)", fontWeight: 700 }}
                      >
                        Access PIN
                      </label>
                      <button
                        type="button"
                        onClick={() => setStep("email")}
                        className="text-[11px] transition-colors"
                        style={{ color: "rgba(201,169,110,0.45)" }}
                        onMouseEnter={e => (e.currentTarget.style.color = "#c9a96e")}
                        onMouseLeave={e => (e.currentTarget.style.color = "rgba(201,169,110,0.45)")}
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
                      className="w-full rounded-xl px-4 py-3.5 text-[22px] text-center tracking-[14px] outline-none transition-all"
                      style={{
                        background: "rgba(255,255,255,0.04)",
                        border: "1px solid rgba(201,169,110,0.16)",
                        color: "#f0ece4",
                      }}
                      onFocus={e => {
                        e.currentTarget.style.borderColor = "rgba(201,169,110,0.5)";
                        e.currentTarget.style.background = "rgba(255,255,255,0.07)";
                        e.currentTarget.style.boxShadow = "0 0 0 3px rgba(201,169,110,0.07), inset 0 1px 0 rgba(248,232,154,0.08)";
                      }}
                      onBlur={e => {
                        e.currentTarget.style.borderColor = "rgba(201,169,110,0.16)";
                        e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                        e.currentTarget.style.boxShadow = "none";
                      }}
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isLoading}
                    className="w-full py-3.5 rounded-xl text-[13px] tracking-[0.08em] uppercase transition-all flex items-center justify-center gap-2 relative overflow-hidden"
                    style={{
                      background: "linear-gradient(135deg, #d9bd7a 0%, #c9a96e 45%, #a07838 100%)",
                      color: "#0c0804",
                      fontWeight: 700,
                      fontFamily: cormorant.style.fontFamily,
                      opacity: isLoading ? 0.7 : 1,
                      boxShadow: `
                        inset 0 1.5px 0 rgba(255,248,180,0.55),
                        inset 0 -1.5px 0 rgba(0,0,0,0.35),
                        0 4px 24px rgba(201,169,110,0.32),
                        0 1px 4px rgba(0,0,0,0.5)
                      `,
                    }}
                  >
                    <span className="absolute inset-x-0 top-0 h-[1px]"
                      style={{ background: "linear-gradient(90deg, transparent 5%, rgba(255,255,255,0.55) 50%, transparent 95%)" }} />
                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : "Enter"}
                  </button>
                </form>
              )}

              <div
                className="px-7 pb-6 text-center text-[10px] leading-relaxed"
                style={{ color: "rgba(140,136,132,0.4)" }}
              >
                No PIN? Check your invitation email or contact support.
              </div>
            </div>
          </div>

          {/* Footer */}
          <p
            className={`${cormorant.className} text-center mt-5 text-[9px] tracking-[3px] uppercase`}
            style={{ color: "rgba(201,169,110,0.18)", fontWeight: 700 }}
          >
            Bali Zero · Private Client Portal
          </p>
        </div>
      </div>
    </div>
  );
}
