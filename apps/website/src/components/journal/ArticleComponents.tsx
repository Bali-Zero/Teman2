import type { ReactNode } from "react";
import {
  type ComponentNode,
  type Data,
  dataRows,
  dataText,
  isDataRecord,
} from "./article-model";
import { safeArticleImage, safeArticleUrl } from "./article-urls";
import styles from "./ArticleReader.module.css";
import comparisonStyles from "./ArticleComparison.module.css";
import { ArticleInteraction } from "./ArticleInteraction";
import { ArticleContextHelp } from "./ArticleReaderActions";
import { checklistData, decisionData } from "./interaction-data";

export const supportedArticleComponents = new Set([
  "InfoCard",
  "Checklist",
  "CheckList",
  "ComparisonTable",
  "Calculator",
  "DecisionTree",
  "AskZantara",
  "JourneyMap",
  "LegalDecoder",
  "ConfidenceMeter",
  "GlossaryTerm",
  "AnswerBox",
  "KeyTakeaway",
  "ArticleClusterCTA",
  "HeaderWhatsAppCTA",
  "ArticleToolEmbed",
]);
// Public display fields only, including nested records. Unknown operational props
// (client IDs, endpoints, context payloads, handlers) never reach the DOM/client.
const displayFields = new Set([
  "title",
  "subtitle",
  "description",
  "text",
  "label",
  "name",
  "value",
  "values",
  "items",
  "steps",
  "sections",
  "definition",
  "term",
  "explanation",
  "original",
  "keyPoints",
  "takeaways",
  "answer",
  "question",
  "questions",
  "suggestedQuestions",
  "defaultValue",
  "suffix",
  "prefix",
  "min",
  "max",
  "options",
  "required",
  "subItems",
  "documents",
  "tips",
  "duration",
  "estimatedTotal",
  "status",
  "documentRef",
  "documentType",
  "confidence",
  "score",
  "level",
  "sources",
  "source",
  "disclaimer",
  "note",
  "benefits",
  "details",
  "result",
  "results",
  "breakdown",
  "amount",
  "total",
  "currency",
  "format",
  "href",
  "url",
  "link",
  "linkText",
  "ctaText",
  "ctaHref",
  "content",
  "heading",
  "points",
  "regulation",
  "reference",
  "lastUpdated",
  "effectiveDate",
]);
const humanLabel = (key: string): string =>
  ({
    defaultValue: "Article example",
    documentRef: "Document reference",
    subItems: "Details",
    estimatedTotal: "Estimated total",
    keyPoints: "Key points",
    ctaHref: "Next step",
    href: "Read more",
    url: "Source",
    required: "Required",
  })[key] ??
  key
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (letter) => letter.toUpperCase());
for (const field of [
  "summary",
  "publishedDate",
  "impact",
  "severity",
  "warnings",
  "recommendation",
  "recommendations",
  "nextSteps",
  "fastTrackNote",
  "indonesian",
  "relatedTerms",
  "helpText",
  "category",
  "group",
  "categories",
  "step",
])
  displayFields.add(field);
const valueText = (value: Data | undefined): string =>
  typeof value === "number"
    ? new Intl.NumberFormat("en-GB", { maximumFractionDigits: 4 }).format(value)
    : typeof value === "boolean"
      ? value
        ? "Yes"
        : "No"
      : dataText(value);

/** Select display data before rendering. Parent 'values' is a comparison map,
 * whose arbitrary labels are authored column/row names, not executable keys. */
export function publicComponentData(
  value: Data,
  comparisonValues = false,
): Data {
  if (Array.isArray(value))
    return value.map((item) => publicComponentData(item, comparisonValues));
  if (!isDataRecord(value)) return value;
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => comparisonValues || displayFields.has(key))
      .map(([key, item]) => [key, publicComponentData(item, key === "values")]),
  );
}

function meaningful(value: Data): boolean {
  return (
    value !== null &&
    (typeof value === "object"
      ? Object.values(value).some(meaningful)
      : typeof value !== "string" || value.trim().length > 0)
  );
}

/** Rebuild interaction props from validated public fields before crossing the
 * server/client boundary. No raw MDX prop record is serialized to the browser. */
function interactionProps(node: ComponentNode): Record<string, Data> | null {
  const common = {
    title: dataText(node.props.title),
    description:
      dataText(node.props.description) || dataText(node.props.subtitle),
  };
  if (node.name === "Checklist" || node.name === "CheckList") {
    const items = checklistData(node.props);
    return items
      ? {
          ...common,
          items: items.map((item) => ({
            id: item.id,
            text: item.text,
            description: item.detail,
            group: item.group,
            required: item.required,
          })),
        }
      : null;
  }
  if (node.name === "DecisionTree") {
    const data = decisionData(node.props);
    return data
      ? {
          ...common,
          startNodeId: data.start,
          nodes: data.nodes.map((item) => ({
            id: item.id,
            question: item.question,
            description: item.detail,
            options: item.options.map((option) => ({
              label: option.text,
              description: option.detail,
              next: option.next,
            })),
            ...(item.result ? { result: { ...item.result } } : {}),
          })),
        }
      : null;
  }
  return null;
}

export function ArticleData({
  value,
  label,
}: {
  value: Data | undefined;
  label?: string;
}) {
  if (value === undefined || value === null) return null;
  if (Array.isArray(value))
    return (
      <ul className={styles.dataList}>
        {value.filter(meaningful).map((item, index) => (
          <li key={index}>
            <ArticleData value={item} />
          </li>
        ))}
      </ul>
    );
  if (isDataRecord(value))
    return (
      <dl className={styles.dataFields}>
        {Object.entries(value)
          .filter(([, item]) => meaningful(item))
          .map(([key, item]) => (
            <div key={key}>
              <dt>{humanLabel(key)}</dt>
              <dd>
                <ArticleData value={item} label={key} />
              </dd>
            </div>
          ))}
      </dl>
    );
  if (
    ["href", "url", "link", "ctaHref"].includes(label ?? "") &&
    typeof value === "string"
  ) {
    const href = safeArticleUrl(value);
    return href ? <a href={href}>{href}</a> : <span>Link unavailable</span>;
  }
  return <span>{valueText(value)}</span>;
}

function Comparison({ node }: { node: ComponentNode }) {
  const items = dataRows(node.props.items);
  const features = [
    ...new Set(
      items.flatMap((item) =>
        isDataRecord(item.values) ? Object.keys(item.values) : [],
      ),
    ),
  ];
  if (
    !items.length ||
    !features.length ||
    items.some((item) => !dataText(item.name) || !isDataRecord(item.values))
  )
    return (
      <StaticData
        node={node}
        reason="The comparison is shown as published notes because its column data is incomplete."
      />
    );
  return (
    <div
      className={comparisonStyles.comparison}
      tabIndex={0}
      role="region"
      aria-label={dataText(node.props.title) || "Article comparison"}
    >
      <table role="table">
        <caption>
          {dataText(node.props.description) ||
            dataText(node.props.subtitle) ||
            "Published comparison"}
        </caption>
        <thead role="rowgroup">
          <tr role="row">
            <th scope="col" role="columnheader">
              Feature
            </th>
            {items.map((item, index) => (
              <th scope="col" role="columnheader" key={index}>
                {dataText(item.name)}
                {item.subtitle ? (
                  <small>{dataText(item.subtitle)}</small>
                ) : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody role="rowgroup">
          {features.map((feature) => (
            <tr role="row" key={feature}>
              <th scope="row" role="rowheader">
                {feature}
              </th>
              {items.map((item, index) => (
                <td role="cell" key={index}>
                  <span
                    className={comparisonStyles.mobileLabel}
                    aria-hidden="true"
                  >
                    {dataText(item.name)}
                    {item.subtitle ? (
                      <small>{dataText(item.subtitle)}</small>
                    ) : null}
                  </span>
                  <ArticleData
                    value={publicComponentData(
                      (item.values as Record<string, Data>)[feature] ??
                        "Not specified",
                    )}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StaticData({
  node,
  reason,
}: {
  node: ComponentNode;
  reason?: string;
}) {
  const data = publicComponentData(node.props) as Record<string, Data>;
  delete data.title;
  delete data.description;
  delete data.subtitle;
  const present = meaningful(data);
  return (
    <>
      {reason ? <p className={styles.presentationNote}>{reason}</p> : null}
      <ArticleData value={data} />
      {!present &&
      !node.children.length &&
      !dataText(node.props.description) ? (
        <p>
          This embedded feature contains no readable details. Use the article’s
          explanation above and bring this section to the team when discussing
          your next step.
        </p>
      ) : null}
    </>
  );
}

function InfoCardData({ node }: { node: ComponentNode }) {
  const data = publicComponentData(node.props) as Record<string, Data>;
  const items = dataRows(data.items);
  if (
    !Array.isArray(data.items) ||
    !items.length ||
    items.length !== data.items.length ||
    items.some((item) => !dataText(item.label) || item.value === undefined)
  )
    return <StaticData node={node} />;
  const rest = Object.fromEntries(
    Object.entries(data).filter(
      ([key]) => !["title", "description", "subtitle", "items"].includes(key),
    ),
  );
  return (
    <>
      <dl className={styles.summaryFacts}>
        {items.map((item, index) => {
          const details = Object.fromEntries(
            Object.entries(item).filter(
              ([key]) => !["label", "value"].includes(key),
            ),
          );
          return (
            <div key={index}>
              <dt>{dataText(item.label)}</dt>
              <dd>
                <ArticleData value={item.value} />
                {meaningful(details) ? <ArticleData value={details} /> : null}
              </dd>
            </div>
          );
        })}
      </dl>
      {meaningful(rest) ? <ArticleData value={rest} /> : null}
    </>
  );
}

function CalculatorExample({ node }: { node: ComponentNode }) {
  const fields = dataRows(node.props.fields);
  const defaults = Object.fromEntries(
    fields.map((field) => [dataText(field.id), field.defaultValue]),
  );
  // A checked, fixed worked example. Binding includes the exact source rule AND
  // all default inputs. No article formula is invoked, interpreted or compiled.
  const leaseholdExample =
    node.expressionDigests.calculateResult ===
      "055b1eb53a215ffc1784593d117e68cc1bcffb95a02427c6c66144653ed572b7" &&
    defaults.original === 5000000000 &&
    defaults.totalYears === 25 &&
    defaults.yearsRemaining === 20 &&
    fields.length === 3;
  const villaExample =
    node.expressionDigests.calculateResult ===
      "3c4dbac55e5211115333bf150928e8dd93acf3fe2482f783c0aff45c0fe51016" &&
    defaults.price === 5000000000 &&
    defaults.structure === "leasehold" &&
    fields.length === 2;
  return (
    <>
      <p className={styles.presentationNote}>
        Worked example · fixed inputs from the article
      </p>
      <dl className={styles.exampleInputs}>
        {fields.map((field, index) => (
          <div key={index}>
            <dt>
              {dataText(field.label) || "Input"}
              {field.helpText || field.description ? (
                <small>
                  {dataText(field.helpText) || dataText(field.description)}
                </small>
              ) : null}
            </dt>
            <dd>
              {field.defaultValue !== undefined
                ? valueText(field.defaultValue)
                : "Not specified"}
              {field.suffix &&
              !dataText(field.label).includes(dataText(field.suffix))
                ? ` ${dataText(field.suffix)}`
                : ""}
            </dd>
          </div>
        ))}
      </dl>
      {fields.some(
        (field) =>
          field.options || field.min !== undefined || field.max !== undefined,
      ) ? (
        <details className={styles.staticPaths}>
          <summary>Published input ranges and choices</summary>
          {fields.map((field, index) => (
            <div key={index}>
              <strong>{dataText(field.label) || "Input"}</strong>
              <ArticleData
                value={publicComponentData(
                  Object.fromEntries(
                    Object.entries(field).filter(([key]) =>
                      ["min", "max", "options", "step"].includes(key),
                    ),
                  ),
                )}
              />
            </div>
          ))}
        </details>
      ) : null}
      {leaseholdExample ? (
        <>
          <dl className={styles.exampleResult}>
            <div>
              <dt>Current estimated value</dt>
              <dd>IDR 4,000,000,000</dd>
            </div>
            <div>
              <dt>Total depreciation</dt>
              <dd>IDR 1,000,000,000</dd>
            </div>
            <div>
              <dt>Annual depreciation</dt>
              <dd>IDR 200,000,000</dd>
            </div>
          </dl>
          <p>
            The article’s linear example retains 20 of 25 years, or 80% of the
            original value; 20% has depreciated. This fixed illustration does
            not estimate market value.
          </p>
        </>
      ) : villaExample ? (
        <>
          <dl className={styles.exampleResult}>
            {[
              ["Total example budget", "IDR 5,350,000,000"],
              ["Villa price", "IDR 5,000,000,000"],
              ["Structure setup", "IDR 0"],
              ["Transfer tax (BPHTB)", "IDR 0"],
              ["Notary fees", "IDR 50,000,000"],
              ["Legal fees", "IDR 30,000,000"],
              ["Agent commission (5%)", "IDR 250,000,000"],
              ["Miscellaneous", "IDR 20,000,000"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <p>
            The published leasehold example adds IDR 350,000,000 to the villa
            price. Its original conversion is approximately USD 334,375 at IDR
            16,000 per USD. These are the article’s fixed assumptions, not a
            current quote or exchange rate.
          </p>
        </>
      ) : node.props.results || node.props.result ? (
        <ArticleData
          value={publicComponentData(node.props.results ?? node.props.result)}
        />
      ) : (
        <p className={styles.presentationNote}>
          The article supplies a calculation rule but no stored result. Its
          inputs are preserved here; a result for another scenario needs a
          reviewed calculation. Do not use an input as an estimate.
        </p>
      )}
      {node.props.disclaimer ? (
        <p className={styles.sourceNote}>{dataText(node.props.disclaimer)}</p>
      ) : null}
    </>
  );
}

function DecisionNotes({ node }: { node: ComponentNode }) {
  const nodes = dataRows(node.props.nodes);
  return (
    <>
      <p className={styles.presentationNote}>
        Decision guide · all published paths
      </p>
      <ol className={styles.journey}>
        {nodes.map((item, index) => (
          <li key={index}>
            <strong>
              {dataText(item.question) ||
                (isDataRecord(item.result)
                  ? dataText(item.result.title)
                  : dataText(item.title) || "Outcome")}
            </strong>
            <ArticleData
              value={publicComponentData(
                Object.fromEntries(
                  Object.entries(item).filter(([key]) =>
                    [
                      "description",
                      "recommendation",
                      "recommendations",
                      "nextSteps",
                      "warnings",
                      "helpText",
                    ].includes(key),
                  ),
                ),
              )}
            />
            {isDataRecord(item.result) ? (
              <ArticleData value={publicComponentData(item.result)} />
            ) : (
              <ul>
                {dataRows(item.options).map((option, optionIndex) => {
                  const target = nodes.find(
                    (candidate) =>
                      candidate.id ===
                      (option.nextNodeId ?? option.nextId ?? option.next),
                  );
                  return (
                    <li key={optionIndex}>
                      {dataText(option.label)}
                      {option.description
                        ? ` — ${dataText(option.description)}`
                        : ""}
                      {target ? (
                        <>
                          {" "}
                          →{" "}
                          {dataText(target.question) ||
                            (isDataRecord(target.result)
                              ? dataText(target.result.title)
                              : dataText(target.title) || "Outcome")}
                        </>
                      ) : (
                        " — next step not specified"
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        ))}
      </ol>
      {!nodes.length ? (
        <StaticData
          node={node}
          reason="The decision paths are incomplete; readable notes are retained below."
        />
      ) : null}
    </>
  );
}

export function SafeArticleComponent({
  node,
  children,
  articleUrl,
  articleTitle,
}: {
  node: ComponentNode;
  children: ReactNode;
  articleUrl: string;
  articleTitle: string;
}) {
  const { name, props } = node;
  if (["script", "style", "object", "embed", "input", "source"].includes(name))
    return (
      <span className={styles.presentationNote}>
        Embedded executable content excluded.
      </span>
    );
  // Explicit harmless HTML subset; never spread author attributes.
  if (name === "br") return <br />;
  if (name === "hr") return <hr />;
  if (["strong", "b"].includes(name)) return <strong>{children}</strong>;
  if (["em", "i"].includes(name)) return <em>{children}</em>;
  if (name === "a") {
    const href = safeArticleUrl(dataText(props.href));
    return href ? <a href={href}>{children}</a> : <span>{children}</span>;
  }
  if (name === "img") {
    const src = safeArticleImage(dataText(props.src));
    return src ? (
      <figure>
        <img src={src} alt={dataText(props.alt)} loading="lazy" />
        {props.caption ? (
          <figcaption>{dataText(props.caption)}</figcaption>
        ) : null}
      </figure>
    ) : (
      <p className={styles.mediaNote}>
        Image: {dataText(props.alt) || "No description supplied"}. Media
        unavailable.
      </p>
    );
  }
  if (["div", "span", "p", "section", "figure", "figcaption"].includes(name))
    return <div>{children}</div>;
  if (name === "GlossaryTerm")
    return (
      <div className={styles.glossary}>
        <dfn>{dataText(props.term)}</dfn>
        {props.definition ? ` — ${dataText(props.definition)}` : null}
        <ArticleData
          value={publicComponentData({
            indonesian: props.indonesian ?? null,
            relatedTerms: props.relatedTerms ?? null,
          })}
        />
        {children}
      </div>
    );
  const interactive = interactionProps(node);
  if (interactive)
    return (
      <div data-source-component={name} data-source-offset={node.offset}>
        <ArticleInteraction
          name={name === "CheckList" ? "Checklist" : name}
          props={interactive}
          articleTitle={articleTitle}
          articleUrl={articleUrl}
        />
        {name === "DecisionTree" ? (
          <details className={styles.staticPaths}>
            <summary>Read all published paths</summary>
            <DecisionNotes node={node} />
          </details>
        ) : null}
        {children}
      </div>
    );
  if (name === "AskZantara" || name === "HeaderWhatsAppCTA")
    return (
      <div data-source-component={name} data-source-offset={node.offset}>
        <ArticleContextHelp
          title={articleTitle}
          url={articleUrl}
          questions={[
            ...new Set(
              [
                props.question,
                ...(Array.isArray(props.suggestedQuestions)
                  ? props.suggestedQuestions
                  : Array.isArray(props.questions)
                    ? props.questions
                    : []),
              ].filter(
                (value): value is string =>
                  typeof value === "string" && !!value.trim(),
              ),
            ),
          ]}
        />
        {children}
      </div>
    );
  if (name === "ArticleClusterCTA")
    return (
      <p className={styles.sourceNote}>
        <a
          href={`/news?q=${encodeURIComponent((dataText(props.cluster) || dataText(props.slug)).replace(/-/g, " "))}`}
        >
          Explore related reading in the Journal
        </a>
        {children}
      </p>
    );
  const title =
    dataText(props.title) ||
    ({
      InfoCard: "Article note",
      Checklist: "Checklist",
      CheckList: "Checklist",
      AskZantara: dataText(props.question) || "Questions to discuss",
      JourneyMap: "Step by step",
      LegalDecoder: "Source and explanation",
      ConfidenceMeter: "Published confidence notes",
      KeyTakeaway: "Key takeaway",
      AnswerBox: "Answer",
      ArticleClusterCTA: "Continue reading",
      HeaderWhatsAppCTA: "Discuss this topic",
      ArticleToolEmbed: "Article tool",
    }[name] ??
      "Additional article information");
  const variant =
    name === "InfoCard" ? dataText(props.variant) || dataText(props.type) : "";
  const tone = ["warning", "important", "danger"].includes(variant)
    ? "warning"
    : variant === "tip" || variant === "success"
      ? "advice"
      : "note";
  const label =
    tone === "warning"
      ? "Warning"
      : tone === "advice"
        ? "Practical advice"
        : name === "LegalDecoder"
          ? "Source note"
          : "";
  return (
    <section
      className={`${styles.component} ${name === "InfoCard" || name === "LegalDecoder" ? styles[tone] : ""}`}
      data-source-component={name}
      data-source-offset={node.offset}
    >
      {label ? <p className={styles.noteLabel}>{label}</p> : null}
      <p className={styles.componentTitle}>{title}</p>
      {name !== "ComparisonTable" && (props.description || props.subtitle) ? (
        <p>{dataText(props.description) || dataText(props.subtitle)}</p>
      ) : null}
      {name === "ComparisonTable" ? (
        <Comparison node={node} />
      ) : name === "InfoCard" ? (
        <InfoCardData node={node} />
      ) : name === "Calculator" ? (
        <CalculatorExample node={node} />
      ) : name === "DecisionTree" ? (
        <DecisionNotes node={node} />
      ) : (
        <StaticData
          node={node}
          reason={
            !supportedArticleComponents.has(name)
              ? "This feature is presented as readable article notes. Any additional interaction is not available in this edition."
              : undefined
          }
        />
      )}
      {children}
      {node.issues.some(
        (issue) => !issue.startsWith("Non-literal calculate"),
      ) ? (
        <p className={styles.presentationNote}>
          Some embedded settings could not be read safely. Available notes and
          the surrounding text are preserved.
        </p>
      ) : null}
    </section>
  );
}
