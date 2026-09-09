import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import { SiteShell } from "../../components/SiteShell";
import { Shortlist, ShortlistButton } from "./Shortlist";
import {
  catalogSearch,
  getAllCodes,
  getSections,
  getRelatedCodes,
  publicItem,
  publicEditorial,
  buildKbliFaq,
  formatPmaOwnership,
  riskLabelEn,
  riskOptions,
  isLicensingVerificationPending,
  licensingContentInheritedFrom,
  discloseKbliBaliReason,
  type KBLICode,
  type SearchParams,
} from "./catalog.server";
import { BALI_STATUS_CONFIG } from "../../../../mouth/src/lib/kbli-status-labels";
import {
  describeObligation,
  TRUNCATION_NOTE,
  TRUNCATION_HINT,
} from "../../../../mouth/src/lib/kbli-obligation-truncation";
import { formatTimeframe } from "../../../../mouth/src/lib/kbli-derive";
import type { CatalogItem } from "./types";
import styles from "./kbli.module.css";

export function KbliShell({
  children,
  active = "catalog",
}: {
  children: ReactNode;
  active?: string;
}) {
  return (
    <SiteShell context={{ label: "KBLI Navigator", href: "/kbli" }}>
      <main id="main-content" className={styles.root}>
        <nav className={styles.navigation} aria-label="KBLI tools">
          {[
            ["catalog", "/kbli", "Find an activity"],
            ["sectors", "/kbli/sectors", "Browse sectors"],
            ["builder", "/kbli/builder", "Build a shortlist"],
            ["decoder", "/kbli/decoder", "Decode a code"],
            ["explorer", "/kbli-explorer", "Ask the Explorer"],
          ].map(([id, href, text]) => (
            <a
              key={id}
              href={href}
              aria-current={active === id ? "page" : undefined}
            >
              {text}
            </a>
          ))}
        </nav>
        {children}
      </main>
    </SiteShell>
  );
}

export function CodeCard({ item }: { item: CatalogItem }) {
  return (
    <article className={styles.codeCard}>
      <div className={styles.cardTop}>
        <span className={styles.code}>{item.code}</span>
        <ShortlistButton code={item.code} />
      </div>
      <h3>
        <a href={`/kbli/${item.code}`}>{item.title}</a>
      </h3>
      <p lang="id" className={styles.indonesian}>
        {item.titleId}
      </p>
      <dl className={styles.cardFacts}>
        <div>
          <dt>Foreign ownership</dt>
          <dd>{item.ownership}</dd>
        </div>
        <div>
          <dt>Bali</dt>
          <dd>{item.bali}</dd>
        </div>
        <div>
          <dt>Recorded risk</dt>
          <dd>
            {item.risks.join(" / ") || "No standard risk rows"}
            {item.licensingPending && <small>Verification pending</small>}
          </dd>
        </div>
      </dl>
      <a className={styles.textLink} href={`/kbli/${item.code}`}>
        Read activity & requirements <span aria-hidden="true">↗</span>
      </a>
    </article>
  );
}

function pageHref(base: string, params: SearchParams, page: number): string {
  const search = new URLSearchParams();
  for (const key of ["q", "section", "pma", "risk"]) {
    const value = params[key];
    if (typeof value === "string" && value) search.set(key, value);
  }
  search.set("page", String(page));
  return `${base}?${search}`;
}

export function CatalogPage({
  params,
  mode = "catalog",
  fixedSection,
}: {
  params: SearchParams;
  mode?: "catalog" | "builder" | "decoder";
  fixedSection?: string;
}) {
  const result = catalogSearch(params, fixedSection);
  const sections = getSections();
  const sector = sections.find((section) => section.id === fixedSection);
  const base = fixedSection
    ? `/kbli/sectors/${fixedSection}`
    : mode === "catalog"
      ? "/kbli"
      : `/kbli/${mode}`;
  const titles = {
    catalog: "Your business idea.\nIts Indonesian code.",
    builder: "One business.\nEvery activity considered.",
    decoder: "Five digits.\nA clearer picture.",
  };
  const descriptions = {
    catalog:
      "Find the activity that matches what you will actually do. Explore foreign ownership, licensing by scale, Bali conditions and the evidence behind each record.",
    builder:
      "A business can involve several distinct activities. Search, shortlist and compare them together before reviewing your proposed company structure with our team.",
    decoder:
      "Enter a five-digit code to read its activity definition, recorded licensing requirements and source history. Compare the description with the work your business performs.",
  };
  return (
    <KbliShell active={fixedSection ? "sectors" : mode}>
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>
            {sector
              ? `Sector ${sector.id} · KBLI 2025`
              : "The Bali Zero business classification guide"}
          </span>
          <h1>{sector?.nameEn ?? titles[mode]}</h1>
          <p className={styles.intro}>
            {sector?.description ?? descriptions[mode]}
          </p>
        </div>
        <aside className={styles.heroNote}>
          <span className={styles.largeNumber}>
            {sector
              ? String(sector.codeCount)
              : getAllCodes().length.toLocaleString("en-US")}
          </span>
          <p>
            {sector ? "activities in this sector" : "activity codes to explore"}
          </p>
          <div className={styles.hairline} />
          <p>
            Start with your activity.
            <br />
            Then check the ownership, scale and location together.
          </p>
        </aside>
      </header>
      {mode === "builder" && <Shortlist expanded />}
      {mode === "decoder" && (
        <section className={styles.note}>
          <h2>Reading an older code?</h2>
          <p>
            Search the number first. A 2025 record can show predecessor codes
            and inherited licensing rows separately. Matching digits alone do
            not establish that the activity or its permissions stayed the same.
          </p>
          <a className={styles.textLink} href="/contact?topic=company">
            Review an older business registration →
          </a>
        </section>
      )}
      <section
        className={styles.searchSection}
        aria-label="Search KBLI activities"
      >
        <form action={base} className={styles.searchForm}>
          <div className={styles.searchLine}>
            <label htmlFor="kbli-query">
              {mode === "decoder"
                ? "Enter your KBLI code or activity"
                : "What will your business do?"}
              <input
                id="kbli-query"
                name="q"
                type="search"
                maxLength={200}
                defaultValue={result.q}
                placeholder="Try a business activity or a five-digit code"
              />
            </label>
            <button className={styles.primary} type="submit">
              Find activities <span aria-hidden="true">→</span>
            </button>
          </div>
          <div className={styles.filters}>
            {!fixedSection && (
              <label>
                Sector
                <select name="section" defaultValue={result.section}>
                  <option value="">All sectors</option>
                  {sections.map((section) => (
                    <option key={section.id} value={section.id}>
                      {section.id} — {section.nameEn}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              Foreign ownership
              <select name="pma" defaultValue={result.pma ?? ""}>
                <option value="">All ownership statuses</option>
                <option value="open">Verified open status</option>
                <option value="restricted">Verified restricted status</option>
                <option value="closed">Verified closed status</option>
                <option value="unknown">Not verified</option>
              </select>
            </label>
            <label>
              Recorded risk
              <select name="risk" defaultValue={result.risk ?? ""}>
                <option value="">All recorded risk levels</option>
                {riskOptions.map((risk) => (
                  <option key={risk} value={risk}>
                    {riskLabelEn(risk)}
                  </option>
                ))}
              </select>
            </label>
            <a href={base} className={styles.reset}>
              Reset filters
            </a>
          </div>
        </form>
        <p className={styles.caption}>
          Risk can differ by scope and business scale. A matching search result
          is a starting point for review.
        </p>
      </section>
      <section className={styles.results} aria-label="Activity results">
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.eyebrow}>
              {result.q ? "Your search" : "The activity directory"}
            </span>
            <h2>
              {result.count.toLocaleString("en-US")}{" "}
              {result.count === 1 ? "activity" : "activities"}
              {result.q ? ` for “${result.q}”` : " to explore"}
            </h2>
          </div>
          <span className={styles.caption}>
            Page {result.page} of {result.pages}
          </span>
        </div>
        {result.items.length ? (
          <div className={styles.codeGrid}>
            {result.items.map((item) => (
              <CodeCard key={item.code} item={item} />
            ))}
          </div>
        ) : (
          <div className={styles.empty}>
            <h3>No matching activities.</h3>
            <p>
              Try a broader activity description, an Indonesian term, or remove
              one of the filters.
            </p>
            <a className={styles.textLink} href="/kbli/sectors">
              Browse the sectors →
            </a>
          </div>
        )}
        <nav className={styles.pagination} aria-label="Results pagination">
          {result.page > 1 && (
            <a
              className={styles.secondary}
              href={pageHref(base, params, result.page - 1)}
            >
              ← Previous
            </a>
          )}
          {result.page < result.pages && (
            <a
              className={styles.secondary}
              href={pageHref(base, params, result.page + 1)}
            >
              Next activities →
            </a>
          )}
        </nav>
      </section>
      {mode !== "builder" && <Shortlist />}
      <section className={styles.closing}>
        <span className={styles.eyebrow}>From a code to a workable plan</span>
        <h2>Tell us how your business will operate.</h2>
        <p>
          Bring the activities you shortlisted. Our team can review the scope,
          ownership, location and company setup together.
        </p>
        <a href="/contact?topic=company" className={styles.primary}>
          Talk through my business →
        </a>
      </section>
    </KbliShell>
  );
}

export function SectorsPage() {
  const sections = getSections();
  return (
    <KbliShell active="sectors">
      <header className={styles.hero}>
        <div>
          <span className={styles.eyebrow}>KBLI 2025 · The sectors</span>
          <h1>
            A wider view of
            <br />
            your business.
          </h1>
          <p className={styles.intro}>
            Explore the classification by sector. Each chapter leads to the
            activities, ownership disclosures and licensing records within it.
          </p>
        </div>
        <aside className={styles.heroNote}>
          <span className={styles.largeNumber}>{sections.length}</span>
          <p>sectors in the classification</p>
          <a className={styles.textLink} href="/kbli">
            Search every activity →
          </a>
        </aside>
      </header>
      <section className={styles.sectorList} aria-label="KBLI sectors">
        {sections.map((section) => (
          <a
            key={section.id}
            href={`/kbli/sectors/${section.id}`}
            className={styles.sector}
          >
            <span className={styles.sectorLetter}>{section.id}</span>
            <div>
              <h2>{section.nameEn}</h2>
              <p>{section.description}</p>
              <span lang="id" className={styles.caption}>
                {section.nameId}
              </span>
            </div>
            <span className={styles.sectorCount}>
              {section.codeCount} activities <span aria-hidden="true">↗</span>
            </span>
          </a>
        ))}
      </section>
    </KbliShell>
  );
}

function Prose({ children }: { children?: string | null }) {
  return children ? (
    <div className={styles.prose}>
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  ) : null;
}
function SourceList({ items }: { items: string[] }) {
  return (
    <ul className={styles.requirements}>
      {items.map((item, index) => {
        const display = describeObligation(item);
        return (
          <li key={index}>
            <span lang="id">{display.text}</span>
            {display.truncated && (
              <span className={styles.incomplete} title={TRUNCATION_HINT}>
                {TRUNCATION_NOTE}
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function CodePage({ code }: { code: KBLICode }) {
  const item = publicItem(code);
  const editorial = publicEditorial(code);
  const gold = editorial.gold;
  const intel = editorial.intel;
  const pending = isLicensingVerificationPending(code);
  const inherited = licensingContentInheritedFrom(code);
  const baliReason = discloseKbliBaliReason(code);
  const faq = buildKbliFaq(code);
  const sections = [
    ["The activity, explained", gold?.whatItMeans ?? intel?.whatItMeans],
    ["What you need", gold?.whatYouNeed ?? intel?.whatYouNeed],
    ["What changed", gold?.whatChanged ?? intel?.whatChanged],
    ["In the Bali context", gold?.baliContext ?? intel?.baliContext],
    ["You may also need", gold?.youllAlsoNeed ?? intel?.youllAlsoNeed],
  ];
  return (
    <KbliShell>
      <div className={styles.breadcrumb}>
        <a href="/kbli">Activities</a>
        <span>/</span>
        {code.section && (
          <>
            <a href={`/kbli/sectors/${code.section}`}>{code.sectionName}</a>
            <span>/</span>
          </>
        )}
        <span>{code.code}</span>
      </div>
      <header className={styles.detailHero}>
        <div className={styles.sectionHeading}>
          <span className={styles.eyebrow}>
            KBLI 2025 · Activity {code.code}
          </span>
          <ShortlistButton code={code.code} />
        </div>
        <h1>{code.titleEn}</h1>
        <p className={styles.originalTitle} lang="id">
          {code.titleId}
        </p>
        <div className={styles.summaryFacts}>
          <div>
            <span>Foreign ownership</span>
            <strong>{formatPmaOwnership(code.pma)}</strong>
          </div>
          <div>
            <span>Bali</span>
            <strong>{item.bali}</strong>
          </div>
          <div>
            <span>Recorded risk</span>
            <strong>{item.risks.join(" / ") || "No standard risk rows"}</strong>
            {pending && <small>Verification pending</small>}
          </div>
        </div>
      </header>
      <div className={styles.readingLayout}>
        <aside className={styles.contents}>
          <span className={styles.eyebrow}>Inside this activity</span>
          <a href="#activity">Activity & scope</a>
          <a href="#ownership">Ownership & Bali</a>
          <a href="#licensing">Licensing by scale</a>
          <a href="#sources">Sources & transition</a>
          <a href="#questions">Questions answered</a>
          <a href="/kbli/builder">Compare my shortlist →</a>
        </aside>
        <div>
          <section id="activity" className={styles.readingSection}>
            <span className={styles.eyebrow}>01 · The activity</span>
            <h2>Understand the scope.</h2>
            {code.description ? (
              <div className={styles.definition}>
                <span className={styles.caption}>
                  Activity description · original source wording
                </span>
                <p lang="id">{code.description}</p>
              </div>
            ) : (
              <p>No activity description is available in this record.</p>
            )}
            {intel?.editorial && (
              <div className={styles.editorial}>
                <h3>{intel.editorial.headline}</h3>
                <Prose>{intel.editorial.standfirst}</Prose>
                <Prose>{intel.editorial.body}</Prose>
                {intel.editorial.pullQuote && (
                  <blockquote>{intel.editorial.pullQuote}</blockquote>
                )}
                {intel.editorial.byTheNumbers &&
                  intel.editorial.byTheNumbers.length > 0 && (
                    <dl className={styles.numbers}>
                      {intel.editorial.byTheNumbers.map((number, index) => (
                        <div key={index}>
                          <dt>{number.label}</dt>
                          <dd>{number.value}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
              </div>
            )}
            {sections.map(([title, body]) =>
              body ? (
                <div key={title} className={styles.explanation}>
                  <h3>{title}</h3>
                  <Prose>{body}</Prose>
                </div>
              ) : null,
            )}
            {editorial.withheld && (
              <p className={styles.sourceNote}>
                An editorial explanation is not available for this record. Use
                the source description and the verified disclosures below, then
                review your intended activity with our team.
              </p>
            )}
            {gold?.tkaInfo && (
              <div className={styles.explanation}>
                <h3>Foreign-worker position reference</h3>
                <p>{gold.tkaInfo.categoryName}</p>
                <Prose>{gold.tkaInfo.insight}</Prose>
                <ul>
                  {gold.tkaInfo.relevantPositions.map((position, index) => (
                    <li key={index}>
                      {position.titleEn}{" "}
                      <span lang="id">({position.titleId})</span> · ISCO{" "}
                      {position.isco}
                      {position.temporary ? " · temporary" : ""}
                    </li>
                  ))}
                </ul>
                <Prose>{gold.tkaInfo.keduaNote}</Prose>
              </div>
            )}
          </section>
          <section id="ownership" className={styles.readingSection}>
            <span className={styles.eyebrow}>02 · Ownership & location</span>
            <h2>Read the conditions together.</h2>
            <div className={styles.factPanel}>
              <h3>{formatPmaOwnership(code.pma)}</h3>
              {code.pma.condition && <Prose>{code.pma.condition}</Prose>}
              {code.pma.note && <Prose>{code.pma.note}</Prose>}
              {code.pma.officialBasis ? (
                <p className={styles.sourceNote}>
                  {code.pma.officialBasis}
                  {code.pma.sourceVintage ? ` · ${code.pma.sourceVintage}` : ""}
                </p>
              ) : (
                <p className={styles.sourceNote}>
                  The whole-code ownership verdict has no verified official
                  locator in this record.
                </p>
              )}
            </div>
            {code.perpresSlice?.map((slice, index) => (
              <div className={styles.note} key={index}>
                <h3>Activity-specific restriction</h3>
                <p lang="id">{slice.bidangUsaha}</p>
                <p>
                  Foreign ownership ceiling for this activity:{" "}
                  {slice.foreignCapPct}%.
                </p>
                <p>{slice.condition}</p>
                <p className={styles.sourceNote}>{slice.locator}</p>
              </div>
            ))}
            <div className={styles.factPanel}>
              <h3>
                {code.baliL4
                  ? (BALI_STATUS_CONFIG[code.baliL4.status]?.label ??
                    "Bali status requires review")
                  : "Bali status not available"}
              </h3>
              <Prose>{baliReason}</Prose>
              {code.baliL4?.needsReview && (
                <p>This record requires a location-specific review.</p>
              )}
              {code.baliL4?.moratorium && (
                <p className={styles.sourceNote}>
                  {code.baliL4.moratorium.rule} · Effective{" "}
                  {code.baliL4.moratorium.effective} ·{" "}
                  {code.baliL4.moratorium.source}
                </p>
              )}
            </div>
          </section>
          <section id="licensing" className={styles.readingSection}>
            <span className={styles.eyebrow}>
              03 · Licensing by business scale
            </span>
            <h2>The requirements behind the code.</h2>
            <p>
              Expand each recorded scale to read its licence, requirements and
              obligations. Source requirements remain in Indonesian so their
              wording is preserved.
            </p>
            {pending && (
              <div className={styles.note}>
                <h3>Licensing verification is pending.</h3>
                <p>
                  These rows are reference material. Confirm the current
                  activity scope and licensing requirements in OSS before acting
                  on them.
                </p>
              </div>
            )}
            {inherited && (
              <p className={styles.sourceNote}>
                The licensing text is inherited from source{" "}
                {inherited.length === 1 ? "code" : "codes"}{" "}
                {inherited.join(", ")}. This is distinct from verification of
                the risk classification.
              </p>
            )}
            {code.riskDispute && (
              <p className={styles.sourceNote}>
                The stored risk data has a recorded source conflict. The
                affected tiers are{" "}
                {code.riskDispute.recordTiers.map(riskLabelEn).join(", ")}.
                Review the declared scope before relying on a single risk label.
              </p>
            )}
            {code.licensing.length ? (
              code.licensing.map((row, index) => (
                <details
                  key={index}
                  className={styles.licence}
                  open={index === 0}
                >
                  <summary>
                    <span>
                      {row.scales.join(" / ") || "Scale not recorded"}
                      <small>{riskLabelEn(row.riskCategory)}</small>
                    </span>
                    <strong>
                      {row.licenseType || "Licence type not recorded"}
                    </strong>
                  </summary>
                  <div className={styles.licenceBody}>
                    <dl className={styles.licenceFacts}>
                      <div>
                        <dt>Recorded timeframe</dt>
                        <dd>
                          {formatTimeframe(row.timeframe) || "Not recorded"}
                        </dd>
                      </div>
                      <div>
                        <dt>Responsible authority</dt>
                        <dd>{row.authority || "Not recorded"}</dd>
                      </div>
                    </dl>
                    <h4>Requirements</h4>
                    {row.requirements.length ? (
                      <SourceList items={row.requirements} />
                    ) : (
                      <p>
                        No requirement text is recorded; this does not establish
                        that no requirements apply.
                      </p>
                    )}
                    <h4>Ongoing obligations</h4>
                    {row.obligations.length ? (
                      <SourceList items={row.obligations} />
                    ) : (
                      <p>No obligation text is recorded.</p>
                    )}
                  </div>
                </details>
              ))
            ) : (
              <div className={styles.note}>
                <h3>No standard licensing rows are recorded.</h3>
                <p>
                  This is a data or licensing-scope gap. It does not mean the
                  activity is unregulated or that no licence is needed.
                </p>
              </div>
            )}
          </section>
          <section id="sources" className={styles.readingSection}>
            <span className={styles.eyebrow}>04 · Evidence & transition</span>
            <h2>What the record is based on.</h2>
            <dl className={styles.sources}>
              <div>
                <dt>Activity definition</dt>
                <dd>
                  {code.provenance?.definition.locator ??
                    "No official definition locator recorded"}
                </dd>
              </div>
              <div>
                <dt>Licensing source</dt>
                <dd>
                  {code.provenance?.licensing.locator ??
                    "No verified licensing locator recorded"}
                  {code.provenance?.licensing.vintage
                    ? ` · ${code.provenance.licensing.vintage}`
                    : ""}
                </dd>
              </div>
              <div>
                <dt>Ownership source</dt>
                <dd>
                  {code.provenance?.pma.locator ??
                    "Ownership source not verified"}
                </dd>
              </div>
              <div>
                <dt>KBLI 2020 predecessor mapping</dt>
                <dd>
                  {code.transition.bpsCrosswalk?.codes.length
                    ? code.transition.bpsCrosswalk.codes.join(", ")
                    : "No adjudicated predecessor mapping recorded"}
                </dd>
              </div>
              <div>
                <dt>Licensing source codes</dt>
                <dd>
                  {code.transition.pp28LicensingSourceCodes.length
                    ? code.transition.pp28LicensingSourceCodes.join(", ")
                    : "No inherited source codes recorded"}
                </dd>
              </div>
            </dl>
            {/* Internal curation logs are not public guidance. Official locators,
                predecessor/source codes and the verification limits remain above. */}
            <p className={styles.caption}>
              A predecessor mapping describes classification history; it does
              not independently verify inherited licensing or ownership
              permissions.
            </p>
            <a
              className={styles.textLink}
              href="https://oss.go.id"
              target="_blank"
              rel="noreferrer"
            >
              Open the official OSS portal ↗
            </a>
          </section>
          <section id="questions" className={styles.readingSection}>
            <span className={styles.eyebrow}>05 · Questions answered</span>
            <h2>Before you choose this activity.</h2>
            {faq.map((entry, index) => (
              <details className={styles.faq} key={index}>
                <summary>{entry.question}</summary>
                <Prose>{entry.answer}</Prose>
              </details>
            ))}
          </section>
        </div>
      </div>
      <section className={styles.results}>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.eyebrow}>Keep exploring</span>
            <h2>Related activities.</h2>
          </div>
          <a
            className={styles.textLink}
            href={code.section ? `/kbli/sectors/${code.section}` : "/kbli"}
          >
            View the sector →
          </a>
        </div>
        <div className={styles.codeGrid}>
          {getRelatedCodes(code.code, 3).map((related) => (
            <CodeCard key={related.code} item={publicItem(related)} />
          ))}
        </div>
      </section>
      <section className={styles.closing}>
        <h2>
          A code is the beginning
          <br />
          of the conversation.
        </h2>
        <p>
          Review activity {code.code} alongside your ownership, operating
          location and business scale.
        </p>
        <div className={styles.actions}>
          <a className={styles.primary} href="/contact?topic=company">
            Review my company plans →
          </a>
          <a
            className={styles.secondary}
            href={`/kbli-explorer?inspect=${code.code}`}
          >
            Ask about {code.code} →
          </a>
        </div>
      </section>
    </KbliShell>
  );
}
