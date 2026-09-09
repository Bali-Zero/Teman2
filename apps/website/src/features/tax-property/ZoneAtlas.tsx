"use client";
import { useMemo, useState } from "react";
import type { Coordinate } from "./coordinates";
import { projectZones, type ZoneFeature } from "./property-contract";
import styles from "./tools.module.css";

type Bounds = {
  minLng: number;
  maxLng: number;
  minLat: number;
  maxLat: number;
};
export function ringsOf(feature: ZoneFeature): number[][][] {
  return feature.geometry.type === "Polygon"
    ? (feature.geometry.coordinates as number[][][])
    : (feature.geometry.coordinates as number[][][][]).flat();
}
export function zoneBounds(features: ZoneFeature[]): Bounds | null {
  if (!features.length) return null;
  let minLng = Infinity,
    maxLng = -Infinity,
    minLat = Infinity,
    maxLat = -Infinity;
  for (const feature of features)
    for (const ring of ringsOf(feature))
      for (const [lng, lat] of ring) {
        minLng = Math.min(minLng, lng);
        maxLng = Math.max(maxLng, lng);
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
      }
  const dx = Math.max(maxLng - minLng, 0.001) * 0.04,
    dy = Math.max(maxLat - minLat, 0.001) * 0.04;
  return {
    minLng: minLng - dx,
    maxLng: maxLng + dx,
    minLat: minLat - dy,
    maxLat: maxLat + dy,
  };
}
export function ZoneAtlas({
  selected,
  onSelect,
}: {
  selected: Coordinate | null;
  onSelect: (point: Coordinate) => void;
}) {
  const [features, setFeatures] = useState<ZoneFeature[]>([]);
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">(
    "idle",
  );
  const [selectedZone, setSelectedZone] = useState("");
  const [compared, setCompared] = useState<string[]>([]);
  const [colors, setColors] = useState(true);
  const [zoom, setZoom] = useState(1);
  const bounds = useMemo(() => zoneBounds(features), [features]);
  const codes = useMemo(
    () =>
      [...new Set(features.map((f) => String(f.properties.zone_code ?? "")))]
        .filter(Boolean)
        .sort(),
    [features],
  );
  const project = (point: Coordinate): [number, number] =>
    bounds
      ? [
          ((point.lng - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * 800,
          ((bounds.maxLat - point.lat) / (bounds.maxLat - bounds.minLat)) * 560,
        ]
      : [0, 0];
  const center = selected && bounds ? project(selected) : [400, 280];
  const viewWidth = 800 / zoom,
    viewHeight = 560 / zoom;
  const viewX = Math.max(
    0,
    Math.min(800 - viewWidth, center[0] - viewWidth / 2),
  );
  const viewY = Math.max(
    0,
    Math.min(560 - viewHeight, center[1] - viewHeight / 2),
  );
  async function load(): Promise<void> {
    setState("loading");
    try {
      const response = await fetch("/api/prime/zones-geojson", {
        signal: AbortSignal.timeout(20_000),
      });
      if (!response.ok) throw new Error("Unavailable");
      const data = projectZones(await response.json());
      if (!data.features.length) throw new Error("Empty");
      setFeatures(data.features);
      setState("ready");
    } catch {
      setState("error");
    }
  }
  function selectZone(code: string): void {
    setSelectedZone(code);
    const feature = features.find((f) => f.properties.zone_code === code);
    // Select a recorded boundary vertex rather than inventing an interior centroid.
    const point = feature && ringsOf(feature)[0]?.[0];
    if (point) onSelect({ lat: point[1], lng: point[0] });
  }
  return (
    <section className={styles.atlas} aria-labelledby="atlas-title">
      <div className={styles.sectionHeading}>
        <div>
          <p className={styles.eyebrow}>Prime / Public zoning atlas</p>
          <h2 id="atlas-title">Read the land.</h2>
        </div>
        <span className={styles.north} aria-label="North is up">
          N ↑
        </span>
      </div>
      {state !== "ready" ? (
        <div className={styles.mapEmpty}>
          <div>
            <span className={styles.eyebrow}>Zoning geometry</span>
            <h3>
              {state === "loading"
                ? "Loading the zoning layer…"
                : state === "error"
                  ? "The zoning layer is unavailable."
                  : "Explore the recorded zones."}
            </h3>
            <p>
              {state === "error"
                ? "The map service is unavailable or has no polygons to display. No zoning boundaries have been drawn. You can still enter coordinates for a separate analysis."
                : "Load the service’s public polygons, choose a site and review it with the property form."}
            </p>
            <button
              className={styles.secondary}
              onClick={() => void load()}
              disabled={state === "loading"}
            >
              {state === "loading"
                ? "Loading…"
                : state === "error"
                  ? "Retry zoning layer"
                  : "Load zoning layer"}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className={styles.mapControls}>
            <label>
              <input
                type="checkbox"
                checked={colors}
                onChange={(e) => setColors(e.target.checked)}
              />{" "}
              Zone colors
            </label>
            <div>
              <button
                aria-label="Zoom in"
                onClick={() => setZoom((z) => Math.min(8, z * 2))}
                disabled={zoom === 8}
              >
                +
              </button>
              <button
                aria-label="Zoom out"
                onClick={() => setZoom((z) => Math.max(1, z / 2))}
                disabled={zoom === 1}
              >
                −
              </button>
              <button onClick={() => setZoom(1)}>Reset view</button>
            </div>
          </div>
          <svg
            className={styles.map}
            viewBox={`${viewX} ${viewY} ${viewWidth} ${viewHeight}`}
            preserveAspectRatio="none"
            role="img"
            aria-label="Recorded zoning polygons. Choose a point with the map or enter coordinates in the property form."
            onClick={(event) => {
              if (!bounds) return;
              const rect = event.currentTarget.getBoundingClientRect();
              const x =
                  viewX +
                  ((event.clientX - rect.left) / rect.width) * viewWidth,
                y =
                  viewY +
                  ((event.clientY - rect.top) / rect.height) * viewHeight;
              onSelect({
                lng:
                  bounds.minLng + (x / 800) * (bounds.maxLng - bounds.minLng),
                lat:
                  bounds.maxLat - (y / 560) * (bounds.maxLat - bounds.minLat),
              });
            }}
          >
            <title>Public zoning geometry</title>
            {features.map((feature, index) => (
              <path
                key={index}
                d={ringsOf(feature)
                  .map(
                    (ring) =>
                      ring
                        .map(
                          ([lng, lat], pointIndex) =>
                            `${pointIndex ? "L" : "M"}${project({ lat, lng }).join(",")}`,
                        )
                        .join(" ") + " Z",
                  )
                  .join(" ")}
                fill={
                  colors &&
                  /^#[a-f\d]{6}$/i.test(String(feature.properties.color))
                    ? String(feature.properties.color)
                    : "#d6ded4"
                }
                fillOpacity={0.72}
                fillRule="evenodd"
                stroke={
                  feature.properties.zone_code === selectedZone
                    ? "#1D2C3B"
                    : "#F7F4EE"
                }
                strokeWidth={
                  feature.properties.zone_code === selectedZone ? 2 : 0.6
                }
                vectorEffect="non-scaling-stroke"
              >
                <title>
                  {String(
                    feature.properties.zone_type ??
                      feature.properties.zone_code,
                  )}
                </title>
              </path>
            ))}
            {selected && (
              <g transform={`translate(${project(selected).join(",")})`}>
                <circle
                  r={7 / zoom}
                  fill="#A44B36"
                  stroke="#fff"
                  strokeWidth={2 / zoom}
                />
                <circle
                  r={14 / zoom}
                  fill="none"
                  stroke="#1D2C3B"
                  strokeWidth={1 / zoom}
                />
              </g>
            )}
          </svg>
          <p className={styles.small}>
            {features.length} recorded polygons · 2D zoning diagram; not a
            cadastral survey. Select a point, then use “Analyze property”. Zoom
            is centred on the selected point.
          </p>
          <div className={styles.mapControls}>
            <label className={styles.field}>
              Inspect a zone
              <select
                value={selectedZone}
                onChange={(e) => selectZone(e.target.value)}
              >
                <option value="">Choose zone code</option>
                {codes.map((code) => (
                  <option key={code}>{code}</option>
                ))}
              </select>
            </label>
            <button
              className={styles.secondary}
              disabled={
                !selectedZone ||
                compared.includes(selectedZone) ||
                compared.length >= 3
              }
              onClick={() => setCompared((prev) => [...prev, selectedZone])}
            >
              Compare zone
            </button>
          </div>
          {selectedZone && (
            <p className={styles.small}>
              Zone selection places a marker on a recorded boundary vertex.
              Enter the exact site coordinates before analysis.
            </p>
          )}
          {compared.length > 0 && (
            <section aria-label="Zone comparison">
              <h3>Compare recorded limits</h3>
              <div className={styles.compare}>
                {compared.map((code) => {
                  const feature = features.find(
                    (f) => f.properties.zone_code === code,
                  )!;
                  return (
                    <article key={code}>
                      <div className={styles.sectionHeading}>
                        <h4>{code}</h4>
                        <button
                          className={styles.quiet}
                          aria-label={`Remove ${code}`}
                          onClick={() =>
                            setCompared((prev) =>
                              prev.filter((v) => v !== code),
                            )
                          }
                        >
                          Remove
                        </button>
                      </div>
                      <p>{String(feature.properties.zone_type ?? "")}</p>
                      <dl>
                        {[
                          ["Coverage / KDB", feature.properties.kdb],
                          ["Maximum floors", feature.properties.max_floors],
                          [
                            "Maximum height (m)",
                            feature.properties.max_height_meters,
                          ],
                        ].map(([label, value]) => (
                          <div key={String(label)}>
                            <dt>{label}</dt>
                            <dd>
                              {value === undefined || value === null
                                ? "Not supplied"
                                : String(value)}
                            </dd>
                          </div>
                        ))}
                      </dl>
                      <p className={styles.small}>
                        Values from the first recorded polygon for this code; a
                        site-specific analysis is still required.
                      </p>
                    </article>
                  );
                })}
              </div>
            </section>
          )}
        </>
      )}
    </section>
  );
}
