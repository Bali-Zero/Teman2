type Point = Readonly<{
  x: number;
  y: number;
}>;

type ContourField = Readonly<{
  centerX: number;
  centerY: number;
  radiusX: number;
  radiusY: number;
  rotation: number;
  levels: number;
  points: number;
  irregularity: number;
}>;

type ContourPath = Readonly<{
  d: string;
  isCoastline: boolean;
  isIndexLine: boolean;
}>;

const STUDIO_ATMOSPHERE_SEED = 340788;

const CONTOUR_FIELDS: readonly ContourField[] = [
  {
    centerX: 112,
    centerY: 290,
    radiusX: 340,
    radiusY: 225,
    rotation: -0.18,
    levels: 8,
    points: 18,
    irregularity: 0.17,
  },
  {
    centerX: 1220,
    centerY: 590,
    radiusX: 315,
    radiusY: 410,
    rotation: 0.24,
    levels: 8,
    points: 20,
    irregularity: 0.14,
  },
  {
    centerX: 350,
    centerY: 1355,
    radiusX: 360,
    radiusY: 250,
    rotation: 0.12,
    levels: 8,
    points: 18,
    irregularity: 0.19,
  },
  {
    centerX: 1090,
    centerY: 1570,
    radiusX: 245,
    radiusY: 315,
    rotation: -0.34,
    levels: 8,
    points: 16,
    irregularity: 0.16,
  },
] as const;

/** Mulberry32 is small, deterministic and sufficient for decorative geometry.
 * It runs once at module evaluation; render itself contains no randomness. */
function seededRandom(seed: number): () => number {
  let state = seed >>> 0;

  return () => {
    state += 1831565813;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function fixed(value: number): string {
  return value.toFixed(2);
}

/** Closed Catmull-Rom contour converted to cubic Bezier segments. */
function toClosedBezierPath(points: readonly Point[]): string {
  const lastIndex = points.length - 1;
  let path = `M ${fixed(points[0].x)} ${fixed(points[0].y)}`;

  for (let index = 0; index <= lastIndex; index += 1) {
    const previous = points[(index - 1 + points.length) % points.length];
    const current = points[index];
    const next = points[(index + 1) % points.length];
    const afterNext = points[(index + 2) % points.length];
    const control1 = {
      x: current.x + (next.x - previous.x) / 6,
      y: current.y + (next.y - previous.y) / 6,
    };
    const control2 = {
      x: next.x - (afterNext.x - current.x) / 6,
      y: next.y - (afterNext.y - current.y) / 6,
    };

    path += ` C ${fixed(control1.x)} ${fixed(control1.y)} ${fixed(control2.x)} ${fixed(control2.y)} ${fixed(next.x)} ${fixed(next.y)}`;
  }

  return `${path} Z`;
}

function buildContourPaths(seed: number): readonly ContourPath[] {
  const random = seededRandom(seed);

  return CONTOUR_FIELDS.flatMap((field, fieldIndex) => {
    const phase = random() * Math.PI * 2;
    const baseNoise = Array.from(
      { length: field.points },
      () => random() * 2 - 1,
    );

    return Array.from({ length: field.levels }, (_, level) => {
      const scale = 1 - level * 0.105;
      const ringPhase = phase + level * 0.07;
      const points = Array.from({ length: field.points }, (__, pointIndex) => {
        const angle = (pointIndex / field.points) * Math.PI * 2;
        const modulation =
          1 +
          baseNoise[pointIndex] * field.irregularity +
          Math.sin(angle * 3 + ringPhase) * 0.045 +
          Math.sin(angle * 5 - phase) * 0.025;
        const localX = Math.cos(angle) * field.radiusX * scale * modulation;
        const localY = Math.sin(angle) * field.radiusY * scale * modulation;
        const cosRotation = Math.cos(field.rotation);
        const sinRotation = Math.sin(field.rotation);

        return {
          x: field.centerX + localX * cosRotation - localY * sinRotation,
          y: field.centerY + localX * sinRotation + localY * cosRotation,
        };
      });

      return {
        d: toClosedBezierPath(points),
        isCoastline: level === field.levels - 1,
        isIndexLine: (level + fieldIndex) % 3 === 0,
      };
    });
  });
}

const CONTOUR_PATHS = buildContourPaths(STUDIO_ATMOSPHERE_SEED);

/**
 * Non-informative hydrographic atmosphere for the Studio. Geometry is built
 * from a constant seed at module evaluation, so SSR and hydration receive the
 * exact same paths. The two SVGs are intentionally hidden as one decorative
 * layer: contours carry place; static fractal noise gives the navy paper tooth.
 */
export function StudioAtmosphere() {
  return (
    <div
      aria-hidden="true"
      className="bz-shs-atmosphere"
      data-testid="studio-atmosphere"
    >
      <svg
        className="bz-shs-bathymetry"
        focusable="false"
        preserveAspectRatio="xMidYMid slice"
        viewBox="0 0 1440 1800"
        xmlns="http://www.w3.org/2000/svg"
      >
        <g fill="none">
          {CONTOUR_PATHS.map((contour, index) => (
            <path
              key={index}
              d={contour.d}
              data-contour="true"
              opacity={
                contour.isCoastline ? 0.9 : contour.isIndexLine ? 0.72 : 0.42
              }
              stroke={
                contour.isCoastline
                  ? "var(--bz-shs-bathy-coast)"
                  : "var(--bz-shs-bathy-line)"
              }
              strokeWidth={contour.isIndexLine ? 1.05 : 0.72}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </g>
      </svg>

      <svg
        className="bz-shs-grain"
        focusable="false"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <filter
            id="bz-shs-paper-grain"
            colorInterpolationFilters="sRGB"
            filterRes="180 180"
            x="0"
            y="0"
            width="100%"
            height="100%"
          >
            <feTurbulence
              baseFrequency="0.72"
              numOctaves="3"
              seed="37"
              stitchTiles="stitch"
              type="fractalNoise"
            />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <pattern
            id="bz-shs-paper-grain-pattern"
            width="180"
            height="180"
            patternUnits="userSpaceOnUse"
          >
            <rect width="180" height="180" filter="url(#bz-shs-paper-grain)" />
          </pattern>
        </defs>
        <rect
          width="100%"
          height="100%"
          fill="url(#bz-shs-paper-grain-pattern)"
        />
      </svg>

      <style>{`
        .bz-shs-studio {
          --surface-raised: color-mix(
            in srgb,
            var(--surface-base-solid, var(--surface-deep)) 76%,
            var(--surface-deep) 24%
          );
          --bz-shs-bathy-line: color-mix(
            in srgb,
            var(--text-primary) 7%,
            transparent
          );
          --bz-shs-bathy-coast: color-mix(
            in srgb,
            var(--text-primary) 10%,
            transparent
          );
          position: relative;
          min-height: 100vh;
          isolation: isolate;
          color: var(--text-primary);
        }

        .bz-shs-content {
          position: relative;
          z-index: 1;
        }

        .bz-shs-atmosphere {
          position: fixed;
          z-index: 0;
          inset: 0;
          overflow: clip;
          pointer-events: none;
          user-select: none;
          contain: paint;
          background: var(--surface-base);
        }

        .bz-shs-atmosphere::before {
          position: absolute;
          inset: 0;
          background: color-mix(
            in srgb,
            var(--surface-deep) 55%,
            transparent
          );
          content: "";
        }

        .bz-shs-grain {
          position: absolute;
          display: block;
          width: 100%;
          height: 100%;
          inset: 0;
        }

        .bz-shs-bathymetry {
          position: absolute;
          display: block;
          width: 104%;
          height: 104%;
          inset: -2%;
          opacity: 0.82;
          transform: translate3d(0, 0, 0) scale(1.01);
          transform-origin: center top;
        }

        .bz-shs-grain {
          opacity: 0.028;
          mix-blend-mode: overlay;
        }

        .bz-shs-layout > main > div,
        .bz-shs-layout > aside > .bz-shs-memo,
        .bz-shs-verdict-stack > section:not(.bz-shs-save-plan-bar):not(.custody-map) {
          box-shadow:
            inset 0 1px 0
              color-mix(in srgb, var(--text-primary) 11%, transparent),
            inset 0 -1px 0
              color-mix(in srgb, var(--text-primary) 2%, transparent);
        }

        .bz-shs-layout > main > div,
        .bz-shs-layout > aside > .bz-shs-memo {
          border-color: color-mix(
            in srgb,
            var(--text-primary) 8%,
            transparent
          ) !important;
        }

        .bz-shs-scenario-toggle-trigger {
          color: var(--accent-funnel-text) !important;
        }

        .bz-shs-verdict-stack section[data-verdict-band] > p:first-child,
        .bz-shs-memo [data-known="false"] dd {
          opacity: 1 !important;
        }

        @keyframes bz-shs-bathymetric-drift {
          from {
            transform: translate3d(0, 0, 0) scale(1.01);
          }
          to {
            transform: translate3d(0, -1.25%, 0) scale(1.025);
          }
        }

        @supports (animation-timeline: scroll(root block)) {
          .bz-shs-bathymetry {
            animation: bz-shs-bathymetric-drift linear both;
            animation-timeline: scroll(root block);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .bz-shs-bathymetry {
            animation: none !important;
            transform: none !important;
          }
        }

        @media print {
          .bz-shs-atmosphere {
            display: none !important;
          }

          .bz-shs-studio {
            margin: 0 !important;
            background: transparent !important;
          }
        }
      `}</style>
    </div>
  );
}
