"use client";

import React, { useState, useEffect } from "react";

interface KBLINavigatorIntroProps {
  htmlContent: string;
}

export default function KBLINavigatorIntro({
  htmlContent,
}: KBLINavigatorIntroProps) {
  const [showIntro, setShowIntro] = useState(true);
  const [fadeOut, setFadeOut] = useState(false);

  useEffect(() => {
    // Hide intro after video duration or fixed time
    // Assuming the video is about 5-10 seconds.
    // Let's set it to 6 seconds for a smooth transition.
    const timer = setTimeout(() => {
      setFadeOut(true);
      setTimeout(() => {
        setShowIntro(false);
      }, 1000); // 1s fade out duration
    }, 6000);

    return () => clearTimeout(timer);
  }, []);

  if (showIntro) {
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
            setTimeout(() => setShowIntro(false), 1000);
          }}
          className="w-full h-full object-contain max-w-4xl"
        />
        <div className="absolute bottom-10 left-0 right-0 text-center">
          <p className="text-white/50 text-sm tracking-widest uppercase font-light animate-pulse">
            Loading KBLI Navigator...
          </p>
        </div>
        <button
          onClick={() => setShowIntro(false)}
          className="absolute top-10 right-10 text-white/30 hover:text-white/70 transition-colors text-xs uppercase tracking-widest"
        >
          Skip Intro
        </button>
      </div>
    );
  }

  return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
}
