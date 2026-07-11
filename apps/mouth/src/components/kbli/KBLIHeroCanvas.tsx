import {
  getSectionVisual,
  codeFingerprint,
  sectionGradient,
} from "@/lib/kbli-cover-design";

interface KBLIHeroCanvasProps {
  code: string;
  section: string | null;
  pmaStatus: "open" | "restricted" | "closed";
  baliBlocked?: boolean;
}

/**
 * Full-bleed SVG hero backdrop for the KBLI detail page — same design
 * language as the OG cover (section gradient + per-code fingerprint) but
 * rendered low-contrast/content-first, as a subtle backdrop behind the H1
 * rather than a standalone graphic. Pure server component, no client JS,
 * no network requests.
 */
export function KBLIHeroCanvas({
  code,
  section,
  pmaStatus,
  baliBlocked = false,
}: KBLIHeroCanvasProps) {
  const visual = getSectionVisual(section);
  const fp = codeFingerprint(code);

  const width = 1600;
  const height = 500;
  const laneWidth = (width / 3) / Math.max(fp.bars.length, 1);
  const laneOffsetX = (width * 2) / 3;
  const maxBarHeight = height * 0.62;
  const barWidth = laneWidth * 0.42;

  const statusColor = baliBlocked
    ? "#e0645a"
    : pmaStatus === "open"
      ? "#5aab6e"
      : pmaStatus === "restricted"
        ? "#c9a227"
        : "#e0645a";

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 h-full w-full"
      aria-hidden="true"
    >
      <defs>
        <linearGradient
          id={`kbli-hero-grad-${code}`}
          x1="0%"
          y1="0%"
          x2="100%"
          y2="100%"
        >
          <stop offset="0%" stopColor={visual.hueA} />
          <stop offset="100%" stopColor={visual.hueB} />
        </linearGradient>
      </defs>
      <rect
        width={width}
        height={height}
        fill={`url(#kbli-hero-grad-${code})`}
      />
      {fp.bars.map((bar) => {
        const barHeight = maxBarHeight * bar.heightFrac;
        const x = laneOffsetX + bar.xFrac * (width / 3) - barWidth / 2;
        const y = height - barHeight;
        return (
          <rect
            key={bar.digitIndex}
            x={x}
            y={y}
            width={barWidth}
            height={barHeight}
            rx={bar.radius}
            fill={visual.accent}
            opacity={0.08 + bar.digit * 0.035}
            transform={`rotate(${bar.rotationDeg} ${x + barWidth / 2} ${height})`}
          />
        );
      })}
      <circle
        cx={40}
        cy={height - 40}
        r={5}
        fill={statusColor}
        opacity={0.85}
      />
    </svg>
  );
}

/**
 * CSS-only variant, compatible with how the page currently applies hero
 * styles via `getHeroStyle(section)` (which returns { gradient, pattern }).
 * Provided for call sites that want the gradient without mounting the SVG.
 */
export function getHeroCanvasStyle(section: string | null): {
  background: string;
} {
  const visual = getSectionVisual(section);
  return { background: sectionGradient(visual) };
}
