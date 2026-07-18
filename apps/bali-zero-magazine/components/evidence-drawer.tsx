import type { ClaimView } from "@/lib/server/magazine-read-model";

type EvidenceDrawerProps = Readonly<{
  claims: readonly ClaimView[];
}>;

export function EvidenceDrawer({ claims }: EvidenceDrawerProps) {
  return (
    <section className="evidence-drawer" aria-labelledby="evidence-title">
      <div className="evidence-heading">
        <p className="section-label">Ground truth</p>
        <h2 id="evidence-title">Claims and evidence</h2>
        <p>Facts and editorial analysis are labeled separately.</p>
      </div>
      {claims.length === 0 ? (
        <p className="evidence-empty">
          No publishable claim evidence is available.
        </p>
      ) : (
        <ol className="claim-list">
          {claims.map((claim, index) => (
            <li key={`${claim.kind}-${index}`}>
              <span className={`claim-kind claim-kind--${claim.kind}`}>
                {claim.kind === "analysis" ? "Analysis" : "Verified claim"}
              </span>
              <p>{claim.text}</p>
              {claim.numericValue ? (
                <p className="numeric-claim">
                  {claim.numericValue} {claim.numericUnit}
                  {claim.asOf ? ` · as of ${claim.asOf}` : ""}
                </p>
              ) : null}
              {claim.evidence.length > 0 ? (
                <ul className="evidence-list">
                  {claim.evidence.map((evidence, evidenceIndex) => (
                    <li key={`${evidence.publisher}-${evidenceIndex}`}>
                      <strong>{evidence.publisher}</strong>
                      {evidence.citation ? (
                        <span>{evidence.citation}</span>
                      ) : null}
                      {evidence.canonicalUrl ? (
                        <a href={evidence.canonicalUrl} rel="noreferrer">
                          Open source
                        </a>
                      ) : null}
                      {evidence.note ? <small>{evidence.note}</small> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <small className="evidence-missing">
                  Evidence not cleared for publication.
                </small>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
