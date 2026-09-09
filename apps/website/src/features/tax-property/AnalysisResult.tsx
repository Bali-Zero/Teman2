import type { Fields, PropertyAnalysis } from "./property-contract";
import styles from "./tools.module.css";

const labels: Record<string, string> = {
  code: "Zone code",
  zone_code: "Zone code",
  name: "Zone name",
  zone_name: "Zone name",
  source: "Data source",
  desa: "Village",
  kecamatan: "District",
  kdb: "KDB · building coverage",
  klb: "KLB · floor-area ratio",
  kdh: "KDH · green area",
  tb: "TB · building height",
  gsb: "GSB · setback",
  confidence: "Source confidence",
  is_restricted: "Restriction reported",
  title: "Business activity",
  state: "Assessment state",
  reason: "Reason",
  oss_risk: "OSS risk",
  max_foreign_ownership: "Maximum foreign ownership",
  total_investment_idr: "Total investment · IDR",
  roi: "ROI · engine estimate",
  bey: "Break-even · engine estimate",
  annual_pbb: "Annual PBB · IDR estimate",
  pbb_rate_pct: "PBB rate · %",
  acquisition_bphtb: "Acquisition BPHTB · IDR estimate",
  npoptkp_applied: "NPOPTKP applied · IDR",
  njop_used: "NJOP basis used · IDR",
  kkop: "Airport height overlay",
  lp2b: "Protected agriculture overlay",
  tsunami: "Tsunami overlay",
  flood_risk: "Flood-risk overlay",
  temple_buffer: "Temple buffer",
  kkop_status: "Airport height status",
  lp2b_status: "Protected agriculture status",
};
const factors: Record<string, string> = {
  roi: "ROI quality",
  zone_kbli_fit: "Zone / activity fit",
  building_capacity: "Building capacity",
  break_even: "Break-even",
  risk: "Site risk",
  flood_risk: "Flood risk",
  market: "Market validation",
  regulatory: "Regulatory risk",
  amenity: "Amenity access",
};
export function EvidenceFields({ data }: { data: Fields }) {
  return (
    <dl className={styles.facts}>
      {Object.entries(data)
        .filter(([key]) => key !== "available")
        .map(([key, value]) => (
          <div key={key}>
            <dt>{labels[key] ?? key.replace(/_/g, " ")}</dt>
            <dd>
              {value === null || value === ""
                ? "Not supplied"
                : typeof value === "boolean"
                  ? value
                    ? "Yes"
                    : "No"
                  : typeof value === "number"
                    ? value.toLocaleString("en-GB", {
                        maximumFractionDigits: 4,
                      })
                    : value}
            </dd>
          </div>
        ))}
    </dl>
  );
}
export function AnalysisResult({ result }: { result: PropertyAnalysis }) {
  if (!result.zone)
    return (
      <section className={styles.empty} aria-labelledby="property-result-title">
        <p className={styles.eyebrow}>Coverage result</p>
        <h2 id="property-result-title">No supported zone returned.</h2>
        <p>
          The service could not resolve this site to a zoning record. This is
          not an eligibility decision. Check the coordinates or arrange a
          site-specific review.
        </p>
        <a className={styles.textLink} href="/zoning">
          Prepare a zoning review →
        </a>
      </section>
    );
  const verdict = result.verdict;
  return (
    <article className={styles.result} aria-labelledby="property-result-title">
      <header className={styles.resultHeader}>
        <div>
          <p className={styles.eyebrow}>Property findings / service response</p>
          <h2 id="property-result-title">
            {String(result.zone.code ?? result.zone.zone_code ?? "Zone record")}
            {result.zone.name || result.zone.zone_name
              ? ` · ${result.zone.name ?? result.zone.zone_name}`
              : ""}
          </h2>
        </div>
        {verdict && (
          <div className={styles.score}>
            <strong>
              {verdict.score ?? "—"}
              <small>/100</small>
            </strong>
            <span>
              {verdict.label || "Unclassified"} ·{" "}
              {verdict.risk_level || "Risk not supplied"}
            </span>
            <small>Engine assessment</small>
          </div>
        )}
      </header>
      <p className={styles.notice}>
        This is the connected service’s preliminary assessment. It does not
        confirm title, grant permission or replace review of the applicable
        rules and property documents.
      </p>
      {!!verdict?.hard_blocks.length && (
        <section className={styles.blockers}>
          <h3>Restrictions that need attention</h3>
          <ul>
            {verdict.hard_blocks.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ul>
        </section>
      )}
      <section className={styles.section}>
        <h3>Site & building parameters</h3>
        <EvidenceFields data={result.zone} />
        {result.sea_distance_m !== null && (
          <p>
            Distance to sea reported:{" "}
            {result.sea_distance_m.toLocaleString("en-GB")} m
          </p>
        )}
        {Object.keys(result.overlays).length > 0 && (
          <>
            <h3>Reported overlays</h3>
            <EvidenceFields data={result.overlays} />
          </>
        )}
      </section>
      {verdict && (
        <section className={styles.section}>
          <h3>What sits behind the score</h3>
          {Object.keys(verdict.breakdown).length > 0 ? (
            <dl className={styles.breakdown}>
              {Object.entries(verdict.breakdown).map(([key, factor]) => (
                <div key={key}>
                  <dt>{factors[key] ?? key}</dt>
                  <dd>
                    {factor.score === null ? (
                      "Not assessed"
                    ) : (
                      <>
                        <meter
                          min={0}
                          max={factor.max && factor.max > 0 ? factor.max : 100}
                          value={factor.score}
                          aria-label={factors[key] ?? key}
                        />
                        {factor.score} / {factor.max ?? "—"}
                      </>
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p>No factor breakdown was supplied.</p>
          )}
          {verdict.modifiers.length > 0 && (
            <ul className={styles.editorialList}>
              {verdict.modifiers.map((text, i) => (
                <li key={i}>{text}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      {result.kbli && (
        <section className={styles.section}>
          <h3>Business activity assessment</h3>
          <EvidenceFields data={result.kbli} />
        </section>
      )}
      {result.opportunities.length > 0 && (
        <section className={styles.section}>
          <h3>Activities returned for this site</h3>
          <p className={styles.small}>
            Foreign-investment status appears only when explicitly supplied by
            the service.
          </p>
          <ul className={styles.opportunities}>
            {result.opportunities.map((o, i) => (
              <li key={i}>
                <strong>{o.title_en}</strong>
                <span>{o.category_en}</span>
                <small>
                  {o.pma_open === true
                    ? "PMA open — reported"
                    : o.pma_open === false
                      ? "PMA not open — reported"
                      : "PMA status not supplied"}
                </small>
              </li>
            ))}
          </ul>
        </section>
      )}
      {result.roi && (
        <section className={styles.section}>
          <h3>Investment calculation</h3>
          {result.roi.available === false ? (
            <p>The investment calculator did not return an estimate.</p>
          ) : (
            <EvidenceFields data={result.roi} />
          )}
          <p className={styles.small}>
            Engine estimates depend on its inputs and assumptions. Review them
            before relying on an investment projection.
          </p>
        </section>
      )}
      {result.property_tax && (
        <section className={styles.section}>
          <h3>Property tax calculation</h3>
          <EvidenceFields data={result.property_tax} />
          <p className={styles.small}>
            These are engine estimates, not a tax assessment or service quote.
            The local basis, rates and allowances need verification.
          </p>
        </section>
      )}
      <div className={styles.actions}>
        <a
          className={styles.primary}
          href="/contact?topic=property&from=%2Fproperty%2Feligibility"
        >
          Discuss these findings →
        </a>
        <a className={styles.secondary} href="/zoning">
          Prepare the property documents
        </a>
      </div>
    </article>
  );
}
