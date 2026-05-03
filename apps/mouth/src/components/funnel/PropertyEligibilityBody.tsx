"use client";
import { useMemo, useState } from "react";
import { trackPropertyAnalyzeCTA, trackPropertyWACTA } from "@/lib/analytics";
import { parseCoordinates } from "./parse-coordinates";

// Semantic color tokens for the verdict label — fallback hex ensures
// correct visual even if the --color-success/warning/danger CSS vars
// aren't wired on a theme. Matches Balizero copper + complementary palette.
const LABEL_STYLE: Record<
  string,
  { color: string; bg: string; border: string }
> = {
  GREEN: {
    color: "var(--color-success, #3ecf8e)",
    bg: "color-mix(in srgb, #3ecf8e 14%, transparent)",
    border: "color-mix(in srgb, #3ecf8e 40%, transparent)",
  },
  YELLOW: {
    color: "var(--color-warning, #e8a849)",
    bg: "color-mix(in srgb, #e8a849 16%, transparent)",
    border: "color-mix(in srgb, #e8a849 48%, transparent)",
  },
  RED: {
    color: "var(--color-danger, #f05252)",
    bg: "color-mix(in srgb, #f05252 14%, transparent)",
    border: "color-mix(in srgb, #f05252 44%, transparent)",
  },
};

function VerdictPill({ label }: { label: string }) {
  const s = LABEL_STYLE[label.toUpperCase()] ?? {
    color: "var(--text-primary)",
    bg: "var(--surface-sunken, rgba(255,255,255,0.06))",
    border: "var(--color-border-subtle)",
  };
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.35em",
        padding: "0.15em 0.7em",
        borderRadius: 999,
        fontSize: "0.85em",
        fontWeight: 700,
        letterSpacing: "0.04em",
        color: s.color,
        background: s.bg,
        border: `1px solid ${s.border}`,
      }}
    >
      <span
        aria-hidden
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: s.color,
          boxShadow: `0 0 8px ${s.color}`,
        }}
      />
      {label.toUpperCase()}
    </span>
  );
}

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

  // Dedupe opportunities by title_en (backend occasionally returns repeats)
  // and keep at most 5 distinct entries for the UI.
  const opportunities = useMemo(() => {
    const list = result?.opportunities ?? [];
    const seen = new Set<string>();
    const out: AnalyzeOpportunity[] = [];
    for (const o of list) {
      const key = `${o.title_en ?? ""}|${o.category_en ?? ""}`.toLowerCase();
      if (!seen.has(key) && o.title_en) {
        seen.add(key);
        out.push(o);
      }
      if (out.length >= 5) break;
    }
    return out;
  }, [result]);

  async function analyze() {
    setError(null);
    setResult(null);
    const parsed = parseCoordinates(coord);
    if (!parsed) {
      setError(
        `Format not recognized. Try decimals (e.g. -8.65, 115.13), Google Maps format (e.g. 8°39'17.4"S 115°08'22.3"E) or a Google Maps link.`,
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
        setError(`Error ${res.status}: zone not analyzable.`);
        return;
      }
      setResult((await res.json()) as AnalyzeResponse);
    } catch (e) {
      setError("Network error. Please retry.");
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
          placeholder={`Paste from Google Maps (e.g. 8°39'17.4"S 115°08'22.3"E) or lat, lng`}
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
          {loading ? "Analyzing…" : "Analyze"}
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
            position: "relative",
            marginTop: "var(--space-6)",
            padding: "var(--space-6)",
            borderRadius: "var(--radius-lg)",
            // Liquid glassmorphism — same pattern as FunnelFeature v2 homepage.
            // Saturated funnel-accent tint + backdrop blur + inner highlight.
            background:
              "linear-gradient(135deg, color-mix(in srgb, var(--accent-funnel) 22%, transparent) 0%, color-mix(in srgb, var(--accent-funnel) 10%, transparent) 55%, color-mix(in srgb, var(--accent-funnel) 6%, transparent) 100%)",
            border:
              "1px solid color-mix(in srgb, var(--accent-funnel) 32%, transparent)",
            backdropFilter: "blur(24px) saturate(160%)",
            WebkitBackdropFilter: "blur(24px) saturate(160%)",
            boxShadow:
              "inset 0 1px 0 rgba(255,255,255,0.10), inset 0 0 60px color-mix(in srgb, var(--accent-funnel) 8%, transparent), 0 12px 40px color-mix(in srgb, var(--accent-funnel) 20%, transparent)",
            overflow: "hidden",
          }}
        >
          {/* inner sheen for liquid-glass top highlight */}
          <span
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              background:
                "radial-gradient(ellipse 60% 35% at 30% 0%, rgba(255,255,255,0.09) 0%, transparent 70%)",
            }}
          />
          <div style={{ position: "relative" }}>
            <h2 style={{ marginTop: 0, fontSize: "1.5rem" }}>
              Zone:{" "}
              {result.zone?.code
                ? `${result.zone.code} — ${result.zone.name ?? ""}`
                : "n/a"}
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
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "var(--space-3)",
                  alignItems: "center",
                  margin: "var(--space-3) 0",
                  color: "var(--text-secondary)",
                }}
              >
                <span>
                  Investment score:{" "}
                  <strong style={{ color: "var(--text-primary)" }}>
                    {result.verdict.score ?? "—"}/100
                  </strong>
                </span>
                {result.verdict.label ? (
                  <VerdictPill label={result.verdict.label} />
                ) : null}
                {result.verdict.risk_level ? (
                  <span>
                    Risk:{" "}
                    <strong style={{ color: "var(--text-primary)" }}>
                      {result.verdict.risk_level}
                    </strong>
                  </span>
                ) : null}
              </div>
            ) : null}
            {opportunities.length ? (
              <div style={{ margin: "var(--space-4) 0" }}>
                <strong>KBLI opportunities open to PMA:</strong>
                <ul
                  style={{
                    marginTop: "var(--space-2)",
                    paddingLeft: 0,
                    color: "var(--text-secondary)",
                    listStyle: "none",
                    display: "grid",
                    gap: "var(--space-2)",
                  }}
                >
                  {opportunities.map((o, i) => (
                    <li
                      key={`${o.title_en}-${i}`}
                      style={{
                        display: "flex",
                        flexWrap: "wrap",
                        gap: "0.5em",
                        alignItems: "center",
                      }}
                    >
                      <span style={{ color: "var(--text-primary)" }}>
                        {o.title_en}
                      </span>
                      {o.category_en ? (
                        <span
                          style={{
                            fontSize: "0.78em",
                            padding: "0.15em 0.55em",
                            borderRadius: 999,
                            background:
                              "color-mix(in srgb, var(--accent-funnel) 12%, transparent)",
                            border:
                              "1px solid color-mix(in srgb, var(--accent-funnel) 24%, transparent)",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {o.category_en}
                        </span>
                      ) : null}
                      {o.pma_open ? (
                        <span
                          style={{
                            fontSize: "0.72em",
                            padding: "0.12em 0.5em",
                            borderRadius: 999,
                            background:
                              "color-mix(in srgb, #3ecf8e 14%, transparent)",
                            border:
                              "1px solid color-mix(in srgb, #3ecf8e 35%, transparent)",
                            color: "var(--color-success, #3ecf8e)",
                            fontWeight: 600,
                            letterSpacing: "0.04em",
                          }}
                        >
                          PMA
                        </span>
                      ) : null}
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
                Talk to Bali Zero
              </a>
            </div>
          </div>
        </article>
      ) : null}
    </section>
  );
}
