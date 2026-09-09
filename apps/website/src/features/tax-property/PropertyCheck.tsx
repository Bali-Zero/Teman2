"use client";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { parseCoordinates } from "./coordinates";
import { projectAnalysis, type PropertyAnalysis } from "./property-contract";
import { AnalysisResult } from "./AnalysisResult";
import { ZoneAtlas } from "./ZoneAtlas";
import styles from "./tools.module.css";

export function PropertyCheck({ atlas = false }: { atlas?: boolean }) {
  const [coord, setCoord] = useState("");
  const [kbli, setKbli] = useState("");
  const [pma, setPma] = useState(true);
  const [area, setArea] = useState("");
  const [price, setPrice] = useState("");
  const [result, setResult] = useState<PropertyAnalysis | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  function edit(action: () => void): void {
    action();
    setResult(null);
    setError("");
  }
  async function analyze(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (loading) return;
    setResult(null);
    setError("");
    const point = parseCoordinates(coord);
    if (!point) {
      setError(
        "Enter valid decimal coordinates, degrees/minutes/seconds, or a Google Maps URL containing coordinates. Short map links need the coordinates copied from the opened map.",
      );
      return;
    }
    if ((area && !price) || (price && !area)) {
      setError(
        "Enter both land area and purchase price for an investment estimate, or leave both blank.",
      );
      return;
    }
    setLoading(true);
    try {
      const response = await fetch("/api/property/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...point,
          ...(kbli ? { kbli_code: kbli, is_pma: pma } : {}),
          ...(area && price
            ? { land_size_m2: Number(area), price_idr: Number(price) }
            : {}),
        }),
        signal: AbortSignal.timeout(20_000),
      });
      if (!response.ok) {
        setError(
          response.status === 503
            ? "Property analysis is not connected in this preview. Your coordinates have not been sent to the property service. You can still prepare a zoning review below."
            : "The property service could not complete this analysis. No result has been inferred. Please retry.",
        );
        return;
      }
      const data = projectAnalysis(await response.json());
      if (!["analyzed", "outside_coverage"].includes(data.status))
        throw new Error("Invalid result");
      setResult(data);
      requestAnimationFrame(() => resultRef.current?.focus());
    } catch {
      setError(
        "The analysis did not complete. Check your connection and retry; no result has been inferred.",
      );
    } finally {
      setLoading(false);
    }
  }
  const form: ReactNode = (
    <form onSubmit={analyze} className={styles.form}>
      <fieldset disabled={loading}>
        <legend className={styles.eyebrow}>01 / Locate the property</legend>
        <label className={styles.field}>
          Property coordinates
          <input
            name="coordinates"
            autoComplete="off"
            value={coord}
            required
            onChange={(e) => edit(() => setCoord(e.target.value))}
            placeholder="−8.65, 115.13"
            aria-describedby="coordinate-help"
          />
        </label>
        <p id="coordinate-help" className={styles.small}>
          Paste latitude, longitude; degrees/minutes/seconds; or a Google Maps
          link containing coordinates.
        </p>
        <details className={styles.optional}>
          <summary>Refine with business & investment inputs</summary>
          <div className={styles.formGrid}>
            <label className={styles.field}>
              KBLI code <span>(optional)</span>
              <input
                name="kbli"
                inputMode="numeric"
                pattern="[0-9]{5}"
                maxLength={5}
                value={kbli}
                onChange={(e) => edit(() => setKbli(e.target.value))}
                placeholder="5-digit activity code"
              />
            </label>
            <label className={styles.field}>
              Business structure
              <select
                disabled={!kbli}
                value={pma ? "pma" : "domestic"}
                onChange={(e) => edit(() => setPma(e.target.value === "pma"))}
              >
                <option value="pma">Foreign investment / PMA</option>
                <option value="domestic">Domestic investment</option>
              </select>
            </label>
            <label className={styles.field}>
              Land area <span>(m², optional)</span>
              <input
                name="area"
                type="number"
                min="0.01"
                max="1000000000"
                step="any"
                value={area}
                onChange={(e) => edit(() => setArea(e.target.value))}
              />
            </label>
            <label className={styles.field}>
              Purchase price <span>(IDR, optional)</span>
              <input
                name="price"
                type="number"
                min="1"
                max="10000000000000000"
                step="any"
                value={price}
                onChange={(e) => edit(() => setPrice(e.target.value))}
              />
            </label>
          </div>
          <p className={styles.small}>
            Area and purchase price are used together by the connected
            investment calculator. No service prices are supplied here.
          </p>
          <a className={styles.textLink} href="/kbli">
            Find a KBLI code →
          </a>
        </details>
        <button className={styles.primary} type="submit">
          {loading ? "Checking the site…" : "Analyze property →"}
        </button>
      </fieldset>
      {loading && (
        <p role="status">
          Requesting zoning records and the service’s assessment…
        </p>
      )}
      {error && (
        <p role="alert" className={styles.error}>
          {error}
        </p>
      )}
    </form>
  );
  return (
    <>
      {atlas ? (
        <div className={styles.atlasGrid}>
          <ZoneAtlas
            selected={parseCoordinates(coord)}
            onSelect={(point) => {
              if (!loading)
                edit(() =>
                  setCoord(`${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`),
                );
            }}
          />
          {form}
        </div>
      ) : (
        <div className={styles.split}>
          {form}
          <aside className={styles.dossier}>
            <p className={styles.eyebrow}>A site-specific first look</p>
            <h2>Location before assumption.</h2>
            <p>
              See the zoning record, building parameters, reported restrictions
              and activities returned for the exact point.
            </p>
            <a className={styles.lightLink} href="/prime">
              Explore the zoning atlas →
            </a>
            <div className={styles.asideRule}>
              <p>
                Title and ownership, permits, legal structure and tax treatment
                require review of the documents. A map score does not settle
                these questions.
              </p>
            </div>
          </aside>
        </div>
      )}
      <div ref={resultRef} tabIndex={-1} className={styles.resultFocus}>
        {result && <AnalysisResult result={result} />}
      </div>
      <section className={styles.nextStep}>
        <div>
          <p className={styles.eyebrow}>Continue the review</p>
          <h2>The map is one part of the dossier.</h2>
          <p>
            Bring the title records, site plans, building approvals and proposed
            agreement into the same conversation.
          </p>
        </div>
        <a className={styles.secondary} href="/zoning">
          Prepare a zoning review →
        </a>
      </section>
      {atlas && (
        <aside className={styles.notice}>
          <strong>Continue in your Prime workspace</strong>
          <p>
            Use the public atlas to explore zoning and check a location. Open
            your secure Prime workspace for the Google 3D view, client overlays,
            portfolio records and proposal creation.
          </p>
          <a className={styles.textLink} href="/legacy/prime">
            Open Prime workspace →
          </a>
        </aside>
      )}
    </>
  );
}
