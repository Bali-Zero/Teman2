"use client";

import { motion } from "framer-motion";
import Image from "next/image";

export function ThinkingAvatar() {
  return (
    <div className="flex-shrink-0 w-14 h-14 -ml-2 relative">
      {/* Pulsing glow effect */}
      <motion.div
        className="absolute inset-0 rounded-full bg-gradient-to-r from-purple-500/30 to-blue-500/30 blur-xl"
        animate={{
          scale: [1, 1.2, 1],
          opacity: [0.5, 0.8, 0.5],
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      />
      {/* Orbiting particles */}
      <motion.div
        className="absolute inset-0"
        animate={{ rotate: 360 }}
        transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
      >
        <div className="absolute top-0 left-1/2 w-1.5 h-1.5 -ml-0.75 bg-purple-400 rounded-full" />
        <div className="absolute bottom-0 left-1/2 w-1 h-1 -ml-0.5 bg-blue-400 rounded-full" />
      </motion.div>
      <motion.div
        className="absolute inset-0"
        animate={{ rotate: -360 }}
        transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
      >
        <div className="absolute left-0 top-1/2 w-1 h-1 -mt-0.5 bg-cyan-400 rounded-full" />
        <div className="absolute right-0 top-1/2 w-1.5 h-1.5 -mt-0.75 bg-pink-400 rounded-full" />
      </motion.div>
      {/* Logo */}
      <div className="relative w-full h-full">
        <Image
          src="/assets/logo/logo_zan.png"
          alt="Zantara"
          fill
          className="object-contain brightness-110 drop-shadow-[0_0_20px_rgba(100,100,255,0.5)] scale-125"
        />
      </div>
    </div>
  );
}
