"use client";
import { useMemo, useState, type CSSProperties, type ReactNode } from "react";
import {
  trackPropertyAnalyzeCTA,
  trackPropertyWACTA,
  trackPropertyBuyerSelected,
  trackPropertyUseSelected,
} from "@/lib/analytics";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { parseCoordinates } from "./parse-coordinates";

type BuyerValue = "wni" | "wna_individual" | "wna_pma";

interface BuyerOption {
  value: BuyerValue;
  label: string;
  nationality: "WNI" | "WNA";
}

// Nationality is always the literal "WNI"/"WNA" string the backend fails
// closed on (never a country name) — see spec-property-check.md §3: the
// nationality fail-closed fix (PR 7581) may not be live everywhere yet, and
// this mapping is correct with or without it. `value` (not `nationality`)
// selects the section-3 copy variant — WNA splits into individual vs. PT
// PMA even though both send nationality "WNA".
const BUYER_OPTIONS: BuyerOption[] = [
  {
    value: "wni",
    label: "Indonesian citizen (WNI)",
    nationality: "WNI",
  },
  {
    value: "wna_individual",
    label: "Foreign individual (WNA)",
    nationality: "WNA",
  },
  {
    value: "wna_pma",
    label: "Foreign-owned company (PT PMA)",
    nationality: "WNA",
  },
];

type UseValue = "own_use" | "villa_rental" | "restaurant" | "retail" | "office";

interface UseOption {
  value: UseValue;
  label: string;
}

// REWORK-DESIGN v2 (spec-property-check-v2.md, 2026-09-28): no KBLI code is
// attached to a use anymore. The v1 mapping (one KBLI code per use, KBLIEye's
// verdict shown as "Allowed to this buyer") was legally unsafe on a public
// page — villa rental has no PMA-eligible code at all (55203 is 0% foreign,
// reserved Koperasi/UMKM; 68112 is a property-leasing code, and registering
// short-term rental under it is a compliance breach — see
// research/property/2026-07-21-kbli-villa-pma-eligibility-verification.md:116-118,162-175)
// and the live KBLIEye/backend data disagree on several other codes for Bali.
// Section 3 below is static reviewed copy keyed on (buyer, use), not a live
// KBLI lookup.
const USE_OPTIONS: UseOption[] = [
  { value: "own_use", label: "Live-in villa (own use, no business)" },
  { value: "villa_rental", label: "Short-term villa rental" },
  { value: "restaurant", label: "Restaurant" },
  { value: "retail", label: "Retail shop" },
  { value: "office", label: "Office / commercial building" },
];

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

// B1 (gate-7596-report.md v2, REWORK-BUILD): no verdict field on this type —
// the report never renders a score/risk/GREEN-YELLOW-RED grade of the
// purchase. If the backend payload carries one, it is deliberately unread.
type AnalyzeResponse = {
  status?: string;
  zone?: AnalyzeZone;
  opportunities?: AnalyzeOpportunity[];
  sea_distance_m?: number;
  [key: string]: unknown;
};

/** Section 3 copy — static, reviewed, keyed on (buyer, use). No KBLI verdict,
 * no KBLIEye call, no "allowed"/GREEN pill: see the REWORK-DESIGN note above
 * USE_OPTIONS. Every legal sentence here is verbatim from
 * spec-property-check-v2.md (grammar-only fixes allowed) — do not add a new
 * legal claim, KBLI code or regulation here without updating that spec. */
function renderSection3(
  buyerOption: BuyerOption,
  useOption: UseOption,
): ReactNode | null {
  if (useOption.value === "own_use") return null;

  if (buyerOption.value === "wni") {
    return (
      <p style={{ color: "var(--text-secondary)", margin: 0 }}>
        As an Indonesian individual or a local company (PT PMDN) you can
        register this activity, subject to the zoning in section 1 and the local
        permits.
      </p>
    );
  }

  const pmaCopy =
    useOption.value === "villa_rental" ? (
      <p
        style={{
          color: "var(--r19-copper, var(--text-primary))",
          margin: 0,
          fontWeight: 600,
        }}
      >
        Villa rental (KBLI 55203) is reserved for Indonesian small businesses
        and is not open to a PT PMA (Perpres 10/2021 jo. 49/2021). There is
        currently no business code that lets a PT PMA operate a villa directly,
        and registering short-term rental under a property-leasing code is a
        compliance breach. There are compliant routes for foreign investors:
        we&rsquo;ll walk you through them.
      </p>
    ) : (
      <p style={{ color: "var(--text-secondary)", margin: 0 }}>
        Whether this activity is open to a PT PMA here depends on the exact
        business code and the project&rsquo;s scale, and since May 2026 Bali has
        closed several codes to new PMA registrations. We check it for your
        project before you commit.
      </p>
    );

  if (buyerOption.value === "wna_individual") {
    return (
      <div style={{ display: "grid", gap: "var(--space-3)" }}>
        <p style={{ color: "var(--text-secondary)", margin: 0 }}>
          A foreign individual can&rsquo;t run a business in Indonesia in their
          own name: foreign investment has to go through a foreign-owned company
          (PT PMA), with an investment of more than Rp 10 billion per business
          activity per location, excluding land and buildings (UU 25/2007, Art.
          5(2); BKPM Reg. 5/2025).
        </p>
        {pmaCopy}
      </div>
    );
  }

  // wna_pma
  return pmaCopy;
}

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
  // The (buyer, use) SNAPSHOT that produced `result` — section 3 reads this,
  // never the live selects, so changing a select after analyzing does not
  // change the printed copy until the next analyze (F8, gate-7596-report.md).
  const [snapshot, setSnapshot] = useState<{
    buyerOption: BuyerOption;
    useOption: UseOption;
  } | null>(null);
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
          land_size_m2: landSizeM2 ? Number(landSizeM2) : undefined,
          price_idr: priceIdr ? Number(priceIdr) : undefined,
          // Literal "WNI"/"WNA" only — never a country name (spec §3). No
          // kbli_code / is_pma: section 3 is static copy, not a KBLIEye call
          // (REWORK-DESIGN v2, spec-property-check-v2.md).
          investor_profile: { nationality: buyerOption.nationality },
        }),
      });
      if (!res.ok) {
        setError(`Error ${res.status}: zone not analyzable.`);
        return;
      }
      const data = (await res.json()) as AnalyzeResponse;
      // The proxy (api/prime/v2/analyze/route.ts) answers HTTP 200 with
      // {status:"error"} on an upstream failure — `res.ok` alone misses it
      // (F4, gate-7596-report.md). A response with no zone payload is
      // equally unusable.
      if (data.status === "error" || !data.zone) {
        setError("Error: zone not analyzable.");
        return;
      }
      setResult(data);
      setSnapshot({ buyerOption, useOption });
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
          marginBottom: "var(--space-4)",
        }}
      >
        <div
          style={{
            display: "grid",
            gap: "var(--space-3)",
            // Minor (gate-7596-report.md v2): auto-fit/minmax stacks these
            // to one column once the row is too narrow for both at a
            // readable width, instead of squeezing a long option label
            // ("Foreign-owned company (PT PMA)") into an unreadable sliver
            // at 390 — no media query needed.
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
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
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
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
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* Section 3 — What you can do with it. Static reviewed copy keyed
              on the ANALYSED (buyer, use) snapshot — never the live selects
              (F8). No KBLI verdict, no "allowed"/GREEN pill: see
              renderSection3 above USE_OPTIONS. */}
          {snapshot
            ? (() => {
                const body = renderSection3(
                  snapshot.buyerOption,
                  snapshot.useOption,
                );
                if (!body) return null;
                return (
                  <div style={{ margin: "var(--space-5) 0" }}>
                    <h3
                      style={{
                        fontFamily: "var(--font-serif)",
                        fontWeight: 500,
                        fontSize: "1.05rem",
                        margin: "0 0 var(--space-2)",
                      }}
                    >
                      What you can do with it
                    </h3>
                    {body}
                  </div>
                );
              })()
            : null}

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
