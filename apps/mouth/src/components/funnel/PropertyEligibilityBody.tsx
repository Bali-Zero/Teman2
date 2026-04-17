"use client";
import { useState } from "react";
import { trackPropertyAnalyzeCTA, trackPropertyWACTA } from "@/lib/analytics";
import { parseCoordinates } from "./parse-coordinates";

type AnalyzeVerdict = {
  can_invest?: boolean;
  risk_level?: "LOW" | "MEDIUM" | "HIGH" | string;
  score?: number;
  label?: "GREEN" | "YELLOW" | "RED" | string;
};

type AnalyzeZone = {
  code?: string;
  name?: string;
  desa?: string;
  kecamatan?: string;
  kdb?: string;
  klb?: string;
  tb?: string;
};

type AnalyzeOpportunity = {
  title_en?: string;
  category_en?: string;
  pma_open?: boolean;
};

type AnalyzeResponse = {
  status?: string;
  zone?: AnalyzeZone;
  verdict?: AnalyzeVerdict;
  opportunities?: AnalyzeOpportunity[];
  sea_distance_m?: number;
  [key: string]: unknown;
};

export function PropertyEligibilityBody() {
  const [coord, setCoord] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function analyze() {
    setError(null);
    setResult(null);
    const parsed = parseCoordinates(coord);
    if (!parsed) {
      setError(
        `Formato non riconosciuto. Prova con decimali (es. -8.65, 115.13), formato Google Maps (es. 8°39'17.4"S 115°08'22.3"E) o un link di Google Maps.`,
      );
      return;
    }
    const { lat, lng } = parsed;
    trackPropertyAnalyzeCTA(lat, lng);
    setLoading(true);
    try {
      const res = await fetch("/api/property/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lat, lng }),
      });
      if (!res.ok) {
        setError(`Errore ${res.status}: zona non analizzabile.`);
        return;
      }
      setResult((await res.json()) as AnalyzeResponse);
    } catch (e) {
      setError("Errore di rete. Riprova.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <div
        style={{
          display: "grid",
          gap: "var(--space-3)",
          gridTemplateColumns: "1fr auto",
          alignItems: "stretch",
          marginBottom: "var(--space-4)",
        }}
      >
        <input
          placeholder={`Incolla da Google Maps (es. 8°39'17.4"S 115°08'22.3"E) o lat, lng`}
          value={coord}
          onChange={(e) => setCoord(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void analyze();
          }}
          style={{
            padding: "var(--space-3) var(--space-4)",
            width: "100%",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-border-subtle)",
            background: "var(--surface-raised)",
            color: "var(--text-primary)",
            fontSize: "1rem",
          }}
        />
        <button
          onClick={() => void analyze()}
          disabled={loading}
          style={{
            padding: "var(--space-3) var(--space-5, 1.25rem)",
            borderRadius: "var(--radius-md)",
            background: "var(--accent-funnel)",
            color: "var(--text-on-accent)",
            border: "none",
            fontWeight: 600,
            cursor: loading ? "wait" : "pointer",
            opacity: loading ? 0.6 : 1,
            whiteSpace: "nowrap",
          }}
        >
          {loading ? "Analizzo…" : "Analizza"}
        </button>
      </div>
      {error ? (
        <p
          style={{
            color: "var(--color-danger, #d4574d)",
            margin: "var(--space-2) 0 var(--space-4)",
          }}
          role="alert"
        >
          {error}
        </p>
      ) : null}
      {result ? (
        <article
          style={{
            marginTop: "var(--space-6)",
            padding: "var(--space-6)",
            borderRadius: "var(--radius-lg)",
            background: "var(--surface-raised)",
            border: "1px solid var(--color-border-subtle)",
          }}
        >
          <h2 style={{ marginTop: 0, fontSize: "1.5rem" }}>
            Zona:{" "}
            {result.zone?.code
              ? `${result.zone.code} — ${result.zone.name ?? ""}`
              : "n/d"}
            {result.zone?.desa ? ` · ${result.zone.desa}` : ""}
          </h2>
          <p
            style={{
              color: "var(--text-secondary)",
              margin: "var(--space-2) 0",
            }}
          >
            KDB: {result.zone?.kdb ?? "—"} · KLB: {result.zone?.klb ?? "—"} ·
            TB: {result.zone?.tb ?? "—"}
          </p>
          {result.verdict ? (
            <p
              style={{
                color: "var(--text-secondary)",
                margin: "var(--space-2) 0",
              }}
            >
              Investment score: {result.verdict.score ?? "—"}/100 ·{" "}
              {result.verdict.label ?? "—"} · Risk:{" "}
              {result.verdict.risk_level ?? "—"}
            </p>
          ) : null}
          {result.opportunities && result.opportunities.length ? (
            <div style={{ margin: "var(--space-4) 0" }}>
              <strong>Opportunità KBLI aperte a PMA:</strong>
              <ul
                style={{
                  marginTop: "var(--space-2)",
                  paddingLeft: "var(--space-5, 1.25rem)",
                  color: "var(--text-secondary)",
                }}
              >
                {result.opportunities.slice(0, 5).map((o, i) => (
                  <li key={i}>
                    {o.title_en}
                    {o.category_en ? ` · ${o.category_en}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <div
            style={{
              display: "flex",
              gap: "var(--space-3)",
              marginTop: "var(--space-4)",
              flexWrap: "wrap",
            }}
          >
            <a
              href="https://wa.me/628213107363?text=Property%20analysis%20Bali%20Zero"
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
              onClick={() => trackPropertyWACTA()}
              style={{
                padding: "var(--space-2) var(--space-4)",
                borderRadius: "var(--radius-md)",
                background: "var(--accent-funnel)",
                color: "var(--text-on-accent)",
                textDecoration: "none",
                fontWeight: 600,
              }}
            >
              Parla con Bali Zero
            </a>
          </div>
        </article>
      ) : null}
    </section>
  );
}
