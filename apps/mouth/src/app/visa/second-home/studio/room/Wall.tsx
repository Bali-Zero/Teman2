"use client";

import Image from "next/image";
import type { ReactNode } from "react";
import { rosterBySlug } from "@/data/team-roster";
import { getCopy } from "@/lib/secondhome-studio/copy";

/** Ari is read from the roster (name, role, department, photo) — never a
 *  bio written here. If the roster ever drops her, the frame drops too. */
function ariLine(): { name: string; role: string; photo: string } | null {
  const ari = rosterBySlug("ari");
  if (!ari || !ari.photo) return null;
  const dept = ari.dept.charAt(0).toUpperCase() + ari.dept.slice(1);
  return { name: ari.name, role: `${ari.role}, ${dept}`, photo: ari.photo };
}

export interface WallProps {
  /** The labelled step rail ("Where we are"); null on the verdict stage. */
  chart: ReactNode | null;
  /** The custody map, product-gated by the caller exactly as before. */
  map: ReactNode | null;
}

/**
 * THE WALL — what hangs where you look up from the desk: Ari's portrait, the
 * framed chart of the interview and, once a deposit route is on the table,
 * the framed custody map. On narrow screens it dissolves (`display:contents`)
 * so each frame can take its own place in the single column: portrait and
 * chart as a strip above the desk, the map after it.
 */
export function Wall({ chart, map }: WallProps) {
  const ari = ariLine();
  return (
    <aside className="bz-shs-wall" aria-label={getCopy("room.wall.label")}>
      {ari ? (
        <figure className="bz-shs-frame bz-shs-frame--ari">
          <Image
            className="bz-shs-ari-photo"
            src={ari.photo}
            alt=""
            width={56}
            height={56}
          />
          <figcaption className="bz-shs-ari-caption">
            <span className="bz-shs-ari-name">
              {ari.name} · {ari.role}
            </span>
            <span className="bz-shs-ari-line">
              {getCopy("room.wall.deskLine")}
            </span>
          </figcaption>
        </figure>
      ) : null}
      {chart ? (
        <figure className="bz-shs-frame bz-shs-frame--chart">
          <figcaption className="bz-shs-frame-title">
            {getCopy("room.wall.chartTitle")}
          </figcaption>
          {chart}
        </figure>
      ) : null}
      {map ? (
        <figure className="bz-shs-frame bz-shs-frame--map">
          <figcaption className="bz-shs-frame-title">
            {getCopy("room.wall.mapTitle")}
          </figcaption>
          {map}
        </figure>
      ) : null}
    </aside>
  );
}
