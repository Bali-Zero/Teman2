"use client";
import { useMemo, useState, type CSSProperties } from "react";
import {
  trackPropertyAnalyzeCTA,
  trackPropertyWACTA,
  trackPropertyBuyerSelected,
  trackPropertyUseSelected,
} from "@/lib/analytics";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { parseCoordinates } from "./parse-coordinates";

// Semantic state tokens (APPROVED/WARNING/REJECTED, verdict GREEN/YELLOW/RED).
// Fallback hex only — the real color comes from the CSS var when it's wired.
const STATE_STYLE: Record<
  string,
  { color: string; bg: string; border: string }
> = {
  GREEN: {
    color: "var(--color-success, #2f7a52)",
    bg: "color-mix(in srgb, var(--color-success, #2f7a52) 12%, transparent)",
    border:
      "color-mix(in srgb, var(--color-success, #2f7a52) 35%, transparent)",
  },
  YELLOW: {
    color: "var(--color-warning, #a4752b)",
    bg: "color-mix(in srgb, var(--color-warning, #a4752b) 14%, transparent)",
    border:
      "color-mix(in srgb, var(--color-warning, #a4752b) 40%, transparent)",
  },
  RED: {
    color: "var(--color-danger, #a4402f)",
    bg: "color-mix(in srgb, var(--color-danger, #a4402f) 12%, transparent)",
    border: "color-mix(in srgb, var(--color-danger, #a4402f) 40%, transparent)",
  },
};

// KBLIEye audit states -> the traffic-light family StatePill already knows.
const KBLI_STATE_TO_LABEL: Record<string, string> = {
  APPROVED: "GREEN",
  WARNING: "YELLOW",
  REJECTED: "RED",
  ERROR: "RED",
};

const KBLI_REASON_TEXT: Record<string, string> = {
  STANDARD_COMPLIANCE:
    "No foreign-ownership restriction found for this activity.",
  PMA_NOT_VERIFIED:
    "This code's PMA cap is a declared data gap, not a confirmed approval — verify with Bali Zero before relying on it.",
  PERPRES_10_2021_RESERVATION:
    "Reserved for Koperasi/UMKM (Perpres 49/2021) — a PT PMA cannot legally hold this code.",
  PERPRES_10_2021_FOREIGN_CAP:
    "Foreign ownership is capped below 100% for this activity, not closed outright.",
  BALI_GOV_LETTER_9_CODES:
    "Named in the Bali governor's 28 Jan 2026 letter as used by PMAs to obtain stay permits without real activity.",
  BALI_INGUB_6_2025_MORATORIUM:
    "Under the Bali modern-chain-retail moratorium (INGUB 6/2025).",
};

function StatePill({ label }: { label: string }) {
  const s = STATE_STYLE[label.toUpperCase()] ?? {
    color: "var(--text-primary)",
    bg: "var(--r19-wash, var(--surface-base))",
    border: "var(--border-subtle)",
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
        }}
      />
      {label.toUpperCase()}
    </span>
  );
}

type BuyerValue = "wni" | "wna_individual" | "wna_pma";

interface BuyerOption {
  value: BuyerValue;
  label: string;
  nationality: "WNI" | "WNA";
  isPma: boolean;
}

// Nationality is always the literal "WNI"/"WNA" string the backend fails
// closed on (never a country name) — see spec-property-check.md §3: the
// nationality fail-closed fix (#7581) may not be live everywhere yet, and
// this mapping is correct with or without it.
const BUYER_OPTIONS: BuyerOption[] = [
  {
    value: "wni",
    label: "Indonesian citizen (WNI)",
    nationality: "WNI",
    isPma: false,
  },
  {
    value: "wna_individual",
    label: "Foreign individual (WNA)",
    nationality: "WNA",
    isPma: false,
  },
  {
    value: "wna_pma",
    label: "Foreign-owned PT PMA",
    nationality: "WNA",
    isPma: true,
  },
];

type UseValue = "own_use" | "villa_rental" | "restaurant" | "retail" | "office";

interface UseOption {
  value: UseValue;
  label: string;
  kbliCode: string | null;
  kbliTitle: string | null;
}

// Curated — there is no free-text KBLI search endpoint on mouth or the prime
// router (spec-property-check.md §3). Verified against
// data/KBLI_2025_FINAL_CLEAN.json 2026-09-28: 55203 "Aktivitas Vila" is
// allocated 0% foreign (Perpres 49/2021, Koperasi/UMKM reservation) — a PT
// PMA cannot legally hold it, so it is never offered here. 68112 is the
// registration a villa-rental PMA actually uses instead — see the caveat
// rendered below, which states its own live KBLIEye status honestly.
const USE_OPTIONS: UseOption[] = [
  {
    value: "own_use",
    label: "Live-in villa (own use, no business)",
    kbliCode: null,
    kbliTitle: null,
  },
  {
    value: "villa_rental",
    label: "Short-term villa rental business",
    kbliCode: "68112",
    kbliTitle: "Aktivitas Penyewaan Bangunan dan Lahan Hunian (68112)",
  },
  {
    value: "restaurant",
    label: "Restaurant",
    kbliCode: "56101",
    kbliTitle: "Aktivitas Penyediaan Makanan di Bangunan Tetap (56101)",
  },
  {
    value: "retail",
    label: "Retail shop",
    kbliCode: "47112",
    kbliTitle: "Perdagangan Eceran, non-self-service (47112)",
  },
  {
    value: "office",
    label: "Office / commercial building",
    kbliCode: "68127",
    kbliTitle: "Pengelolaan Gedung Perkantoran (68127)",
  },
];

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

type AnalyzeKbli = {
  code?: string;
  title?: string;
  state?: "APPROVED" | "WARNING" | "REJECTED" | "ERROR" | string;
  reason?: string;
  max_foreign_ownership?: number | null;
};

type AnalyzeResponse = {
  status?: string;
  zone?: AnalyzeZone;
  verdict?: AnalyzeVerdict;
  opportunities?: AnalyzeOpportunity[];
  kbli?: AnalyzeKbli | null;
  sea_distance_m?: number;
  [key: string]: unknown;
};

const fieldStyle: CSSProperties = {
  padding: "var(--space-3) var(--space-4)",
  width: "100%",
  borderRadius: "8px",
  border: "1px solid var(--border-subtle)",
  background: "var(--surface-raised)",
  color: "var(--text-primary)",
  fontSize: "1rem",
};

export function PropertyEligibilityBody() {
  const [coord, setCoord] = useState("");
  const [buyer, setBuyer] = useState<BuyerValue | "">("");
  const [use, setUse] = useState<UseValue | "">("");
  const [priceIdr, setPriceIdr] = useState("");
  const [landSizeM2, setLandSizeM2] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const selectedUse = useMemo(
    () => USE_OPTIONS.find((o) => o.value === use),
    [use],
  );

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
    const buyerOption = BUYER_OPTIONS.find((b) => b.value === buyer);
    if (!buyerOption) {
      setError("Select who is buying before analyzing.");
      return;
    }
    const useOption = USE_OPTIONS.find((o) => o.value === use);
    if (!useOption) {
      setError("Select the intended use before analyzing.");
      return;
    }
    const { lat, lng } = parsed;
    trackPropertyAnalyzeCTA(lat, lng);
    setLoading(true);
    try {
      const res = await fetch("/api/prime/v2/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lat,
          lng,
          kbli_code: useOption.kbliCode ?? undefined,
          is_pma: buyerOption.isPma,
          land_size_m2: landSizeM2 ? Number(landSizeM2) : undefined,
          price_idr: priceIdr ? Number(priceIdr) : undefined,
          // Literal "WNI"/"WNA" only — never a country name (spec §3).
          investor_profile: { nationality: buyerOption.nationality },
        }),
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

  const kbli = result?.kbli;
  const kbliLabel = kbli?.state
    ? (KBLI_STATE_TO_LABEL[kbli.state.toUpperCase()] ?? "YELLOW")
    : null;

  return (
    <section>
      <div
        style={{
          display: "grid",
          gap: "var(--space-3)",
          marginBottom: "var(--space-4)",
        }}
      >
        <div
          style={{
            display: "grid",
            gap: "var(--space-3)",
            gridTemplateColumns: "1fr 1fr",
          }}
        >
          <label style={{ display: "grid", gap: "0.35em" }}>
            <span
              style={{ fontSize: "0.85em", color: "var(--text-secondary)" }}
            >
              Who is buying?
            </span>
            <select
              aria-label="Buyer profile"
              value={buyer}
              onChange={(e) => {
                const v = e.target.value as BuyerValue | "";
                setBuyer(v);
                if (v) trackPropertyBuyerSelected(v);
              }}
              style={fieldStyle}
            >
              <option value="" disabled>
                Select buyer profile…
              </option>
              {BUYER_OPTIONS.map((b) => (
                <option key={b.value} value={b.value}>
                  {b.label}
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: "grid", gap: "0.35em" }}>
            <span
              style={{ fontSize: "0.85em", color: "var(--text-secondary)" }}
            >
              Intended use
            </span>
            <select
              aria-label="Intended use"
              value={use}
              onChange={(e) => {
                const v = e.target.value as UseValue | "";
                setUse(v);
                if (v) trackPropertyUseSelected(v);
              }}
              style={fieldStyle}
            >
              <option value="" disabled>
                Select intended use…
              </option>
              {USE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div
          style={{
            display: "grid",
            gap: "var(--space-3)",
            gridTemplateColumns: "1fr 1fr",
          }}
        >
          <label style={{ display: "grid", gap: "0.35em" }}>
            <span
              style={{ fontSize: "0.85em", color: "var(--text-secondary)" }}
            >
              Price (IDR, optional)
            </span>
            <input
              type="number"
              min={0}
              inputMode="numeric"
              placeholder="e.g. 3000000000"
              value={priceIdr}
              onChange={(e) => setPriceIdr(e.target.value)}
              style={fieldStyle}
            />
          </label>
          <label style={{ display: "grid", gap: "0.35em" }}>
            <span
              style={{ fontSize: "0.85em", color: "var(--text-secondary)" }}
            >
              Land size (m², optional)
            </span>
            <input
              type="number"
              min={0}
              inputMode="numeric"
              placeholder="e.g. 300"
              value={landSizeM2}
              onChange={(e) => setLandSizeM2(e.target.value)}
              style={fieldStyle}
            />
          </label>
        </div>
        <div
          style={{
            display: "grid",
            gap: "var(--space-3)",
            gridTemplateColumns: "1fr auto",
          }}
        >
          <input
            placeholder={`Paste from Google Maps (e.g. 8°39'17.4"S 115°08'22.3"E) or lat, lng`}
            value={coord}
            onChange={(e) => setCoord(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void analyze();
            }}
            style={fieldStyle}
          />
          <button
            onClick={() => void analyze()}
            disabled={loading}
            style={{
              padding: "var(--space-3) var(--space-5, 1.25rem)",
              borderRadius: "8px",
              background: "var(--r19-copper, var(--accent-funnel))",
              color: "var(--r19-cta-ink, var(--text-on-accent))",
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
      </div>
      {error ? (
        <p
          style={{
            color: "var(--color-danger, #a4402f)",
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
            borderRadius: "8px",
            background: "var(--r19-surface, var(--surface-raised))",
            border: "1px solid var(--r19-line, var(--border-subtle))",
          }}
        >
          {/* Section 1 — Zone */}
          <h2
            style={{
              marginTop: 0,
              fontFamily: "var(--font-serif)",
              fontWeight: 500,
              fontSize: "1.5rem",
            }}
          >
            Zone:{" "}
            {result.zone?.code
              ? `${result.zone.code} — ${result.zone.name ?? ""}`
              : "n/a"}
            {result.zone?.desa ? ` · ${result.zone.desa}` : ""}
          </h2>
          {result.zone?.code ? (
            <p
              style={{
                color: "var(--text-secondary)",
                margin: "var(--space-2) 0",
              }}
            >
              KDB: {result.zone?.kdb ?? "—"} · KLB: {result.zone?.klb ?? "—"} ·
              TB: {result.zone?.tb ?? "—"}
            </p>
          ) : (
            <p
              style={{
                color: "var(--text-secondary)",
                margin: "var(--space-2) 0",
              }}
            >
              Not covered by BATARA/GISTARU for this point — request a manual
              check.
            </p>
          )}
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
                <StatePill label={result.verdict.label} />
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

          {/* Section 2 — What may be built here */}
          {opportunities.length ? (
            <div style={{ margin: "var(--space-5) 0" }}>
              <h3
                style={{
                  fontFamily: "var(--font-serif)",
                  fontWeight: 500,
                  fontSize: "1.05rem",
                  margin: "0 0 var(--space-2)",
                }}
              >
                What may be built here
              </h3>
              <ul
                style={{
                  margin: 0,
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
                          background: "var(--r19-wash, var(--surface-base))",
                          border:
                            "1px solid var(--r19-line, var(--border-subtle))",
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
                          background: STATE_STYLE.GREEN.bg,
                          border: `1px solid ${STATE_STYLE.GREEN.border}`,
                          color: STATE_STYLE.GREEN.color,
                          fontWeight: 600,
                          letterSpacing: "0.04em",
                        }}
                      >
                        PMA open
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* Section 3 — Allowed to this buyer / PMA-open */}
          {selectedUse ? (
            <div style={{ margin: "var(--space-5) 0" }}>
              <h3
                style={{
                  fontFamily: "var(--font-serif)",
                  fontWeight: 500,
                  fontSize: "1.05rem",
                  margin: "0 0 var(--space-2)",
                }}
              >
                Allowed to this buyer
              </h3>
              {selectedUse.kbliCode ? (
                <div style={{ display: "grid", gap: "var(--space-2)" }}>
                  <div
                    style={{
                      display: "flex",
                      flexWrap: "wrap",
                      gap: "0.6em",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ color: "var(--text-primary)" }}>
                      {kbli?.title || selectedUse.kbliTitle}
                    </span>
                    {kbliLabel ? <StatePill label={kbliLabel} /> : null}
                  </div>
                  {kbli?.reason ? (
                    <p style={{ color: "var(--text-secondary)", margin: 0 }}>
                      {KBLI_REASON_TEXT[kbli.reason] ?? kbli.reason}
                    </p>
                  ) : null}
                  {use === "villa_rental" ? (
                    <p
                      style={{
                        color: "var(--r19-copper, var(--text-primary))",
                        margin: 0,
                        fontWeight: 600,
                      }}
                    >
                      This tool never offers KBLI 55203 (&ldquo;Aktivitas
                      Vila&rdquo;) for a PT PMA: it is allocated 0% to foreign
                      ownership, reserved for Koperasi/UMKM (Perpres 49/2021).
                      68112 is the code a villa-rental PMA actually registers
                      under — but its own PMA cap is an unverified data gap, not
                      a confirmed approval, so verify it with Bali Zero before
                      relying on it.
                    </p>
                  ) : null}
                </div>
              ) : (
                <p style={{ color: "var(--text-secondary)", margin: 0 }}>
                  Own-use residential occupancy is not a KBLI business activity
                  — no business license applies.
                </p>
              )}
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
              href={buildWhatsAppLink("property")}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary"
              onClick={() => trackPropertyWACTA()}
              style={{
                padding: "var(--space-2) var(--space-4)",
                borderRadius: "8px",
                background: "var(--r19-copper, var(--accent-funnel))",
                color: "var(--r19-cta-ink, var(--text-on-accent))",
                textDecoration: "none",
                fontWeight: 600,
              }}
            >
              Talk to Bali Zero
            </a>
          </div>
        </article>
      ) : null}
    </section>
  );
}
