"use client";

import React from "react";
import { motion } from "framer-motion";

const SIZE = 40;
const STROKE = 3;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function getColor(score: number): string {
  if (score >= 70) return "#D4B483"; // gold
  if (score >= 40) return "#F59E0B"; // amber
  return "#555"; // dim
}

export default function MatchScoreRing({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const offset = CIRCUMFERENCE - (pct / 100) * CIRCUMFERENCE;
  const color = getColor(pct);

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: SIZE, height: SIZE }}
    >
      <svg width={SIZE} height={SIZE} className="-rotate-90">
        {/* Track */}
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={STROKE}
        />
        {/* Fill */}
        <motion.circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={color}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          initial={{ strokeDashoffset: CIRCUMFERENCE }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: "easeOut", delay: 0.2 }}
        />
      </svg>
      <span
        className="absolute font-mono text-[10px] font-medium"
        style={{ color }}
      >
        {pct}
      </span>
    </div>
  );
}
