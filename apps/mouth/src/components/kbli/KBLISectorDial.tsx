"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export interface DialSection {
  id: string;
  nameEn: string;
  /** SECTION_VISUALS[id].label — the short name the list prints in full */
  shortName: string;
  codeCount: number;
}

const SIZE = 260;
const C = SIZE / 2;
const R_OUT = 96;
const R_IN = 72;
const R_TICK = 101;
const R_COUNT = 117;
const GAP_DEG = 0.9;
/** A segment narrower than this carries no engraved letter/count on the rim. */
const LABEL_MIN_DEG = 11;

const INK = "var(--r19-structure, #233D52)";
const COPPER = "var(--kbli-accent, #A44B36)";

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
 * The sector dial — the Navigator's instrument face, engraved in ONE ink.
 *
 * One ring, one segment per non-empty KBLI 2025 section, each segment's angle
 * = its codeCount over the total (both read from `getSections()` at render,
 * never a literal). Council v2 (2026-09-26): no per-section rainbow — the
 * segments are the R19 structure slate in two alternating weights, the
 * section letter is engraved on the band and its count on the rim, and only
 * the ACTIVE section turns copper.
 *
 * The ORDERED LIST under the ring is the truth: every section is a real link
 * to /kbli/sectors/[id] with its full short name and count in text. The SVG is
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
    return sections.map((s, i) => {
      const sweep = (s.codeCount / sum) * 360;
      const start = cursor + GAP_DEG / 2;
      const end = cursor + sweep - GAP_DEG / 2;
      const mid = cursor + sweep / 2;
      cursor += sweep;
      return {
        ...s,
        start,
        end: Math.max(end, start + 0.4),
        mid,
        sweep,
        weight: i % 2 === 0 ? 0.92 : 0.62,
      };
    });
  }, [sections, sum]);

  const current = segments.find((s) => s.id === active) ?? null;

  return (
    <div className="kbli-dial grid grid-cols-1 items-center gap-5">
      <div className="relative mx-auto w-full max-w-[13rem] sm:max-w-[14rem]">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          className="block h-auto w-full"
          aria-hidden="true"
          focusable="false"
        >
          {/* bezel: 72 minor ticks, 4 major, slate */}
          <g stroke={INK} strokeLinecap="round">
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
                  opacity={major ? 0.75 : 0.4}
                />
              );
            })}
          </g>
          {segments.map((s) => {
            const on = active === s.id;
            return (
              <path
                key={s.id}
                d={arcPath(s.start, s.end)}
                fill={on ? COPPER : INK}
                opacity={on ? 1 : active === null ? s.weight : 0.22}
                onMouseEnter={() => setActive(s.id)}
                onMouseLeave={() => setActive(null)}
                onClick={() => router.push(`/kbli/sectors/${s.id}`)}
                style={{ cursor: "pointer", transition: "opacity 160ms" }}
              />
            );
          })}
          {/* engraved letters on the band, counts on the rim */}
          <g
            style={{ fontFamily: "var(--font-sans)", pointerEvents: "none" }}
            textAnchor="middle"
            dominantBaseline="central"
          >
            {segments
              .filter((s) => s.sweep >= LABEL_MIN_DEG)
              .map((s) => {
                const [lx, ly] = polar((R_IN + R_OUT) / 2, s.mid);
                const [cx, cy] = polar(R_COUNT, s.mid);
                const on = active === s.id;
                return (
                  <g key={s.id}>
                    <text
                      x={lx}
                      y={ly}
                      fontSize={10}
                      fontWeight={700}
                      fill="var(--kbli-bg-surface, #FFFCF7)"
                    >
                      {s.id}
                    </text>
                    <text
                      x={cx}
                      y={cy}
                      fontSize={9.5}
                      fontWeight={600}
                      fill={on ? COPPER : "var(--kbli-text-secondary, #58626B)"}
                      style={{ fontVariantNumeric: "tabular-nums" }}
                    >
                      {s.codeCount}
                    </text>
                  </g>
                );
              })}
          </g>
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
                transform: `rotate(${current.mid}deg)`,
                transformOrigin: `${C}px ${C}px`,
                transition: "transform 220ms ease-out",
              }}
            >
              <line
                x1={C}
                y1={C - R_IN + 4}
                x2={C}
                y2={C - R_TICK - 8}
                stroke={COPPER}
                strokeWidth={1.6}
                strokeLinecap="round"
              />
            </g>
          )}
        </svg>
        {/* centre readout (decorative mirror of the list; aria-hidden) */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-[29%] text-center"
        >
          {current ? (
            <>
              <span className="kbli-figure text-[28px] leading-none text-[var(--kbli-accent)]">
                {current.codeCount.toLocaleString("en-US")}
              </span>
              <span className="mt-1 line-clamp-3 text-[10px] font-semibold leading-tight text-[var(--kbli-text-secondary)]">
                {current.id} · {current.nameEn}
              </span>
            </>
          ) : (
            <>
              <span className="kbli-figure text-[30px] leading-none text-[var(--kbli-text-primary)]">
                {totalCodes.toLocaleString("en-US")}
              </span>
              <span className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--kbli-text-secondary)]">
                codes
              </span>
            </>
          )}
        </div>
      </div>

      <ol
        aria-label="KBLI 2025 sections"
        data-kbli-dial-list=""
        className="grid grid-cols-1 gap-x-6 sm:grid-cols-2"
      >
        {sections.map((s) => (
          <li key={s.id}>
            <Link
              href={`/kbli/sectors/${s.id}`}
              onMouseEnter={() => setActive(s.id)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(s.id)}
              onBlur={() => setActive(null)}
              title={s.nameEn}
              className="group flex min-h-[44px] items-center gap-2.5 border-b border-[var(--kbli-border)] py-1 text-[13px] leading-snug text-[var(--kbli-text-primary)] no-underline focus-visible:outline-[3px] focus-visible:outline-offset-[3px] focus-visible:outline-[var(--kbli-accent)] lg:min-h-[32px]"
            >
              <span className="w-3 shrink-0 font-bold text-[var(--kbli-text-secondary)] group-hover:text-[var(--kbli-accent)]">
                {s.id}
              </span>
              <span className="min-w-0 flex-1 group-hover:text-[var(--kbli-accent)]">
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
