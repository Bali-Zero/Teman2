"use client";

import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import type { RefObject } from "react";

/**
 * What the head of the road is doing. `head` = a question, the trailhead or
 * the confirmation; `checking` = waiting for the engine; the rest are the
 * five outcome states, each drawn as its own kind of arrival.
 */
export type RoadHeadStatus =
  | "head"
  | "checking"
  | "SUPPORTED_CANDIDATES"
  | "NO_SUPPORTED_PATH"
  | "NEEDS_INPUT"
  | "HUMAN_REVIEW_REQUIRED"
  | "TEMPORARILY_UNAVAILABLE";

interface Point {
  x: number;
  y: number;
}
interface RecordPoint extends Point {
  status: "ink" | "pencil" | "ghost";
  pruned: number;
}
interface Geometry {
  w: number;
  h: number;
  x: number;
  records: RecordPoint[];
  ghosts: RecordPoint[];
  head: Point | null;
  exits: Point[];
}

const EMPTY: Geometry = {
  w: 0,
  h: 0,
  x: 0,
  records: [],
  ghosts: [],
  head: null,
  exits: [],
};

const useIsoLayoutEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

/**
 * The road, drawn BEHIND the list it describes (field study: one semantic
 * DOM list is the truth, the scene is aria-hidden). Every coordinate is
 * measured from the rendered `<li>` rows, the head's h1 and the head's own
 * options, so the drawing can never disagree with the controls: ink = what
 * you said, dashed pencil = unsure or said before an edit, faint stubs =
 * the options you did not take, copper only on the last stretch into a
 * suggested path. No loop, no glow; one ≤280ms draw-in per new stretch,
 * none under reduced motion.
 */
export function RoadCanvas({
  containerRef,
  headStatus,
  layoutKey,
  reducedMotion,
}: {
  containerRef: RefObject<HTMLElement | null>;
  headStatus: RoadHeadStatus;
  layoutKey: string;
  reducedMotion: boolean;
}) {
  const [geo, setGeo] = useState<Geometry>(EMPTY);

  const measure = useCallback(() => {
    const root = containerRef.current;
    if (!root) return;
    const box = root.getBoundingClientRect();
    const pad = Number.parseFloat(getComputedStyle(root).paddingLeft) || 40;
    const x = Math.round(pad / 2);
    const centreY = (el: Element) => {
      const r = el.getBoundingClientRect();
      return Math.round(r.top - box.top + r.height / 2);
    };
    const nodes = Array.from(
      root.querySelectorAll<HTMLElement>("[data-road-node]"),
    ).map((el) => ({
      x,
      y: centreY(el),
      status: (el.dataset.roadNode ?? "ink") as RecordPoint["status"],
      pruned: Number(el.dataset.roadPruned ?? 0),
    }));
    const headEl = root.querySelector<HTMLElement>(".oracle-roadhead");
    const h1 = headEl?.querySelector("h1") ?? null;
    let head: Point | null = null;
    if (h1) {
      const r = h1.getBoundingClientRect();
      head = { x, y: Math.round(r.top - box.top + Math.min(r.height / 2, 22)) };
    } else if (headEl) {
      head = {
        x,
        y: Math.round(headEl.getBoundingClientRect().top - box.top + 18),
      };
    }
    const exits = headEl
      ? Array.from(
          headEl.querySelectorAll<HTMLElement>(
            ".oracle-option-card, .oracle-tile, [data-road-exit]",
          ),
        )
          .map((el) => el.getBoundingClientRect())
          .filter((r) => r.width > 0 && r.height > 0)
          .slice(0, 14)
          .map((r) => ({
            x: Math.round(r.left - box.left),
            y: Math.round(r.top - box.top + r.height / 2),
          }))
      : [];
    const next: Geometry = {
      w: Math.round(box.width),
      h: Math.round(box.height),
      x,
      records: nodes.filter((n) => n.status !== "ghost"),
      ghosts: nodes.filter((n) => n.status === "ghost"),
      head,
      exits,
    };
    setGeo((prev) =>
      JSON.stringify(prev) === JSON.stringify(next) ? prev : next,
    );
  }, [containerRef]);

  useIsoLayoutEffect(() => {
    measure();
  }, [measure, layoutKey]);

  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    const observer =
      typeof ResizeObserver === "function"
        ? new ResizeObserver(() => measure())
        : null;
    observer?.observe(root);
    window.addEventListener("resize", measure);
    void document.fonts?.ready.then(measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [containerRef, measure]);

  if (geo.w === 0 || geo.h === 0) {
    return (
      <svg
        className="oracle-road__canvas"
        aria-hidden="true"
        focusable="false"
      />
    );
  }

  const { x, records, ghosts, head, exits } = geo;
  const spine: Point[] = head ? [...records, head] : records;
  const arrived = headStatus !== "head" && headStatus !== "checking";

  return (
    <svg
      className="oracle-road__canvas"
      aria-hidden="true"
      focusable="false"
      width={geo.w}
      height={geo.h}
      viewBox={`0 0 ${geo.w} ${geo.h}`}
      data-road-head-status={headStatus}
    >
      {/* the trailhead cap — only once a record exists. With the head alone
          the cap sat 6px above its ring and the pair read as a "♂" glyph
          (council CRITIQUE-v2 Oracle #5, confirmed on the 01 render). */}
      {records.length > 0 && (
        <line
          className="oracle-road__cap"
          x1={x - 7}
          x2={x + 7}
          y1={spine[0].y - 14}
          y2={spine[0].y - 14}
        />
      )}
      {records.length > 0 && (
        <line
          className="oracle-road__seg"
          x1={x}
          x2={x}
          y1={spine[0].y - 14}
          y2={spine[0].y}
        />
      )}

      {/* the walked road, one stretch per answer */}
      {spine.slice(1).map((b, index) => {
        const a = spine[index];
        const last = index === spine.length - 2 && head !== null;
        const pencil =
          (a as RecordPoint).status === "pencil" ||
          (b as RecordPoint).status === "pencil" ||
          (last && headStatus === "checking");
        const copper = last && headStatus === "SUPPORTED_CANDIDATES";
        const cls = [
          "oracle-road__seg",
          pencil ? "oracle-road__seg--pencil" : "",
          copper ? "oracle-road__seg--copper" : "",
          last && !pencil && !reducedMotion ? "oracle-road__seg--fresh" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <line
            key={`seg-${index}-${b.y}`}
            className={cls}
            x1={x}
            x2={x}
            y1={a.y}
            y2={b.y}
            pathLength={1}
          />
        );
      })}

      {/* options not taken: faint stubs at every answered node */}
      {records.map((p, index) =>
        Array.from({ length: Math.min(p.pruned, 4) }, (_, k) => {
          const n = Math.min(p.pruned, 4);
          const degrees = n === 1 ? -30 : -55 + (k * 110) / (n - 1);
          const angle = (degrees * Math.PI) / 180;
          return (
            <line
              key={`stub-${index}-${k}`}
              className="oracle-road__stub"
              x1={x}
              y1={p.y}
              x2={Math.round(x + 11 * Math.cos(angle))}
              y2={Math.round(p.y + 11 * Math.sin(angle))}
            />
          );
        }),
      )}

      {/* the roads leaving the head: one per option, a fan at the crossroads */}
      {head &&
        exits.map((exit, index) => {
          const bend = Math.min(18, Math.abs(exit.y - head.y));
          const down = exit.y >= head.y ? 1 : -1;
          const d = `M ${x} ${head.y} V ${exit.y - down * bend} Q ${x} ${exit.y} ${x + bend} ${exit.y} H ${exit.x}`;
          return (
            <path
              key={`exit-${index}`}
              className={`oracle-road__exit${arrived ? " oracle-road__exit--back" : ""}`}
              d={d}
            />
          );
        })}

      {/* answers given before an edit, now in pencil below the head */}
      {head && ghosts.length > 0 && (
        <line
          className="oracle-road__seg oracle-road__seg--pencil"
          x1={x}
          x2={x}
          y1={head.y}
          y2={ghosts[ghosts.length - 1].y}
        />
      )}
      {ghosts.map((p, index) => (
        <circle
          key={`ghost-${index}`}
          className="oracle-road__node-ghost"
          cx={x}
          cy={p.y}
          r={4}
        />
      ))}

      {records.map((p, index) => (
        <circle
          key={`node-${index}`}
          className={
            p.status === "pencil"
              ? "oracle-road__node-pencil"
              : "oracle-road__node-ink"
          }
          cx={x}
          cy={p.y}
          r={4.5}
        />
      ))}

      {head && <HeadMark x={x} y={head.y} status={headStatus} />}
    </svg>
  );
}

function HeadMark({
  x,
  y,
  status,
}: {
  x: number;
  y: number;
  status: RoadHeadStatus;
}) {
  switch (status) {
    case "SUPPORTED_CANDIDATES":
      return (
        <g className="oracle-road__arrival">
          <circle className="oracle-road__arrival-ring" cx={x} cy={y} r={8} />
          <circle className="oracle-road__arrival-dot" cx={x} cy={y} r={3.5} />
        </g>
      );
    case "NO_SUPPORTED_PATH":
      return (
        <g className="oracle-road__edge">
          <line x1={x - 10} x2={x + 10} y1={y} y2={y} />
          <line x1={x - 6} x2={x + 6} y1={y + 5} y2={y + 5} />
        </g>
      );
    case "NEEDS_INPUT":
      return (
        <g className="oracle-road__pencil-ring">
          <circle cx={x} cy={y} r={11} />
          <circle className="oracle-road__pencil-dot" cx={x} cy={y} r={3} />
        </g>
      );
    case "HUMAN_REVIEW_REQUIRED":
      return (
        <g className="oracle-road__specialist">
          <circle cx={x} cy={y} r={8} />
          <circle className="oracle-road__specialist-dot" cx={x} cy={y} r={3} />
        </g>
      );
    case "TEMPORARILY_UNAVAILABLE":
    case "checking":
      return (
        <g className="oracle-road__pause">
          <circle cx={x} cy={y} r={9} />
        </g>
      );
    default:
      return (
        <g className="oracle-road__head">
          <circle className="oracle-road__head-ring" cx={x} cy={y} r={8} />
          <circle className="oracle-road__head-dot" cx={x} cy={y} r={3} />
        </g>
      );
  }
}
