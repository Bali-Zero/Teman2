"use client";

import React, { useState, useEffect } from "react";

export default function KBLIIntroOverlay() {
  const [isVisible, setIsVisible] = useState(true);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    // Gestione della chiusura automatica
    const timer = setTimeout(() => {
      setFadeOut(true);
      setTimeout(() => setIsVisible(false), 1000);
    }, 6000);

    return () => clearTimeout(timer);
  }, []);

  if (!isVisible) return null;

  return (
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center bg-[#051C2C] transition-opacity duration-1000 ${fadeOut ? "opacity-0" : "opacity-100"}`}
    >
      <video
        src="/videos/kbli-logo-puzzle.mp4"
        autoPlay
        muted
        playsInline
        onEnded={() => {
          setFadeOut(true);
          setTimeout(() => setIsVisible(false), 1000);
        }}
        className="w-full h-full object-contain max-w-4xl"
      />
      <div className="absolute bottom-10 left-0 right-0 text-center">
        <p className="text-white/50 text-sm tracking-widest uppercase font-light animate-pulse">
          Loading KBLI Navigator...
        </p>
      </div>
      <button
        onClick={() => {
          setFadeOut(true);
          setTimeout(() => setIsVisible(false), 300);
        }}
        className="absolute top-10 right-10 text-white/30 hover:text-white/70 transition-colors text-xs uppercase tracking-widest z-[10000]"
      >
        Skip Intro
      </button>
    </div>
  );
}
