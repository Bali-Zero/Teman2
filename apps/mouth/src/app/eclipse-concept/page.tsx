// apps/mouth/src/app/eclipse-concept/page.tsx
"use client";

import React, { useState } from "react";
import Image from "next/image";

export default function EclipseLogin() {
  const [email, setEmail] = useState("");
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div className="relative min-h-screen bg-[#050505] flex items-center justify-center overflow-hidden">
      {/* The Eclipse Effect (Corona) */}
      <div
        className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full blur-[90px] transition-all duration-1000 ease-in-out pointer-events-none ${
          isHovered
            ? "bg-gradient-to-tr from-amber-600/50 via-red-600/30 to-amber-500/40 scale-110"
            : "bg-gradient-to-tr from-amber-600/20 via-red-500/10 to-amber-500/10 scale-100"
        }`}
      />
      {/* Subtle Starfield or noise */}
      <div className="absolute inset-0 bg-[#000000] opacity-[0.95] mix-blend-multiply pointer-events-none" />

      <div className="relative z-10 w-full max-w-sm px-6 flex flex-col items-center">
        {/* The Black Circular Logo blocking the light (Eclipse Core) */}
        <div
          className="relative mb-16 cursor-pointer group flex items-center justify-center"
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          {/* Intense back-glow specifically behind the logo edge */}
          <div className="absolute inset-0 rounded-full bg-amber-500/0 group-hover:bg-amber-500/40 blur-2xl transition-all duration-500 ease-in-out scale-110" />
          <div className="absolute inset-0 rounded-full bg-red-600/0 group-hover:bg-red-600/30 blur-md transition-all duration-300 ease-in-out scale-100" />

          <div className="w-56 h-56 relative z-20 transition-all duration-700 ease-out group-hover:scale-[1.02]">
            {/* INSERISCO IL LOGO VERO DI BALI ZERO QUI */}
            <Image
              src="/assets/logo/logo_zan.png"
              alt="3ALI ZERO"
              fill
              className="object-contain drop-shadow-[0_0_15px_rgba(0,0,0,1)]"
              priority
            />
          </div>
        </div>

        <div className="w-full text-center mb-8 opacity-0 animate-[fadeIn_1s_ease-out_0.3s_forwards]">
          <p className="text-amber-500/70 text-[10px] tracking-[0.4em] uppercase mb-4">
            Private Client Access
          </p>
        </div>

        {/* Minimalist Floating Form */}
        <div className="w-full mx-auto opacity-0 animate-[fadeIn_1s_ease-out_0.6s_forwards]">
          <form className="space-y-10" onSubmit={(e) => e.preventDefault()}>
            <div className="relative group/input max-w-[280px] mx-auto">
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="SECURE EMAIL IDENTITY"
                className="w-full bg-transparent border-b border-white/20 px-0 py-3 text-white placeholder-white/30 focus:outline-none focus:border-red-600/80 transition-all text-center text-sm font-light tracking-[0.2em] peer"
              />
              {/* Animated bottom border on focus */}
              <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-0 h-[2px] bg-gradient-to-r from-transparent via-red-600 to-transparent peer-focus:w-full transition-all duration-500" />
            </div>

            <div className="flex justify-center">
              <button className="px-10 bg-white/5 hover:bg-white/10 border border-white/10 hover:border-red-600/50 text-white/80 hover:text-white font-light py-3 rounded-full transition-all duration-300 transform active:scale-[0.98] text-[10px] tracking-[0.3em] uppercase backdrop-blur-md shadow-[0_0_15px_rgba(220,38,38,0)] hover:shadow-[0_0_20px_rgba(220,38,38,0.2)]">
                Authenticate
              </button>
            </div>
          </form>

          <div className="mt-16 flex justify-center gap-6 text-[9px] uppercase tracking-widest text-white/20">
            <a href="#" className="hover:text-red-500 transition-colors">
              Request Access
            </a>
            <span className="text-white/10">|</span>
            <a href="#" className="hover:text-red-500 transition-colors">
              Support
            </a>
          </div>
        </div>
      </div>

      <style jsx global>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </div>
  );
}
