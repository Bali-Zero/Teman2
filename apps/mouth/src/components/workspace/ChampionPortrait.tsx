"use client";

import { useState, type CSSProperties } from "react";
import Image from "next/image";
import { initialsOf } from "@/lib/team-initials";
import { cn } from "@/lib/utils";

/**
 * Where the face sits on each approved staff photo: [x %, y %, zoom] of the
 * source bitmap. The staff cards print the name, role and logo beside the
 * face, so a `face` portrait zooms the circle onto the face instead of the
 * whole card. Display framing only — the bitmaps stay untouched, and a file
 * missing here keeps the plain centred crop.
 */
const FACE_FRAMING: Record<string, readonly [number, number, number]> = {
  "adit.jpg": [63.5, 36, 2.2],
  "angel.jpg": [49, 43, 2.15],
  "ari.jpg": [50, 34, 2.45],
  "asya.jpg": [49, 42, 2.05],
  "candra.jpg": [49.5, 41, 2.35],
  "damar.jpg": [54, 29, 2.35],
  "dea.jpg": [48, 46, 2.2],
  "dewaayu.jpg": [52, 42, 2.4],
  "krisna-20260927.jpg": [55, 33, 2.45],
  "subhi.jpg": [53.5, 40, 2.25],
  "surya.jpg": [52, 40, 2],
  "veronika.jpg": [55, 43, 2.2],
  "vino.jpg": [48, 33, 2.3],
  "ruslana.jpg": [50, 37, 1.6],
  "zainal-ceo.jpg": [52, 33, 1.95],
};

/**
 * The leaderboard's avatar_url comes from team_members.avatar, which still
 * names a superseded photo; the approved one ships under a versioned name.
 * Exact local paths only — anything else goes through the checks unchanged.
 */
const SUPERSEDED_SOURCES = new Map<string, string>([
  ["/static/team/krisna.jpg", "/static/team/krisna-20260927.jpg"],
]);

/**
 * object-position pins the focal point of the covered image at the same
 * percentage of the box; the transform then moves that point to the centre
 * and zooms around it.
 */
function faceFraming(src: string): CSSProperties | undefined {
  const framing = FACE_FRAMING[src.slice(src.lastIndexOf("/") + 1)];
  if (!framing) return undefined;
  const [x, y, zoom] = framing;
  return {
    objectPosition: `${x}% ${y}%`,
    transformOrigin: "0 0",
    transform: `translate(50%, 50%) scale(${zoom}) translate(-${x}%, -${y}%)`,
  };
}

export function ChampionPortrait({
  name,
  src,
  className,
  face = false,
  sizes = "(max-width: 640px) 120px, 220px",
}: {
  name: string;
  src?: string | null;
  className?: string;
  face?: boolean;
  sizes?: string;
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const source = src ? (SUPERSEDED_SOURCES.get(src) ?? src) : src;
  const safeSource =
    source && /^\/static\/team\/[a-z0-9_-]+\.(jpg|jpeg|png|webp)$/i.test(source)
      ? source
      : null;
  return (
    <span
      className={cn(
        "relative isolate inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-[var(--bz-card-hover)] text-[var(--bz-copper-text)]",
        className,
      )}
    >
      {safeSource && safeSource !== failedSource ? (
        <Image
          src={safeSource}
          alt={name}
          fill
          sizes={sizes}
          className="object-cover"
          style={face ? faceFraming(safeSource) : undefined}
          onError={() => setFailedSource(safeSource)}
        />
      ) : (
        <span role="img" aria-label={name} className="text-2xl font-bold">
          {initialsOf(name)}
        </span>
      )}
    </span>
  );
}
