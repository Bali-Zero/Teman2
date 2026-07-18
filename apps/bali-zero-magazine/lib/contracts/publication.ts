export type ClaimKind = "fact" | "numeric" | "analysis";
export type BreakingGate =
  | "official-primary"
  | "two-independent-root-sources"
  | null;

export type ClaimV1 = Readonly<{
  claim_id: string;
  claim_kind: ClaimKind;
  normalized_text: string;
  numeric_value: string | null;
  numeric_unit: string | null;
  as_of: string | null;
  evidence_ids: readonly string[];
  breaking_gate: BreakingGate;
}>;

export type EvidenceRefV1 = Readonly<{
  evidence_id: string;
  root_source_id: string;
  canonical_url: string | null;
  publisher: string;
  document_citation: string | null;
  published_at: string | null;
  retrieved_at: string;
  source_type: "official" | "journalism" | "research" | "dataset";
  primary_document_status: "verified" | "not-primary" | "unresolved";
  root_resolution_status: "resolved" | "ambiguous" | "unresolved";
  independence_verdict: "independent" | "dependent" | "ambiguous";
  evidence_note: string | null;
  upstream_root_source_ids: readonly string[];
  syndication_group_fingerprint: string;
  independence_ruleset_version: string;
  independence_reason: string;
  counts_toward_breaking: boolean;
}>;

export type ScoreComponentsV1 = Readonly<{
  editorial: number;
  impact: number;
  freshness: number;
  evidence: number;
  diversity: number;
}>;

export type StoryVersionV1 = Readonly<{
  story_id: string;
  version: number;
  expected_current_version: number;
  slug: string;
  language: string;
  domain:
    | "immigration"
    | "company"
    | "tax"
    | "property"
    | "compliance"
    | "general";
  severity: "low" | "medium" | "high" | "critical";
  lifecycle_state: "developing" | "verified" | "amended" | "superseded";
  first_seen_at: string;
  updated_at: string;
  title: string;
  deck: string;
  summary: string;
  why_it_matters: string;
  curiosity_text: string | null;
  score_components: ScoreComponentsV1;
  claims: readonly ClaimV1[];
  evidence_refs: readonly EvidenceRefV1[];
  contributing_system_ids: readonly string[];
  coverage_state: "full" | "partial";
  confidence: "low" | "medium" | "high";
  asset_digests: readonly string[];
  adapter_version: string;
  ruleset_version: string;
}>;

export type StoryPacketV1 = Readonly<{
  schema_version: "story.v1";
  packet_id: string;
  publication_target: "breaking";
  expected_breaking_revision: number;
  publication_state: "building";
  verified_at: string;
  story: StoryVersionV1;
}>;

export type EditionPlacementV1 = Readonly<{
  story_id: string;
  version: number;
  section:
    | "immigration"
    | "company"
    | "tax"
    | "property"
    | "compliance"
    | "general";
  order: number;
}>;

export type EditionPacketV1 = Readonly<{
  schema_version: "edition.v1";
  packet_id: string;
  editor_version: string;
  ruleset_version: string;
  edition_date: string;
  edition_revision: number;
  expected_current_revision: number;
  expected_breaking_revision: number;
  edition_kind: "standard" | "quiet";
  publication_state: "building";
  coverage_state: "complete" | "partial";
  readiness_cutoff: string;
  verified_at: string;
  collector_run_ids: readonly string[];
  stories: readonly StoryVersionV1[];
  placements: readonly EditionPlacementV1[];
  breaking_story_ids: readonly string[];
  referenced_claim_ids: readonly string[];
  referenced_evidence_ids: readonly string[];
  asset_digests: readonly string[];
  coverage_gaps: readonly string[];
  reader_notices: readonly string[];
}>;

type JsonRecord = Record<string, unknown>;

const STORY_KEYS = [
  "story_id",
  "version",
  "expected_current_version",
  "slug",
  "language",
  "domain",
  "severity",
  "lifecycle_state",
  "first_seen_at",
  "updated_at",
  "title",
  "deck",
  "summary",
  "why_it_matters",
  "curiosity_text",
  "score_components",
  "claims",
  "evidence_refs",
  "contributing_system_ids",
  "coverage_state",
  "confidence",
  "asset_digests",
  "adapter_version",
  "ruleset_version",
] as const;

export function requireClosedRecord(
  value: unknown,
  path: string,
  allowedKeys: readonly string[],
): JsonRecord {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError(`${path} must be an object`);
  }
  const record = value as JsonRecord;
  const allowed = new Set(allowedKeys);
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) throw new TypeError(`${path}: unknown field ${key}`);
  }
  for (const key of allowedKeys) {
    if (!Object.hasOwn(record, key))
      throw new TypeError(`${path}: missing field ${key}`);
  }
  return record;
}

export function requireString(value: unknown, path: string): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.trim() !== value
  ) {
    throw new TypeError(`${path} must be a non-empty trimmed string`);
  }
  return value;
}

function requireNullableString(value: unknown, path: string): string | null {
  if (value === null) return null;
  return requireString(value, path);
}

export function requireInteger(
  value: unknown,
  path: string,
  minimum = 0,
): number {
  if (!Number.isSafeInteger(value) || (value as number) < minimum) {
    throw new TypeError(`${path} must be a safe integer >= ${minimum}`);
  }
  return value as number;
}

function requireNumber(value: unknown, path: string): number {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < 0 ||
    value > 1
  ) {
    throw new TypeError(`${path} must be a finite number between 0 and 1`);
  }
  return value;
}

export function requireEnum<const T extends readonly string[]>(
  value: unknown,
  path: string,
  allowed: T,
): T[number] {
  if (typeof value !== "string" || !allowed.includes(value)) {
    throw new TypeError(`${path} must be one of ${allowed.join(", ")}`);
  }
  return value as T[number];
}

export function requireTimestamp(value: unknown, path: string): string {
  const timestamp = requireString(value, path);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(timestamp)) {
    throw new TypeError(`${path} must be a UTC RFC 3339 timestamp`);
  }
  if (!Number.isFinite(Date.parse(timestamp))) {
    throw new TypeError(`${path} must be a valid timestamp`);
  }
  return timestamp;
}

export function requireSha256(value: unknown, path: string): string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) {
    throw new TypeError(`${path} must be a lowercase SHA-256 digest`);
  }
  return value;
}

export function requireStringArray(value: unknown, path: string): string[] {
  if (!Array.isArray(value)) throw new TypeError(`${path} must be an array`);
  const result = value.map((item, index) =>
    requireString(item, `${path}[${index}]`),
  );
  if (new Set(result).size !== result.length)
    throw new TypeError(`${path} contains duplicates`);
  return result;
}

function parseClaim(value: unknown, path: string): ClaimV1 {
  const raw = requireClosedRecord(value, path, [
    "claim_id",
    "claim_kind",
    "normalized_text",
    "numeric_value",
    "numeric_unit",
    "as_of",
    "evidence_ids",
    "breaking_gate",
  ]);
  const claimKind = requireEnum(raw.claim_kind, `${path}.claim_kind`, [
    "fact",
    "numeric",
    "analysis",
  ] as const);
  const numericValue = requireNullableString(
    raw.numeric_value,
    `${path}.numeric_value`,
  );
  const numericUnit = requireNullableString(
    raw.numeric_unit,
    `${path}.numeric_unit`,
  );
  if (claimKind === "numeric") {
    if (
      numericValue === null ||
      !/^-?(?:0|[1-9]\d*)(?:\.\d+)?$/.test(numericValue)
    ) {
      throw new TypeError(
        `${path}.numeric_value must be a normalized decimal string`,
      );
    }
  } else if (numericValue !== null || numericUnit !== null) {
    throw new TypeError(
      `${path} non-numeric claim cannot contain numeric fields`,
    );
  }
  const breakingGate =
    raw.breaking_gate === null
      ? null
      : requireEnum(raw.breaking_gate, `${path}.breaking_gate`, [
          "official-primary",
          "two-independent-root-sources",
        ] as const);
  const evidenceIds = requireStringArray(
    raw.evidence_ids,
    `${path}.evidence_ids`,
  );
  if (
    (claimKind === "fact" || claimKind === "numeric") &&
    evidenceIds.length === 0
  ) {
    throw new TypeError(`${path} factual or numeric claim requires evidence`);
  }
  const asOf = requireNullableString(raw.as_of, `${path}.as_of`);
  if (asOf !== null && !/^\d{4}-\d{2}-\d{2}$/.test(asOf)) {
    throw new TypeError(`${path}.as_of must be an ISO date`);
  }
  return {
    claim_id: requireString(raw.claim_id, `${path}.claim_id`),
    claim_kind: claimKind,
    normalized_text: requireString(
      raw.normalized_text,
      `${path}.normalized_text`,
    ),
    numeric_value: numericValue,
    numeric_unit: numericUnit,
    as_of: asOf,
    evidence_ids: evidenceIds,
    breaking_gate: breakingGate,
  };
}

function parseEvidence(value: unknown, path: string): EvidenceRefV1 {
  const raw = requireClosedRecord(value, path, [
    "evidence_id",
    "root_source_id",
    "canonical_url",
    "publisher",
    "document_citation",
    "published_at",
    "retrieved_at",
    "source_type",
    "primary_document_status",
    "root_resolution_status",
    "independence_verdict",
    "evidence_note",
    "upstream_root_source_ids",
    "syndication_group_fingerprint",
    "independence_ruleset_version",
    "independence_reason",
    "counts_toward_breaking",
  ]);
  const canonicalUrl = requireNullableString(
    raw.canonical_url,
    `${path}.canonical_url`,
  );
  if (canonicalUrl !== null) {
    let parsed: URL;
    try {
      parsed = new URL(canonicalUrl);
    } catch {
      throw new TypeError(`${path}.canonical_url must be a valid HTTPS URL`);
    }
    if (parsed.protocol !== "https:" || parsed.username || parsed.password) {
      throw new TypeError(`${path}.canonical_url must be a valid HTTPS URL`);
    }
  }
  const publishedAt =
    raw.published_at === null
      ? null
      : requireTimestamp(raw.published_at, `${path}.published_at`);
  if (typeof raw.counts_toward_breaking !== "boolean") {
    throw new TypeError(`${path}.counts_toward_breaking must be boolean`);
  }
  const sourceType = requireEnum(raw.source_type, `${path}.source_type`, [
    "official",
    "journalism",
    "research",
    "dataset",
  ] as const);
  const primaryDocumentStatus = requireEnum(
    raw.primary_document_status,
    `${path}.primary_document_status`,
    ["verified", "not-primary", "unresolved"] as const,
  );
  const rootResolutionStatus = requireEnum(
    raw.root_resolution_status,
    `${path}.root_resolution_status`,
    ["resolved", "ambiguous", "unresolved"] as const,
  );
  const independenceVerdict = requireEnum(
    raw.independence_verdict,
    `${path}.independence_verdict`,
    ["independent", "dependent", "ambiguous"] as const,
  );
  if (primaryDocumentStatus === "verified" && sourceType !== "official") {
    throw new TypeError(
      `${path}.primary_document_status verified requires an official source`,
    );
  }
  if (
    raw.counts_toward_breaking &&
    (rootResolutionStatus !== "resolved" ||
      independenceVerdict !== "independent")
  ) {
    throw new TypeError(
      `${path}.counts_toward_breaking contradicts lineage verdict`,
    );
  }
  return {
    evidence_id: requireString(raw.evidence_id, `${path}.evidence_id`),
    root_source_id: requireString(raw.root_source_id, `${path}.root_source_id`),
    canonical_url: canonicalUrl,
    publisher: requireString(raw.publisher, `${path}.publisher`),
    document_citation: requireNullableString(
      raw.document_citation,
      `${path}.document_citation`,
    ),
    published_at: publishedAt,
    retrieved_at: requireTimestamp(raw.retrieved_at, `${path}.retrieved_at`),
    source_type: sourceType,
    primary_document_status: primaryDocumentStatus,
    root_resolution_status: rootResolutionStatus,
    independence_verdict: independenceVerdict,
    evidence_note: requireNullableString(
      raw.evidence_note,
      `${path}.evidence_note`,
    ),
    upstream_root_source_ids: requireStringArray(
      raw.upstream_root_source_ids,
      `${path}.upstream_root_source_ids`,
    ),
    syndication_group_fingerprint: requireString(
      raw.syndication_group_fingerprint,
      `${path}.syndication_group_fingerprint`,
    ),
    independence_ruleset_version: requireString(
      raw.independence_ruleset_version,
      `${path}.independence_ruleset_version`,
    ),
    independence_reason: requireString(
      raw.independence_reason,
      `${path}.independence_reason`,
    ),
    counts_toward_breaking: raw.counts_toward_breaking,
  };
}

function independentResolvedRootCount(
  supporting: readonly EvidenceRefV1[],
): number {
  const candidates = supporting.filter(
    (item) =>
      item.counts_toward_breaking &&
      item.root_resolution_status === "resolved" &&
      item.independence_verdict === "independent",
  );
  const parent = candidates.map((_, index) => index);
  const find = (index: number): number => {
    while (parent[index] !== index) {
      parent[index] = parent[parent[index]];
      index = parent[index];
    }
    return index;
  };
  const union = (left: number, right: number): void => {
    const leftRoot = find(left);
    const rightRoot = find(right);
    if (leftRoot !== rightRoot) parent[rightRoot] = leftRoot;
  };
  const lineages = candidates.map(
    (item) => new Set([item.root_source_id, ...item.upstream_root_source_ids]),
  );
  for (let left = 0; left < candidates.length; left += 1) {
    for (let right = left + 1; right < candidates.length; right += 1) {
      const sameSyndicationGroup =
        candidates[left].syndication_group_fingerprint ===
        candidates[right].syndication_group_fingerprint;
      const sharesLineage = [...lineages[left]].some((rootId) =>
        lineages[right].has(rootId),
      );
      if (sameSyndicationGroup || sharesLineage) union(left, right);
    }
  }
  return new Set(candidates.map((_, index) => find(index))).size;
}

function validateBreakingClaims(story: StoryVersionV1): void {
  if (story.severity !== "high" && story.severity !== "critical") {
    throw new TypeError("Breaking story severity must be high or critical");
  }
  const evidenceById = new Map(
    story.evidence_refs.map((item) => [item.evidence_id, item]),
  );
  for (const claim of story.claims) {
    if (claim.claim_kind === "analysis") continue;
    if (claim.breaking_gate === null) {
      throw new TypeError(
        `claim ${claim.claim_id} requires a valid Breaking gate`,
      );
    }
    const supporting = claim.evidence_ids.map((id) => evidenceById.get(id)!);
    if (claim.breaking_gate === "official-primary") {
      if (
        !supporting.some(
          (item) =>
            item.source_type === "official" &&
            item.primary_document_status === "verified" &&
            item.root_resolution_status === "resolved" &&
            item.independence_verdict === "independent" &&
            item.counts_toward_breaking &&
            (item.canonical_url !== null || item.document_citation !== null),
        )
      ) {
        throw new TypeError(
          `claim ${claim.claim_id} lacks a resolvable official primary document`,
        );
      }
    } else {
      if (independentResolvedRootCount(supporting) < 2) {
        throw new TypeError(
          `claim ${claim.claim_id} requires two independent resolved root sources`,
        );
      }
    }
  }
}

function parseStory(
  value: unknown,
  path: string,
  isBreaking: boolean,
): StoryVersionV1 {
  const raw = requireClosedRecord(value, path, STORY_KEYS);
  const version = requireInteger(raw.version, `${path}.version`, 1);
  const expectedCurrentVersion = requireInteger(
    raw.expected_current_version,
    `${path}.expected_current_version`,
  );
  if (version !== expectedCurrentVersion + 1) {
    throw new TypeError(
      "story version must equal expected_current_version + 1",
    );
  }
  const score = requireClosedRecord(
    raw.score_components,
    `${path}.score_components`,
    ["editorial", "impact", "freshness", "evidence", "diversity"],
  );
  if (!Array.isArray(raw.claims) || !Array.isArray(raw.evidence_refs)) {
    throw new TypeError(`${path}.claims and evidence_refs must be arrays`);
  }
  const claims = raw.claims.map((item, index) =>
    parseClaim(item, `${path}.claims[${index}]`),
  );
  const evidenceRefs = raw.evidence_refs.map((item, index) =>
    parseEvidence(item, `${path}.evidence_refs[${index}]`),
  );
  const evidenceIds = new Set(evidenceRefs.map((item) => item.evidence_id));
  if (evidenceIds.size !== evidenceRefs.length)
    throw new TypeError(`${path} duplicate evidence_id`);
  const claimIds = new Set<string>();
  for (const claim of claims) {
    if (claimIds.has(claim.claim_id))
      throw new TypeError(`${path} duplicate claim_id`);
    claimIds.add(claim.claim_id);
    for (const evidenceId of claim.evidence_ids) {
      if (!evidenceIds.has(evidenceId)) {
        throw new TypeError(`${path}: unknown evidence_id ${evidenceId}`);
      }
    }
  }
  const story: StoryVersionV1 = {
    story_id: requireString(raw.story_id, `${path}.story_id`),
    version,
    expected_current_version: expectedCurrentVersion,
    slug: requireString(raw.slug, `${path}.slug`),
    language: requireString(raw.language, `${path}.language`),
    domain: requireEnum(raw.domain, `${path}.domain`, [
      "immigration",
      "company",
      "tax",
      "property",
      "compliance",
      "general",
    ] as const),
    severity: requireEnum(raw.severity, `${path}.severity`, [
      "low",
      "medium",
      "high",
      "critical",
    ] as const),
    lifecycle_state: requireEnum(
      raw.lifecycle_state,
      `${path}.lifecycle_state`,
      ["developing", "verified", "amended", "superseded"] as const,
    ),
    first_seen_at: requireTimestamp(raw.first_seen_at, `${path}.first_seen_at`),
    updated_at: requireTimestamp(raw.updated_at, `${path}.updated_at`),
    title: requireString(raw.title, `${path}.title`),
    deck: requireString(raw.deck, `${path}.deck`),
    summary: requireString(raw.summary, `${path}.summary`),
    why_it_matters: requireString(raw.why_it_matters, `${path}.why_it_matters`),
    curiosity_text: requireNullableString(
      raw.curiosity_text,
      `${path}.curiosity_text`,
    ),
    score_components: {
      editorial: requireNumber(
        score.editorial,
        `${path}.score_components.editorial`,
      ),
      impact: requireNumber(score.impact, `${path}.score_components.impact`),
      freshness: requireNumber(
        score.freshness,
        `${path}.score_components.freshness`,
      ),
      evidence: requireNumber(
        score.evidence,
        `${path}.score_components.evidence`,
      ),
      diversity: requireNumber(
        score.diversity,
        `${path}.score_components.diversity`,
      ),
    },
    claims,
    evidence_refs: evidenceRefs,
    contributing_system_ids: requireStringArray(
      raw.contributing_system_ids,
      `${path}.contributing_system_ids`,
    ),
    coverage_state: requireEnum(raw.coverage_state, `${path}.coverage_state`, [
      "full",
      "partial",
    ] as const),
    confidence: requireEnum(raw.confidence, `${path}.confidence`, [
      "low",
      "medium",
      "high",
    ] as const),
    asset_digests: (() => {
      if (!Array.isArray(raw.asset_digests))
        throw new TypeError(`${path}.asset_digests must be an array`);
      return raw.asset_digests.map((item, index) =>
        requireSha256(item, `${path}.asset_digests[${index}]`),
      );
    })(),
    adapter_version: requireString(
      raw.adapter_version,
      `${path}.adapter_version`,
    ),
    ruleset_version: requireString(
      raw.ruleset_version,
      `${path}.ruleset_version`,
    ),
  };
  if (isBreaking) validateBreakingClaims(story);
  return story;
}

export function parseStoryPacket(raw: unknown): StoryPacketV1 {
  const packet = requireClosedRecord(raw, "story packet", [
    "schema_version",
    "packet_id",
    "publication_target",
    "expected_breaking_revision",
    "publication_state",
    "verified_at",
    "story",
  ]);
  if (packet.schema_version !== "story.v1") {
    throw new TypeError(
      `unsupported schema_version ${String(packet.schema_version)}`,
    );
  }
  return {
    schema_version: "story.v1",
    packet_id: requireString(packet.packet_id, "story packet.packet_id"),
    publication_target: requireEnum(
      packet.publication_target,
      "story packet.publication_target",
      ["breaking"] as const,
    ),
    expected_breaking_revision: requireInteger(
      packet.expected_breaking_revision,
      "story packet.expected_breaking_revision",
    ),
    publication_state: requireEnum(
      packet.publication_state,
      "story packet.publication_state",
      ["building"] as const,
    ),
    verified_at: requireTimestamp(
      packet.verified_at,
      "story packet.verified_at",
    ),
    story: parseStory(packet.story, "story packet.story", true),
  };
}

function parsePlacement(value: unknown, path: string): EditionPlacementV1 {
  const raw = requireClosedRecord(value, path, [
    "story_id",
    "version",
    "section",
    "order",
  ]);
  return {
    story_id: requireString(raw.story_id, `${path}.story_id`),
    version: requireInteger(raw.version, `${path}.version`, 1),
    section: requireEnum(raw.section, `${path}.section`, [
      "immigration",
      "company",
      "tax",
      "property",
      "compliance",
      "general",
    ] as const),
    order: requireInteger(raw.order, `${path}.order`, 1),
  };
}

function requireExactReferenceSet(
  declared: readonly string[],
  actual: ReadonlySet<string>,
  field: string,
): void {
  if (
    declared.length !== actual.size ||
    declared.some((item) => !actual.has(item))
  ) {
    throw new TypeError(
      `${field} must exactly match embedded story references`,
    );
  }
}

export function parseEditionPacket(raw: unknown): EditionPacketV1 {
  const packet = requireClosedRecord(raw, "edition packet", [
    "schema_version",
    "packet_id",
    "editor_version",
    "ruleset_version",
    "edition_date",
    "edition_revision",
    "expected_current_revision",
    "expected_breaking_revision",
    "edition_kind",
    "publication_state",
    "coverage_state",
    "readiness_cutoff",
    "verified_at",
    "collector_run_ids",
    "stories",
    "placements",
    "breaking_story_ids",
    "referenced_claim_ids",
    "referenced_evidence_ids",
    "asset_digests",
    "coverage_gaps",
    "reader_notices",
  ]);
  if (packet.schema_version !== "edition.v1") {
    throw new TypeError(
      `unsupported schema_version ${String(packet.schema_version)}`,
    );
  }
  const editionRevision = requireInteger(
    packet.edition_revision,
    "edition packet.edition_revision",
    1,
  );
  const expectedCurrentRevision = requireInteger(
    packet.expected_current_revision,
    "edition packet.expected_current_revision",
  );
  if (editionRevision !== expectedCurrentRevision + 1) {
    throw new TypeError(
      "edition_revision must equal expected_current_revision + 1",
    );
  }
  if (!Array.isArray(packet.stories) || !Array.isArray(packet.placements)) {
    throw new TypeError("edition packet stories and placements must be arrays");
  }
  const stories = packet.stories.map((item, index) =>
    parseStory(item, `edition packet.stories[${index}]`, false),
  );
  const storyIds = new Set(stories.map((item) => item.story_id));
  if (storyIds.size !== stories.length)
    throw new TypeError("edition packet contains duplicate story_id");
  const storyKeys = new Set(
    stories.map((item) => `${item.story_id}:${item.version}`),
  );
  if (storyKeys.size !== stories.length)
    throw new TypeError("edition packet contains duplicate story version");
  const placements = packet.placements.map((item, index) =>
    parsePlacement(item, `edition packet.placements[${index}]`),
  );
  for (const placement of placements) {
    if (!storyKeys.has(`${placement.story_id}:${placement.version}`)) {
      throw new TypeError(
        `edition placement references unknown story version ${placement.story_id}`,
      );
    }
  }
  const breakingStoryIds = requireStringArray(
    packet.breaking_story_ids,
    "edition packet.breaking_story_ids",
  );
  const storiesById = new Map(stories.map((story) => [story.story_id, story]));
  for (const storyId of breakingStoryIds) {
    const breakingStory = storiesById.get(storyId);
    if (!breakingStory)
      throw new TypeError(`Breaking list references unknown story ${storyId}`);
    validateBreakingClaims(breakingStory);
  }
  const referencedClaimIds = requireStringArray(
    packet.referenced_claim_ids,
    "edition packet.referenced_claim_ids",
  );
  const referencedEvidenceIds = requireStringArray(
    packet.referenced_evidence_ids,
    "edition packet.referenced_evidence_ids",
  );
  if (!Array.isArray(packet.asset_digests)) {
    throw new TypeError("edition packet.asset_digests must be an array");
  }
  const assetDigests = packet.asset_digests.map((item, index) =>
    requireSha256(item, `edition packet.asset_digests[${index}]`),
  );
  requireExactReferenceSet(
    referencedClaimIds,
    new Set(
      stories.flatMap((story) => story.claims.map((claim) => claim.claim_id)),
    ),
    "referenced_claim_ids",
  );
  requireExactReferenceSet(
    referencedEvidenceIds,
    new Set(
      stories.flatMap((story) =>
        story.evidence_refs.map((evidence) => evidence.evidence_id),
      ),
    ),
    "referenced_evidence_ids",
  );
  requireExactReferenceSet(
    assetDigests,
    new Set(stories.flatMap((story) => story.asset_digests)),
    "asset_digests",
  );
  return {
    schema_version: "edition.v1",
    packet_id: requireString(packet.packet_id, "edition packet.packet_id"),
    editor_version: requireString(
      packet.editor_version,
      "edition packet.editor_version",
    ),
    ruleset_version: requireString(
      packet.ruleset_version,
      "edition packet.ruleset_version",
    ),
    edition_date: (() => {
      const date = requireString(
        packet.edition_date,
        "edition packet.edition_date",
      );
      if (!/^\d{4}-\d{2}-\d{2}$/.test(date))
        throw new TypeError("edition_date must be an ISO date");
      return date;
    })(),
    edition_revision: editionRevision,
    expected_current_revision: expectedCurrentRevision,
    expected_breaking_revision: requireInteger(
      packet.expected_breaking_revision,
      "edition packet.expected_breaking_revision",
    ),
    edition_kind: requireEnum(
      packet.edition_kind,
      "edition packet.edition_kind",
      ["standard", "quiet"] as const,
    ),
    publication_state: requireEnum(
      packet.publication_state,
      "edition packet.publication_state",
      ["building"] as const,
    ),
    coverage_state: requireEnum(
      packet.coverage_state,
      "edition packet.coverage_state",
      ["complete", "partial"] as const,
    ),
    readiness_cutoff: requireTimestamp(
      packet.readiness_cutoff,
      "edition packet.readiness_cutoff",
    ),
    verified_at: requireTimestamp(
      packet.verified_at,
      "edition packet.verified_at",
    ),
    collector_run_ids: requireStringArray(
      packet.collector_run_ids,
      "edition packet.collector_run_ids",
    ),
    stories,
    placements,
    breaking_story_ids: breakingStoryIds,
    referenced_claim_ids: referencedClaimIds,
    referenced_evidence_ids: referencedEvidenceIds,
    asset_digests: assetDigests,
    coverage_gaps: requireStringArray(
      packet.coverage_gaps,
      "edition packet.coverage_gaps",
    ),
    reader_notices: requireStringArray(
      packet.reader_notices,
      "edition packet.reader_notices",
    ),
  };
}
