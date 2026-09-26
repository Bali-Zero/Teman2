"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export interface DialSection {
  id: string;
  nameEn: string;
  /** SECTION_VISUALS[id].label — the short name the list can hold */
  shortName: string;
  codeCount: number;
  /** SECTION_VISUALS[id].accent (lib/kbli-cover-design.ts) */
  color: string;
}

const SIZE = 240;
const C = SIZE / 2;
const R_OUT = 104;
const R_IN = 78;
const R_TICK = 112;
const GAP_DEG = 0.9;

function polar(r: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180;
  return [C + r * Math.cos(rad), C + r * Math.sin(rad)];
}

function arcPath(start: number, end: number): string {
  const [x1, y1] = polar(R_OUT, start);
  const [x2, y2] = polar(R_OUT, end);
  const [x3, y3] = polar(R_IN, end);
  const [x4, y4] = polar(R_IN, start);
  const large = end - start > 180 ? 1 : 0;
  const f = (n: number) => n.toFixed(2);
  return [
    `M${f(x1)} ${f(y1)}`,
    `A${R_OUT} ${R_OUT} 0 ${large} 1 ${f(x2)} ${f(y2)}`,
    `L${f(x3)} ${f(y3)}`,
    `A${R_IN} ${R_IN} 0 ${large} 0 ${f(x4)} ${f(y4)}`,
    "Z",
  ].join(" ");
}

/**
 * The sector dial — the Navigator's instrument face.
 *
 * One ring, one segment per non-empty KBLI 2025 section, each segment's angle
 * = its codeCount over the total (both read from `getSections()` at render,
 * never a literal), each coloured by the section's SECTION_VISUALS accent.
 *
 * The ORDERED LIST beside the ring is the truth: every section is a real link
 * to /kbli/sectors/[id] with its name and count in text. The SVG is
 * aria-hidden decoration that follows the list — hovering or focusing an
 * entry swings the needle to its segment and reads it in the centre; pointer
 * users may also click a segment (same destination as the link).
 */
export function KBLISectorDial({
  sections,
  totalCodes,
}: {
  sections: DialSection[];
  totalCodes: number;
}) {
  const router = useRouter();
  const [active, setActive] = React.useState<string | null>(null);
  const sum = sections.reduce((n, s) => n + s.codeCount, 0);

  const segments = React.useMemo(() => {
    let cursor = 0;
    return sections.map((s) => {
      const sweep = (s.codeCount / sum) * 360;
      const start = cursor + GAP_DEG / 2;
      const end = cursor + sweep - GAP_DEG / 2;
      const mid = cursor + sweep / 2;
      cursor += sweep;
      return { ...s, start, end: Math.max(end, start + 0.4), mid };
    });
  }, [sections, sum]);

  const current = segments.find((s) => s.id === active) ?? null;
  const needleDeg = current ? current.mid : 0;

  return (
    <div className="kbli-dial grid items-center gap-6 sm:grid-cols-[minmax(0,15rem)_1fr] lg:grid-cols-1 xl:grid-cols-[minmax(0,15rem)_1fr]">
      <div className="relative mx-auto w-full max-w-[15rem]">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="block h-auto w-full"
          aria-hidden="true"
          focusable="false"
        >
          {/* bezel: 72 minor ticks, 4 major */}
          <g stroke="var(--kbli-text-primary)" strokeLinecap="round">
            {Array.from({ length: 72 }, (_, i) => {
              const deg = i * 5;
              const major = deg % 90 === 0;
              const [x1, y1] = polar(R_TICK, deg);
              const [x2, y2] = polar(major ? R_TICK + 7 : R_TICK + 3, deg);
              return (
                <line
                  key={deg}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  strokeWidth={major ? 1.1 : 0.6}
                  opacity={major ? 0.7 : 0.35}
                />
              );
            })}
          </g>
          <circle
            cx={C}
            cy={C}
            r={R_OUT + 2.5}
            fill="none"
            stroke="var(--kbli-text-primary)"
            strokeWidth={0.5}
            opacity={0.35}
          />
          {segments.map((s) => (
            <path
              key={s.id}
              d={arcPath(s.start, s.end)}
              fill={s.color}
              opacity={active === null || active === s.id ? 1 : 0.28}
              onMouseEnter={() => setActive(s.id)}
              onMouseLeave={() => setActive(null)}
              onClick={() => router.push(`/kbli/sectors/${s.id}`)}
              style={{ cursor: "pointer", transition: "opacity 160ms" }}
            />
          ))}
          <circle
            cx={C}
            cy={C}
            r={R_IN - 3}
            fill="var(--kbli-bg-surface)"
            stroke="var(--kbli-border)"
            strokeWidth={0.75}
          />
          {current && (
            <g
              style={{
                transform: `rotate(${needleDeg}deg)`,
                transformOrigin: `${C}px ${C}px`,
                transition: "transform 220ms ease-out",
              }}
            >
              <line
                x1={C}
                y1={C - R_IN + 4}
                x2={C}
                y2={C - R_TICK - 6}
                stroke="var(--kbli-accent)"
                strokeWidth={1.6}
                strokeLinecap="round"
              />
            </g>
          )}
        </svg>
        {/* centre readout (decorative mirror of the list; aria-hidden) */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-[26%] text-center"
        >
          {current ? (
            <>
              <span className="kbli-figure text-[30px] leading-none text-[var(--kbli-text-primary)]">
                {current.codeCount.toLocaleString("en-US")}
              </span>
              <span className="mt-1 line-clamp-3 text-[10.5px] font-semibold leading-tight text-[var(--kbli-text-secondary)]">
                {current.id} · {current.nameEn}
              </span>
            </>
          ) : (
            <>
              <span className="kbli-figure text-[32px] leading-none text-[var(--kbli-text-primary)]">
                {totalCodes.toLocaleString("en-US")}
              </span>
              <span className="mt-1 text-[10.5px] font-bold uppercase tracking-[0.14em] text-[var(--kbli-text-secondary)]">
                codes
              </span>
            </>
          )}
        </div>
      </div>

      <ol
        aria-label="KBLI 2025 sections"
        data-kbli-dial-list=""
        className="grid grid-cols-2 gap-x-4 sm:grid-cols-2"
      >
        {sections.map((s) => (
          <li key={s.id}>
            <Link
              href={`/kbli/sectors/${s.id}`}
              onMouseEnter={() => setActive(s.id)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(s.id)}
              onBlur={() => setActive(null)}
              className="group flex min-h-[44px] items-center gap-2 border-b border-[var(--kbli-border)] text-[13px] leading-tight text-[var(--kbli-text-primary)] no-underline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-[var(--kbli-accent)]"
            >
              <span
                aria-hidden="true"
                className="h-2.5 w-2.5 shrink-0 rounded-[1px]"
                style={{ background: s.color }}
              />
              <span className="w-3 shrink-0 font-bold text-[var(--kbli-text-secondary)]">
                {s.id}
              </span>
              <span
                title={s.nameEn}
                className="min-w-0 flex-1 truncate group-hover:text-[var(--kbli-accent)]"
              >
                {s.shortName}
              </span>
              <span className="kbli-figure shrink-0 text-[14px] text-[var(--kbli-text-secondary)]">
                {s.codeCount.toLocaleString("en-US")}
              </span>
            </Link>
          </li>
        ))}
      </ol>
    </div>
  );
}
