"use client";

import React from "react";
import { motion } from "framer-motion";

type RiskLevel = "low" | "medium-low" | "medium" | "medium-high" | "high";

const NEEDLE_ANGLES: Record<RiskLevel, number> = {
  low: 25,
  "medium-low": 55,
  medium: 90,
  "medium-high": 125,
  high: 155,
};

const RISK_LABELS: Record<RiskLevel, string> = {
  low: "Low Risk",
  "medium-low": "Medium-Low",
  medium: "Medium Risk",
  "medium-high": "Medium-High",
  high: "High Risk",
};

const RISK_COLORS: Record<RiskLevel, string> = {
  low: "#34d399",
  "medium-low": "#6ee7b7",
  medium: "#fbbf24",
  "medium-high": "#f97316",
  high: "#ef4444",
};

const WIDTH = 160;
const HEIGHT = 90;
const CX = WIDTH / 2;
const CY = 80;
const RADIUS = 65;
const STROKE = 8;

// Build the arc path for the semi-circle (180 degrees, from left to right)
function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
) {
  const rad = (a: number) => ((a - 90) * Math.PI) / 180;
  const x1 = cx + r * Math.cos(rad(startAngle));
  const y1 = cy + r * Math.sin(rad(startAngle));
  const x2 = cx + r * Math.cos(rad(endAngle));
  const y2 = cy + r * Math.sin(rad(endAngle));
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
}

export default function RiskGauge({ level }: { level: RiskLevel }) {
  const angle = NEEDLE_ANGLES[level];
  const color = RISK_COLORS[level];
  const label = RISK_LABELS[level];

  // Needle endpoint (from center, pointing outward)
  const needleLength = RADIUS - 12;
  const needleRad = ((angle - 90) * Math.PI) / 180;
  const nx = CX + needleLength * Math.cos(needleRad);
  const ny = CY + needleLength * Math.sin(needleRad);

  return (
    <div className="flex flex-col items-center">
      <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
        <defs>
          <linearGradient id="risk-arc-grad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#34d399" />
            <stop offset="35%" stopColor="#fbbf24" />
            <stop offset="65%" stopColor="#f97316" />
            <stop offset="100%" stopColor="#ef4444" />
          </linearGradient>
        </defs>

        {/* Track (dim) */}
        <path
          d={describeArc(CX, CY, RADIUS, -90, 90)}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={STROKE}
          strokeLinecap="round"
        />
        {/* Colored arc */}
        <path
          d={describeArc(CX, CY, RADIUS, -90, 90)}
          fill="none"
          stroke="url(#risk-arc-grad)"
          strokeWidth={STROKE}
          strokeLinecap="round"
        />

        {/* Needle */}
        <motion.line
          x1={CX}
          y1={CY}
          x2={nx}
          y2={ny}
          stroke={color}
          strokeWidth={2}
          strokeLinecap="round"
          initial={{ x2: CX, y2: CY - needleLength }}
          animate={{ x2: nx, y2: ny }}
          transition={{
            type: "spring",
            stiffness: 80,
            damping: 12,
            delay: 0.3,
          }}
        />

        {/* Center dot */}
        <circle cx={CX} cy={CY} r={4} fill={color} />
        <circle cx={CX} cy={CY} r={2} fill="#050507" />
      </svg>
      <span
        className="text-[10px] uppercase tracking-widest mt-1"
        style={{ color }}
      >
        {label}
      </span>
    </div>
  );
}
