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
    <div className="min-h-screen relative overflow-hidden flex flex-col" style={{ background: "#05060a" }}>

      {/* ── HERO: Balinese Gate fullscreen ── */}
      <div className="absolute inset-0">
        {/* Gate image — SVG inline gate silhouette (no external dependency) */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 1440 900"
          preserveAspectRatio="xMidYMid slice"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden="true"
        >
          <defs>
            <radialGradient id="sky" cx="50%" cy="30%" r="70%">
              <stop offset="0%" stopColor="#1a1020" />
              <stop offset="60%" stopColor="#0a0810" />
              <stop offset="100%" stopColor="#05060a" />
            </radialGradient>
            <radialGradient id="glow" cx="50%" cy="52%" r="25%">
              <stop offset="0%" stopColor="#c9a96e" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#c9a96e" stopOpacity="0" />
            </radialGradient>
            <linearGradient id="goldline" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#e8d5a0" stopOpacity="0.9" />
              <stop offset="50%" stopColor="#c9a96e" stopOpacity="0.7" />
              <stop offset="100%" stopColor="#8a6a3a" stopOpacity="0.3" />
            </linearGradient>
            <filter id="gateGlow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="softGlow">
              <feGaussianBlur stdDeviation="8" result="blur" />
              <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>

          {/* Sky background */}
          <rect width="1440" height="900" fill="url(#sky)" />

          {/* Stars */}
          {[
            [200,80],[350,120],[500,60],[700,100],[900,70],[1100,90],[1300,110],[1400,60],
            [150,200],[450,180],[650,220],[850,160],[1050,200],[1250,170],[1380,220],
            [100,300],[300,280],[600,310],[800,290],[1000,270],[1200,300],[1440,280],
            [250,400],[750,380],[1150,390],[720,50],[980,130],[1320,50],
          ].map(([x,y], i) => (
            <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 1.2 : 0.7}
              fill="#e8d5a0" opacity={0.3 + (i % 5) * 0.1} />
          ))}

          {/* Moon — kept subtle in background */}
          <circle cx="720" cy="80" r="30" fill="#1a1020" />
          <circle cx="732" cy="70" r="30" fill="#0d0c15" />
          <circle cx="720" cy="80" r="29" fill="none" stroke="#c9a96e" strokeWidth="0.4" opacity="0.25" />

          {/* Ambient gate glow from below */}
          <ellipse cx="720" cy="520" rx="300" ry="180" fill="url(#glow)" />

          {/* ── GATE STRUCTURE ── */}
          {/* Base platform */}
          <rect x="420" y="750" width="600" height="20" rx="2" fill="#c9a96e" opacity="0.15" filter="url(#softGlow)" />
          <rect x="380" y="760" width="680" height="8" rx="1" fill="#c9a96e" opacity="0.08" />

          {/* Left pillar */}
          <rect x="480" y="380" width="55" height="390" rx="4" fill="#0f0c1a" stroke="url(#goldline)" strokeWidth="1" />
          <rect x="490" y="390" width="35" height="370" rx="2" fill="none" stroke="#c9a96e" strokeWidth="0.3" opacity="0.3" />
          {/* Left pillar decorations */}
          {[420,460,500,540,580,620,660,700].map((y, i) => (
            <rect key={i} x="483" y={y} width="49" height="6" rx="1" fill="#c9a96e" opacity="0.12" />
          ))}
          <rect x="470" y="370" width="75" height="20" rx="3" fill="#0f0c1a" stroke="url(#goldline)" strokeWidth="1" />

          {/* Right pillar */}
          <rect x="905" y="380" width="55" height="390" rx="4" fill="#0f0c1a" stroke="url(#goldline)" strokeWidth="1" />
          <rect x="915" y="390" width="35" height="370" rx="2" fill="none" stroke="#c9a96e" strokeWidth="0.3" opacity="0.3" />
          {[420,460,500,540,580,620,660,700].map((y, i) => (
            <rect key={i} x="908" y={y} width="49" height="6" rx="1" fill="#c9a96e" opacity="0.12" />
          ))}
          <rect x="895" y="370" width="75" height="20" rx="3" fill="#0f0c1a" stroke="url(#goldline)" strokeWidth="1" />

          {/* ── CANDI BENTAR top arch ── */}
          {/* Left arch half */}
          <path d="M480 380 C480 300 560 220 600 180 C620 160 630 150 635 145 L640 370 Z"
            fill="#0f0c1a" stroke="url(#goldline)" strokeWidth="1" filter="url(#gateGlow)" />
          {/* Right arch half */}
          <path d="M960 380 C960 300 880 220 840 180 C820 160 810 150 805 145 L800 370 Z"
            fill="#0f0c1a" stroke="url(#goldline)" strokeWidth="1" filter="url(#gateGlow)" />

          {/* Top ornamental tiers - left */}
          <path d="M600 170 C610 150 620 130 630 115 L640 140 C630 155 620 165 610 175 Z"
            fill="#0f0c1a" stroke="#c9a96e" strokeWidth="0.8" opacity="0.8" />
          <path d="M615 130 C622 112 628 98 634 88 L641 108 C636 118 628 128 620 138 Z"
            fill="#0f0c1a" stroke="#c9a96e" strokeWidth="0.6" opacity="0.7" />
          <path d="M626 95 C631 80 636 68 638 60 L643 78 C640 86 636 95 630 103 Z"
            fill="#0f0c1a" stroke="#c9a96e" strokeWidth="0.5" opacity="0.6" />
          <circle cx="637" cy="52" r="6" fill="#c9a96e" opacity="0.5" />
          <circle cx="637" cy="52" r="3" fill="#e8d5a0" opacity="0.7" />

          {/* Top ornamental tiers - right */}
          <path d="M840 170 C830 150 820 130 810 115 L800 140 C810 155 820 165 830 175 Z"
            fill="#0f0c1a" stroke="#c9a96e" strokeWidth="0.8" opacity="0.8" />
          <path d="M825 130 C818 112 812 98 806 88 L799 108 C804 118 812 128 820 138 Z"
            fill="#0f0c1a" stroke="#c9a96e" strokeWidth="0.6" opacity="0.7" />
          <path d="M814 95 C809 80 804 68 802 60 L797 78 C800 86 804 95 810 103 Z"
            fill="#0f0c1a" stroke="#c9a96e" strokeWidth="0.5" opacity="0.6" />
          <circle cx="803" cy="52" r="6" fill="#c9a96e" opacity="0.5" />
          <circle cx="803" cy="52" r="3" fill="#e8d5a0" opacity="0.7" />

          {/* Gate opening — the passage */}
          <rect x="640" y="380" width="160" height="390" fill="#02030a" opacity="0.95" />
          {/* Inner glow of the passage */}
          <rect x="640" y="380" width="160" height="390"
            fill="none" stroke="#c9a96e" strokeWidth="0.5" opacity="0.2" />

          {/* Horizontal lintel */}
          <rect x="480" y="370" width="480" height="18" rx="2"
            fill="#0f0c1a" stroke="url(#goldline)" strokeWidth="1" />
          {/* Lintel decorations */}
          {[500,540,580,620,660,700,740,780,820,860,900].map((x, i) => (
            <rect key={i} x={x} y="373" width="30" height="12" rx="1" fill="#c9a96e" opacity="0.08" />
          ))}

          {/* Foreground ground / steps */}
          <path d="M0 820 Q360 800 720 810 Q1080 800 1440 820 L1440 900 L0 900 Z"
            fill="#05060a" />
          <path d="M560 800 Q720 785 880 800 L900 810 Q720 796 540 810 Z"
            fill="#0a0810" />
          {/* Step line */}
          <line x1="540" y1="810" x2="900" y2="810" stroke="#c9a96e" strokeWidth="0.4" opacity="0.25" />

          {/* Tropical foliage silhouettes — left */}
          <path d="M0 900 Q50 700 120 650 Q80 750 150 720 Q100 800 200 780 Q160 850 250 840 L0 900Z"
            fill="#060810" />
          <path d="M200 900 Q240 780 300 740 Q270 820 350 800 L200 900Z"
            fill="#060810" />

          {/* Tropical foliage silhouettes — right */}
          <path d="M1440 900 Q1390 700 1320 650 Q1360 750 1290 720 Q1340 800 1240 780 Q1280 850 1190 840 L1440 900Z"
            fill="#060810" />
          <path d="M1240 900 Q1200 780 1140 740 Q1170 820 1090 800 L1240 900Z"
            fill="#060810" />

          {/* Fireflies / floating lights */}
          {[
            [350,600,0.6],[400,550,0.4],[300,680,0.5],[1100,600,0.5],[1050,640,0.4],[1150,570,0.6],
            [650,480,0.4],[750,460,0.3],[700,500,0.35],
          ].map(([x, y, op], i) => (
            <g key={i}>
              <circle cx={x} cy={y} r="2.5" fill="#c9a96e" opacity={op as number} />
              <circle cx={x} cy={y} r="6" fill="#c9a96e" opacity={(op as number) * 0.15} />
            </g>
          ))}
        </svg>

        {/* Heavy gradient overlay — darkens top and bottom, keeps gate visible */}
        <div className="absolute inset-0" style={{
          background: `
            linear-gradient(to bottom,
              rgba(5,6,10,0.5) 0%,
              rgba(5,6,10,0.1) 30%,
              rgba(5,6,10,0.05) 50%,
              rgba(5,6,10,0.5) 70%,
              rgba(5,6,10,0.95) 100%
            )
          `
        }} />
      </div>

      {/* ── CONTENT ── */}
      <div className="relative z-10 flex flex-col min-h-screen">

        {/* Team workspace link — top right only */}
        <div className="flex items-center justify-end px-8 pt-6">
          <a
            href="/login"
            className="text-[11px] transition-colors"
            style={{ color: "rgba(237,234,228,0.25)" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#c9a96e")}
            onMouseLeave={e => (e.currentTarget.style.color = "rgba(237,234,228,0.25)")}
          >
            Team workspace →
          </a>
        </div>

        {/* BZ Logo — large, centered in gate opening */}
        <div className="absolute inset-0 flex justify-center" style={{ top: "16%" }}>
          <div style={{ position: "relative" }}>
            {/* Halo glow behind logo */}
            <div style={{
              position: "absolute",
              top: "50%", left: "50%",
              transform: "translate(-50%, -50%)",
              width: "160px", height: "160px",
              borderRadius: "50%",
              background: "radial-gradient(circle, rgba(201,169,110,0.22) 0%, rgba(201,169,110,0) 70%)",
              filter: "blur(12px)",
            }} />
            <Image
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              width={88}
              height={88}
              className="rounded-full relative z-10"
              style={{ opacity: 0.95 }}
              priority
            />
          </div>
        </div>

        {/* Spacer — push form to bottom */}
        <div className="flex-1" />

        {/* ── BOTTOM SECTION ── */}
        <div className="px-8 pb-10 max-w-md w-full mx-auto">

          {/* Tagline above form */}
          <div className="mb-6 text-center">
            <p className="text-[11px] uppercase tracking-[3px] mb-1" style={{ color: "#c9a96e", opacity: 0.7 }}>
              Private Client Access
            </p>
            <h1 className="text-[24px] font-light leading-tight tracking-[0.04em] uppercase" style={{ color: "#edeae4" }}>
              Your Bali Life,<br />
              <span style={{ color: "#c9a96e" }}>One Portal Away.</span>
            </h1>
          </div>

          {/* Form */}
          <div
            className="rounded-2xl border overflow-hidden"
            style={{
              background: "rgba(12,12,14,0.85)",
              borderColor: "rgba(201,169,110,0.12)",
              backdropFilter: "blur(20px)",
            }}
          >
            {step === "email" ? (
              <form onSubmit={handleSubmitEmail} className="p-6 space-y-4">
                <div className="space-y-1.5">
                  <label
                    className="block text-[10px] font-medium uppercase tracking-[1.5px]"
                    style={{ color: "#8c8884" }}
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
                    className="w-full rounded-lg px-4 py-3 text-[13px] outline-none transition-all"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(201,169,110,0.15)",
                      color: "#edeae4",
                    }}
                    onFocus={e => (e.currentTarget.style.borderColor = "rgba(201,169,110,0.4)")}
                    onBlur={e => (e.currentTarget.style.borderColor = "rgba(201,169,110,0.15)")}
                  />
                </div>
                <button
                  type="submit"
                  className="w-full py-3 rounded-lg text-[13px] font-medium tracking-wide transition-all"
                  style={{
                    background: "linear-gradient(135deg, #c9a96e 0%, #a8813f 100%)",
                    color: "#0c0c0e",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.opacity = "0.9")}
                  onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
                >
                  Pass the Gate →
                </button>
              </form>
            ) : (
              <form onSubmit={handleLogin} className="p-6 space-y-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label
                      className="block text-[10px] font-medium uppercase tracking-[1.5px]"
                      style={{ color: "#8c8884" }}
                    >
                      Access PIN
                    </label>
                    <button
                      type="button"
                      onClick={() => setStep("email")}
                      className="text-[11px] transition-colors"
                      style={{ color: "rgba(201,169,110,0.6)" }}
                      onMouseEnter={e => (e.currentTarget.style.color = "#c9a96e")}
                      onMouseLeave={e => (e.currentTarget.style.color = "rgba(201,169,110,0.6)")}
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
                    className="w-full rounded-lg px-4 py-3 text-[20px] text-center tracking-[12px] outline-none transition-all"
                    style={{
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(201,169,110,0.15)",
                      color: "#edeae4",
                    }}
                    onFocus={e => (e.currentTarget.style.borderColor = "rgba(201,169,110,0.4)")}
                    onBlur={e => (e.currentTarget.style.borderColor = "rgba(201,169,110,0.15)")}
                  />
                </div>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full py-3 rounded-lg text-[13px] font-medium tracking-wide transition-all flex items-center justify-center gap-2"
                  style={{
                    background: "linear-gradient(135deg, #c9a96e 0%, #a8813f 100%)",
                    color: "#0c0c0e",
                    opacity: isLoading ? 0.7 : 1,
                  }}
                >
                  {isLoading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Enter"
                  )}
                </button>
              </form>
            )}

            <div
              className="px-6 pb-5 text-center text-[10px]"
              style={{ color: "#575350" }}
            >
              No PIN? Check your invitation email or contact support.
            </div>
          </div>

          {/* Bottom tagline */}
          <p className="text-center mt-5 text-[10px] tracking-[2px] uppercase" style={{ color: "rgba(201,169,110,0.3)" }}>
            Bali Zero · Private Client Portal
          </p>
        </div>
      </div>
    </div>
  );
}
