"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import type { Language } from "../_lib/flow";
import {
  ATLAS_ASSET_BASE,
  ATLAS_BRANCHES,
  ISLAND_LABELS,
  WORLD_LABELS,
  atlasBranchFor,
  atlasCopy,
  isAtlasCategoryKey,
  type AtlasScene,
  type AtlasSceneId,
} from "../_lib/atlas-scenes";

/**
 * Decoration only — scenery never decides or implies eligibility (BUILD-SPEC
 * §0.8). Root is `aria-hidden` with no focusable descendant and no text a
 * screen reader needs; every affordance a visitor can act on lives in
 * `QuestionScreen`/`OracleShell`, never here.
 */
export interface OracleSceneryProps {
  scene: AtlasScene;
  motion: boolean;
  language: Language;
}

const PERMIT_CLIP_PATH =
  "M0 0 H1586 V166 C1490 239 1400 368 1341 470 C1269 609 1238 716 1193 807 C1020 852 808 878 620 929 C551 949 493 969 449 992 H0 Z";

export function OracleScenery({ scene, motion, language }: OracleSceneryProps) {
  const clipId = useId();
  const [paperReady, setPaperReady] = useState(false);
  const [depthReady, setDepthReady] = useState(false);
  const prevSceneIdRef = useRef<AtlasSceneId | null>(null);
  const [arrival, setArrival] = useState(false);

  // Layered paper arrival (ported locally from `P/src/App.jsx`'s
  // `paperArrival` state): plays once when the interview crosses from the
  // world scene into the permit scene, but ONLY as decoration — it never
  // gates the permit question's own buttons, which QuestionScreen renders
  // and wires independently of this component.
  useEffect(() => {
    const previous = prevSceneIdRef.current;
    prevSceneIdRef.current = scene.id;
    if (
      previous === "world" &&
      scene.id === "paper" &&
      motion &&
      paperReady &&
      depthReady
    ) {
      setArrival(true);
      const timer = window.setTimeout(() => setArrival(false), 650);
      return () => window.clearTimeout(timer);
    }
    setArrival(false);
    return undefined;
  }, [scene.id, motion, paperReady, depthReady]);

  useEffect(() => {
    if (!motion) setArrival(false);
  }, [motion]);

  if (scene.layout === "stage") {
    return (
      <div
        className="oracle-atlas-scenery"
        aria-hidden="true"
        data-paper-arrival={arrival ? "on" : undefined}
      >
        <div className="oracle-atlas-map-stage">
          <img
            className="oracle-atlas-map oracle-atlas-map--island"
            src={`${ATLAS_ASSET_BASE}indonesia.webp`}
            alt=""
          />
          <img
            className="oracle-atlas-map oracle-atlas-map--globe"
            src={`${ATLAS_ASSET_BASE}world.webp`}
            alt=""
          />
        </div>
        <div className="oracle-atlas-labels oracle-atlas-labels--islands">
          {ISLAND_LABELS[language].map(([label, x, y]) => (
            <span key={label} style={{ left: `${x}%`, top: `${y}%` }}>
              {label}
            </span>
          ))}
        </div>
        <div className="oracle-atlas-labels oracle-atlas-labels--world">
          {WORLD_LABELS[language].map(([label, x, y]) => (
            <span key={label} style={{ left: `${x}%`, top: `${y}%` }}>
              {label}
            </span>
          ))}
          <span className="oracle-atlas-place-label">
            {atlasCopy(language, "place.indonesia")}
          </span>
        </div>
        {/* FIX-ROUND-2 K1/Q2: the permit art (paper still + depth preload +
            layered SVG) only needs to exist once the interview has reached
            "world" (so it is ready by the time "paper" arrives) — mounting
            it on "entry" too made the entry scene fetch two extra images it
            never shows. */}
        {(scene.id === "world" || scene.id === "paper") && (
          <div
            className={`oracle-atlas-permit-art${paperReady ? " oracle-atlas-permit-art--ready" : ""}`}
          >
            <img
              className="oracle-atlas-permit-still"
              src={`${ATLAS_ASSET_BASE}permit-paper.webp`}
              alt=""
              onLoad={() => setPaperReady(true)}
              onError={() => setPaperReady(false)}
            />
            <img
              className="oracle-atlas-depth-preload"
              src={`${ATLAS_ASSET_BASE}permit-depth.webp`}
              alt=""
              onLoad={() => setDepthReady(true)}
              onError={() => setDepthReady(false)}
            />
            {depthReady && (
              <svg
                className="oracle-atlas-paper-layers"
                viewBox="0 0 1586 992"
                preserveAspectRatio="xMaxYMid slice"
                focusable="false"
              >
                <defs>
                  <clipPath id={clipId}>
                    <path d={PERMIT_CLIP_PATH} />
                  </clipPath>
                </defs>
                <g className="oracle-atlas-paper-depth">
                  <image
                    href={`${ATLAS_ASSET_BASE}permit-depth.webp`}
                    width="1586"
                    height="992"
                  />
                </g>
                <g className="oracle-atlas-paper-foreground">
                  <image
                    href={`${ATLAS_ASSET_BASE}permit-paper.webp`}
                    width="1586"
                    height="992"
                    clipPath={`url(#${clipId})`}
                  />
                </g>
              </svg>
            )}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="oracle-atlas-scenery" aria-hidden="true">
      <LandscapeArt scene={scene} motion={motion} />
    </div>
  );
}

/** Ports `Scenery` from `P/src/App.jsx`: preloads the next asset off-DOM,
 * only animates the arrival when motion is on AND the load was fast enough
 * to plausibly read as a hand-off rather than a stall, and never removes a
 * successfully-shown image except by replacing it with the next one that
 * actually loaded. */
function LandscapeArt({
  scene,
  motion,
}: {
  scene: AtlasScene;
  motion: boolean;
}) {
  const [loaded, setLoaded] = useState<{
    asset: string;
    animate: boolean;
  } | null>(null);
  const artRef = useRef<HTMLDivElement>(null);
  const motionRef = useRef(motion);
  motionRef.current = motion;

  useEffect(() => {
    let cancelled = false;
    const started = performance.now();
    const img = new Image();
    img.onload = () => {
      if (!cancelled) {
        setLoaded({
          asset: scene.asset,
          animate: performance.now() - started < 400,
        });
      }
    };
    // FIX-ROUND-2 K3: a failed load keeps whatever image was already shown
    // (never blanks the scenery) — `setLoaded(null)` used to wipe it.
    img.onerror = () => {};
    img.src = `${ATLAS_ASSET_BASE}${scene.asset}`;
    return () => {
      cancelled = true;
      // FIX-ROUND-2 K2: a superseded preload (rapid category hover) is
      // actually aborted, not just ignored — clearing the handlers and the
      // source stops the browser from finishing/decoding a request whose
      // result no one will read.
      img.onload = null;
      img.onerror = null;
      img.src = "";
    };
  }, [scene.asset]);

  useLayoutEffect(() => {
    if (!loaded?.animate || !motionRef.current) return undefined;
    const animation = artRef.current?.animate?.(
      [
        { opacity: 0, transform: "scale(1.018)" },
        { opacity: 1, transform: "scale(1)" },
      ],
      { duration: 520, easing: "cubic-bezier(.2,.7,.2,1)" },
    );
    return () => animation?.cancel();
  }, [loaded]);

  useEffect(() => {
    if (!motion) {
      artRef.current
        ?.getAnimations?.()
        .forEach((animation) => animation.cancel());
    }
  }, [motion]);

  return (
    <div className="oracle-atlas-scene-art" data-art={loaded?.asset}>
      <div ref={artRef} className="oracle-atlas-scene-art-inner">
        {loaded && <img src={`${ATLAS_ASSET_BASE}${loaded.asset}`} alt="" />}
      </div>
      <div className="oracle-atlas-scene-wash" />
    </div>
  );
}

export interface AtlasGlyphProps {
  category: string;
}

/** Verbatim port of `Glyph` from `P/src/App.jsx`: an unrecognised category
 * falls back to `ATLAS_BRANCHES.other`'s path rather than rendering an
 * empty `<path>`. */
export function AtlasGlyph({ category }: AtlasGlyphProps) {
  const branch = atlasBranchFor(category) ?? ATLAS_BRANCHES.other;
  return (
    <svg
      className="oracle-atlas-glyph"
      viewBox="0 0 120 84"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path d={branch.glyph} />
    </svg>
  );
}

export interface AtlasBranchCaptionProps {
  category: string | null | undefined;
  language: Language;
  /** Hub variant (on the category/watershed question itself): shows the
   * hovered/focused branch's line, or the hub line when nothing is
   * currently previewed. */
  hub?: boolean;
}

/** Decorative aside naming the chosen (or hovered, in the hub variant)
 * branch — never an affordance, always `aria-hidden`. Hub variant is called
 * with the currently previewed category (possibly none, showing the hub
 * line); the branch variant is called with the already-chosen category. */
export function AtlasBranchCaption({
  category,
  language,
  hub = false,
}: AtlasBranchCaptionProps) {
  const validCategory = isAtlasCategoryKey(category) ? category : null;
  const line = validCategory
    ? atlasCopy(language, `branch.${validCategory}.line`)
    : atlasCopy(language, "hub.line");
  return (
    <aside
      className={`oracle-atlas-branch-caption${hub ? " oracle-atlas-branch-caption--hub" : ""}`}
      aria-hidden="true"
    >
      <AtlasGlyph category={validCategory ?? "other"} />
      <span>{line}</span>
    </aside>
  );
}
