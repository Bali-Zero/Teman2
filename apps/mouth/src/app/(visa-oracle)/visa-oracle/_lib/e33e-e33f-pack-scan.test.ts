import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import {
  E33E_DEPOSIT_THRESHOLD_USD,
  SUPPORT_REASON_COPY,
} from "./engine-adapter";

// Carry-over of PR #8511 re-sign condition 3: pin the structural pack scan
// separating E33E from E33F so that if a future signed pack changes what
// separates the two products, this guard fails until E33F_E33E_DEPOSIT_NOTE
// in engine-adapter.ts and this scan are revisited together.

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PACKS_DIR = path.resolve(
  __dirname,
  "../../../../../../backend-rag/backend/services/visa_engine/contracts/packs",
);

const CURE_MESSAGE =
  "a signed pack changed what separates E33E from E33F: revisit E33F_E33E_DEPOSIT_NOTE in engine-adapter.ts and this scan";

const EXPECTED_E33E_ONLY_RULES = [
  "el.e33e.age-55-59-disputed-band",
  "el.e33e.retirement",
  "hf.e33e.age-below-55",
  "hf.e33e.retirement-income-below-minimum",
];

const EXPECTED_UNTWINNED_E33E_RULES = [
  "el.e33e.age-55-59-disputed-band",
  "el.e33e.retirement",
];

const NAMED_E33E_ELIGIBILITY_RULES = new Set(EXPECTED_UNTWINNED_E33E_RULES);

const EXPECTED_GLOBAL_RULE_COUNT = 5;

const TWIN_IGNORED_KEYS = new Set([
  "rule_id",
  "product_version_ids",
  "explanation_key",
  "source_refs",
]);

type PackRuleEffect = {
  type: string;
  reason_code?: string;
  covered_purposes?: string[];
};

type PackValidPeriod = {
  from?: string | null;
  to?: string | null;
};

type PackRule = {
  rule_id: string;
  scope: string;
  product_version_ids?: string[] | null;
  effect?: PackRuleEffect;
  stage?: string;
  on_unknown?: string;
  valid_period?: PackValidPeriod;
  explanation_key?: string;
  priority?: number;
  required_facts?: string[];
  safety_critical?: boolean;
  source_refs?: string[];
  when?: unknown;
};

type PackProduct = {
  product_code: string;
  product_version_id: string;
  covered_purposes?: string[];
};

type Pack = {
  sequence: number;
  rules: PackRule[];
  products: PackProduct[];
};

type RetirementDelta = {
  missingE33fLeaves: Record<string, unknown>[];
  e33eOnlyLeaves: Record<string, unknown>[];
  ageLeaf: Record<string, unknown> | undefined;
  depositLeaf: Record<string, unknown> | undefined;
  stateBankLeaf: Record<string, unknown> | undefined;
  ownNameLeaf: Record<string, unknown> | undefined;
  unexpectedLeaves: Record<string, unknown>[];
  onUnknownMatches: boolean;
  validPeriodMatches: boolean;
  e33eCoversRetirement: boolean;
  e33fCoversRetirement: boolean;
};

type ScanFacts = {
  e33eOnlyRuleIds: string[];
  e33eOnlyUntwinned: string[];
  e33fOnlyUntwinned: string[];
  twinsChecked: string[];
  twinMismatches: string[];
  retirementDelta: RetirementDelta;
  disputedBandExcludes: boolean;
  disputedBandEffectType: string | undefined;
  disputedBandHasDepositTrio: boolean;
  bothProductRules: string[];
  e33eOnlyExcludes: string[];
  depositThreshold: number | undefined;
  globalRuleCount: number;
  noteThresholdUsd: number;
  problems: string[];
};

function newestSignedPack(): Pack {
  const numbers = fs
    .readdirSync(PACKS_DIR)
    .map((name) => /^rulepack-prod-(\d+)\.signed\.json$/.exec(name))
    .filter((match): match is RegExpExecArray => match !== null)
    .map((match) => Number(match[1]));
  if (numbers.length === 0) throw new Error("no signed production pack found");
  const newest = Math.max(...numbers);
  const name = `rulepack-prod-${String(newest).padStart(3, "0")}.signed.json`;
  const envelope = JSON.parse(
    fs.readFileSync(path.join(PACKS_DIR, name), "utf-8"),
  ) as { payload?: Partial<Pack> };
  const payload = envelope.payload;
  if (
    !payload ||
    payload.sequence !== newest ||
    !Array.isArray(payload.rules) ||
    !Array.isArray(payload.products)
  ) {
    throw new Error(
      `${name}: payload is malformed or its sequence is not ${newest}`,
    );
  }
  return payload as Pack;
}

function isRecord(node: unknown): node is Record<string, unknown> {
  return node !== null && typeof node === "object" && !Array.isArray(node);
}

function stableJson(value: unknown): string {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableJson(item)).join(",")}]`;
  }
  const record = value as Record<string, unknown>;
  const entries = Object.keys(record)
    .filter((key) => record[key] !== undefined)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableJson(record[key])}`);
  return `{${entries.join(",")}}`;
}

function comparableRuleBody(rule: PackRule): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(rule)) {
    if (!TWIN_IGNORED_KEYS.has(key) && value !== undefined) {
      out[key] = value;
    }
  }
  return out;
}

function flattenAndLeaves(node: unknown): Record<string, unknown>[] {
  if (!isRecord(node)) return [];
  if (node.op === "all" && Array.isArray(node.args)) {
    return node.args.flatMap((arg) => flattenAndLeaves(arg));
  }
  return [node];
}

function multisetDiff(
  minuend: Record<string, unknown>[],
  subtrahend: Record<string, unknown>[],
): Record<string, unknown>[] {
  const counts = new Map<string, number>();
  for (const item of subtrahend) {
    const key = stableJson(item);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const diff: Record<string, unknown>[] = [];
  for (const item of minuend) {
    const key = stableJson(item);
    const remaining = counts.get(key) ?? 0;
    if (remaining > 0) {
      counts.set(key, remaining - 1);
    } else {
      diff.push(item);
    }
  }
  return diff;
}

function expectedE33eRetirementExtraLeaves(
  noteThresholdUsd: number,
): Record<string, unknown>[] {
  return [
    { fact: "derived.age_years", op: "gte", value: 55 },
    {
      fact: "secondhome.bank_deposit_usd",
      op: "gte",
      value: noteThresholdUsd,
    },
    {
      fact: "secondhome.bank_deposit_at_state_bank",
      op: "eq",
      value: true,
    },
    {
      fact: "secondhome.bank_deposit_in_own_name",
      op: "eq",
      value: true,
    },
  ];
}

function problem(detail: string): string {
  return `${CURE_MESSAGE} (${detail})`;
}

function violations(
  facts: Omit<ScanFacts, "problems">,
  structuralErrors: string[],
): string[] {
  const out = [...structuralErrors];

  if (
    stableJson(facts.e33eOnlyUntwinned) !==
    stableJson(EXPECTED_UNTWINNED_E33E_RULES)
  ) {
    out.push(
      problem(
        `expected untwinned E33E-only rules ${EXPECTED_UNTWINNED_E33E_RULES.join(", ")}, got ${facts.e33eOnlyUntwinned.join(", ")}`,
      ),
    );
  }

  if (facts.twinMismatches.length > 0) {
    out.push(
      problem(
        `E33E rules lacking an identical E33F twin: ${facts.twinMismatches.join(", ")}`,
      ),
    );
  }

  if (facts.e33fOnlyUntwinned.length > 0) {
    out.push(
      problem(
        `E33F-only rules lacking an identical E33E twin: ${facts.e33fOnlyUntwinned.join(", ")}`,
      ),
    );
  }

  if (facts.e33eOnlyExcludes.length > 0) {
    out.push(
      problem(
        `E33E-only EXCLUDE rules without an identical E33F twin: ${facts.e33eOnlyExcludes.join(", ")}`,
      ),
    );
  }

  if (facts.bothProductRules.length > 0) {
    out.push(
      problem(
        `rules targeting both E33E and E33F: ${facts.bothProductRules.join(", ")}`,
      ),
    );
  }

  if (facts.globalRuleCount !== EXPECTED_GLOBAL_RULE_COUNT) {
    out.push(
      problem(
        `expected ${EXPECTED_GLOBAL_RULE_COUNT} GLOBAL rules, got ${facts.globalRuleCount}`,
      ),
    );
  }

  if (!facts.retirementDelta.onUnknownMatches) {
    out.push(
      problem("el.e33e.retirement and el.e33f.retirement differ on on_unknown"),
    );
  }

  if (!facts.retirementDelta.validPeriodMatches) {
    out.push(
      problem(
        "el.e33e.retirement and el.e33f.retirement differ on valid_period",
      ),
    );
  }

  if (!facts.retirementDelta.e33eCoversRetirement) {
    out.push(
      problem(
        "el.e33e.retirement effect.covered_purposes does not include RETIREMENT",
      ),
    );
  }

  if (!facts.retirementDelta.e33fCoversRetirement) {
    out.push(
      problem(
        "el.e33f.retirement effect.covered_purposes does not include RETIREMENT",
      ),
    );
  }

  if (facts.retirementDelta.missingE33fLeaves.length > 0) {
    out.push(
      problem(
        `el.e33e.retirement is missing el.e33f.retirement leaves: ${stableJson(facts.retirementDelta.missingE33fLeaves)}`,
      ),
    );
  }

  const actualE33eOnlyLeavesJson = facts.retirementDelta.e33eOnlyLeaves
    .map((leaf) => stableJson(leaf))
    .sort();
  const expectedE33eOnlyLeavesJson = expectedE33eRetirementExtraLeaves(
    facts.noteThresholdUsd,
  )
    .map((leaf) => stableJson(leaf))
    .sort();
  if (
    stableJson(actualE33eOnlyLeavesJson) !==
    stableJson(expectedE33eOnlyLeavesJson)
  ) {
    out.push(
      problem(
        `el.e33e.retirement E33E-only leaves ${stableJson(actualE33eOnlyLeavesJson)} !== expected ${stableJson(expectedE33eOnlyLeavesJson)}`,
      ),
    );
  }

  if (facts.depositThreshold !== facts.noteThresholdUsd) {
    out.push(
      problem(
        `pack deposit threshold ${String(facts.depositThreshold)} !== note threshold ${facts.noteThresholdUsd}`,
      ),
    );
  }

  if (
    facts.disputedBandExcludes ||
    facts.disputedBandEffectType !== "SUPPORT"
  ) {
    out.push(
      problem(
        `el.e33e.age-55-59-disputed-band effect is ${String(facts.disputedBandEffectType)}`,
      ),
    );
  }

  if (!facts.disputedBandHasDepositTrio) {
    out.push(
      problem(
        "el.e33e.age-55-59-disputed-band no longer requires the deposit trio",
      ),
    );
  }

  return out;
}

function scanE33eVsE33f(
  payload: Pack,
  noteThresholdUsd: number = E33E_DEPOSIT_THRESHOLD_USD,
): ScanFacts {
  const structuralErrors: string[] = [];
  const e33eProduct = payload.products.find((p) => p.product_code === "E33E");
  const e33fProduct = payload.products.find((p) => p.product_code === "E33F");
  if (!e33eProduct) {
    structuralErrors.push(problem("E33E product missing from pack"));
  }
  if (!e33fProduct) {
    structuralErrors.push(problem("E33F product missing from pack"));
  }
  const e33eId = e33eProduct?.product_version_id ?? "";
  const e33fId = e33fProduct?.product_version_id ?? "";

  const targetsE33e = (rule: PackRule): boolean =>
    rule.scope === "PRODUCTS" &&
    Array.isArray(rule.product_version_ids) &&
    rule.product_version_ids.includes(e33eId);

  const targetsE33f = (rule: PackRule): boolean =>
    rule.scope === "PRODUCTS" &&
    Array.isArray(rule.product_version_ids) &&
    rule.product_version_ids.includes(e33fId);

  const bothProductRules = payload.rules
    .filter((rule) => targetsE33e(rule) && targetsE33f(rule))
    .map((rule) => rule.rule_id)
    .sort();

  const e33eOnlyRules = payload.rules.filter(
    (rule) => targetsE33e(rule) && !targetsE33f(rule),
  );
  const e33fOnlyRules = payload.rules.filter(
    (rule) => targetsE33f(rule) && !targetsE33e(rule),
  );

  const e33eOnlyRuleIds = e33eOnlyRules.map((rule) => rule.rule_id).sort();

  const twinsChecked: string[] = [];
  const twinMismatches: string[] = [];
  const e33eOnlyUntwinned: string[] = [];
  const e33eOnlyExcludes: string[] = [];
  const twinnedE33fRuleIds = new Set<string>();

  for (const rule of e33eOnlyRules) {
    const isNamedEligibility = NAMED_E33E_ELIGIBILITY_RULES.has(rule.rule_id);
    const twinId = rule.rule_id.includes("e33e")
      ? rule.rule_id.replace("e33e", "e33f")
      : null;
    const twinCandidates = twinId
      ? e33fOnlyRules.filter((candidate) => candidate.rule_id === twinId)
      : [];
    const twin = twinCandidates.length === 1 ? twinCandidates[0] : undefined;
    const hasIdenticalTwin =
      twin !== undefined &&
      stableJson(comparableRuleBody(twin)) ===
        stableJson(comparableRuleBody(rule));

    if (hasIdenticalTwin && twin) {
      twinnedE33fRuleIds.add(twin.rule_id);
    } else {
      e33eOnlyUntwinned.push(rule.rule_id);
    }

    if (!isNamedEligibility) {
      if (hasIdenticalTwin) {
        twinsChecked.push(rule.rule_id);
      } else {
        twinMismatches.push(rule.rule_id);
      }
    }

    if (rule.effect?.type === "EXCLUDE" && !hasIdenticalTwin) {
      e33eOnlyExcludes.push(rule.rule_id);
    }
  }
  twinsChecked.sort();
  twinMismatches.sort();
  e33eOnlyUntwinned.sort();
  e33eOnlyExcludes.sort();

  const e33fOnlyUntwinned = e33fOnlyRules
    .filter(
      (rule) =>
        rule.rule_id !== "el.e33f.retirement" &&
        !twinnedE33fRuleIds.has(rule.rule_id),
    )
    .map((rule) => rule.rule_id)
    .sort();

  const e33eRetirement = e33eOnlyRules.find(
    (rule) => rule.rule_id === "el.e33e.retirement",
  );
  const e33fRetirement = e33fOnlyRules.find(
    (rule) => rule.rule_id === "el.e33f.retirement",
  );
  if (!e33eRetirement) {
    structuralErrors.push(
      problem("el.e33e.retirement missing from E33E rules"),
    );
  }
  if (!e33fRetirement) {
    structuralErrors.push(
      problem("el.e33f.retirement missing from E33F rules"),
    );
  }

  const onUnknownMatches =
    Boolean(e33eRetirement && e33fRetirement) &&
    e33eRetirement?.on_unknown === e33fRetirement?.on_unknown;
  const validPeriodMatches =
    Boolean(e33eRetirement && e33fRetirement) &&
    stableJson(e33eRetirement?.valid_period) ===
      stableJson(e33fRetirement?.valid_period);
  const e33eCoversRetirement = Boolean(
    e33eRetirement?.effect?.covered_purposes?.includes("RETIREMENT"),
  );
  const e33fCoversRetirement = Boolean(
    e33fRetirement?.effect?.covered_purposes?.includes("RETIREMENT"),
  );

  const e33eLeaves = flattenAndLeaves(e33eRetirement?.when);
  const e33fLeaves = flattenAndLeaves(e33fRetirement?.when);

  const missingE33fLeaves = multisetDiff(e33fLeaves, e33eLeaves);
  const e33eOnlyLeaves = multisetDiff(e33eLeaves, e33fLeaves);
  const unexpectedLeaves = multisetDiff(
    e33eOnlyLeaves,
    expectedE33eRetirementExtraLeaves(noteThresholdUsd),
  );

  const ageLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "derived.age_years",
  );
  const depositLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "secondhome.bank_deposit_usd",
  );
  const stateBankLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "secondhome.bank_deposit_at_state_bank",
  );
  const ownNameLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "secondhome.bank_deposit_in_own_name",
  );

  const depositThreshold =
    typeof depositLeaf?.value === "number" ? depositLeaf.value : undefined;

  const disputedBandRule = e33eOnlyRules.find(
    (rule) => rule.rule_id === "el.e33e.age-55-59-disputed-band",
  );
  if (!disputedBandRule) {
    structuralErrors.push(
      problem("el.e33e.age-55-59-disputed-band missing from E33E rules"),
    );
  }
  const disputedBandEffectType = disputedBandRule?.effect?.type;
  const disputedBandExcludes = disputedBandEffectType === "EXCLUDE";
  const disputedLeaves = new Set(
    flattenAndLeaves(disputedBandRule?.when).map((leaf) => stableJson(leaf)),
  );
  const disputedBandHasDepositTrio =
    depositLeaf !== undefined &&
    stateBankLeaf !== undefined &&
    ownNameLeaf !== undefined &&
    disputedLeaves.has(stableJson(depositLeaf)) &&
    disputedLeaves.has(stableJson(stateBankLeaf)) &&
    disputedLeaves.has(stableJson(ownNameLeaf));

  const globalRules = payload.rules.filter((rule) => rule.scope === "GLOBAL");
  const globalRuleCount = globalRules.length;
  const globalRulesWithProducts = globalRules
    .filter(
      (rule) =>
        Array.isArray(rule.product_version_ids) &&
        rule.product_version_ids.length > 0,
    )
    .map((rule) => rule.rule_id)
    .sort();
  if (globalRulesWithProducts.length > 0) {
    structuralErrors.push(
      problem(
        `GLOBAL rules with non-empty product_version_ids: ${globalRulesWithProducts.join(", ")}`,
      ),
    );
  }

  const baseFacts: Omit<ScanFacts, "problems"> = {
    e33eOnlyRuleIds,
    e33eOnlyUntwinned,
    e33fOnlyUntwinned,
    twinsChecked,
    twinMismatches,
    retirementDelta: {
      missingE33fLeaves,
      e33eOnlyLeaves,
      ageLeaf,
      depositLeaf,
      stateBankLeaf,
      ownNameLeaf,
      unexpectedLeaves,
      onUnknownMatches,
      validPeriodMatches,
      e33eCoversRetirement,
      e33fCoversRetirement,
    },
    disputedBandExcludes,
    disputedBandEffectType,
    disputedBandHasDepositTrio,
    bothProductRules,
    e33eOnlyExcludes,
    depositThreshold,
    globalRuleCount,
    noteThresholdUsd,
  };

  return {
    ...baseFacts,
    problems: violations(baseFacts, structuralErrors),
  };
}

function mutateDepositThreshold(node: unknown, value: number): number {
  if (!isRecord(node)) return 0;
  let count = 0;
  if (
    node.fact === "secondhome.bank_deposit_usd" &&
    node.op === "gte" &&
    typeof node.value === "number"
  ) {
    node.value = value;
    count += 1;
  }
  if (Array.isArray(node.args)) {
    for (const arg of node.args) {
      count += mutateDepositThreshold(arg, value);
    }
  }
  return count;
}

function mutateAllE33eDepositThresholds(pack: Pack, value: number): number {
  const e33e = pack.products.find((p) => p.product_code === "E33E");
  const e33f = pack.products.find((p) => p.product_code === "E33F");
  if (!e33e || !e33f) throw new Error("E33E or E33F missing");
  let count = 0;
  for (const rule of pack.rules) {
    if (
      rule.scope === "PRODUCTS" &&
      Array.isArray(rule.product_version_ids) &&
      rule.product_version_ids.includes(e33e.product_version_id) &&
      !rule.product_version_ids.includes(e33f.product_version_id)
    ) {
      count += mutateDepositThreshold(rule.when, value);
    }
  }
  return count;
}

function appendToTopLevelAll(
  when: unknown,
  clause: Record<string, unknown>,
): void {
  if (!isRecord(when) || when.op !== "all" || !Array.isArray(when.args)) {
    throw new Error("expected top-level op:all with args array");
  }
  when.args.push(clause);
}

function removeDepositClauses(node: unknown): unknown {
  if (!isRecord(node)) return node;
  if (Array.isArray(node.args)) {
    const kept = node.args
      .map((arg) => removeDepositClauses(arg))
      .filter((arg) => {
        if (!isRecord(arg)) return true;
        if (
          typeof arg.fact === "string" &&
          arg.fact.startsWith("secondhome.bank_deposit_")
        ) {
          return false;
        }
        if (arg.op === "all" && Array.isArray(arg.args)) {
          return arg.args.length > 0;
        }
        return true;
      });
    return { ...node, args: kept };
  }
  return node;
}

describe("E33E vs E33F pack scan", () => {
  it("innocence: the newest signed pack has no problems (E33E-only rules are the four named, each twin identical)", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.problems, CURE_MESSAGE).toEqual([]);
    expect(scan.e33eOnlyRuleIds, CURE_MESSAGE).toEqual(
      EXPECTED_E33E_ONLY_RULES,
    );
    expect(scan.twinMismatches, CURE_MESSAGE).toEqual([]);
    expect(scan.e33fOnlyUntwinned, CURE_MESSAGE).toEqual([]);
    expect(scan.globalRuleCount, CURE_MESSAGE).toBe(EXPECTED_GLOBAL_RULE_COUNT);
  });

  it("the E33E-only rules are exactly the hard filters with identical twins plus el.e33e.retirement and the disputed-band rule", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.e33eOnlyRuleIds, CURE_MESSAGE).toEqual([
      "el.e33e.age-55-59-disputed-band",
      "el.e33e.retirement",
      "hf.e33e.age-below-55",
      "hf.e33e.retirement-income-below-minimum",
    ]);
    expect(scan.e33eOnlyUntwinned, CURE_MESSAGE).toEqual(
      EXPECTED_UNTWINNED_E33E_RULES,
    );
    expect(scan.twinsChecked, CURE_MESSAGE).toEqual([
      "hf.e33e.age-below-55",
      "hf.e33e.retirement-income-below-minimum",
    ]);
    expect(scan.twinMismatches, CURE_MESSAGE).toEqual([]);
    expect(scan.e33fOnlyUntwinned, CURE_MESSAGE).toEqual([]);
    expect(scan.e33eOnlyExcludes, CURE_MESSAGE).toEqual([]);
  });

  it("el.e33e.retirement is the E33F rule plus age 55 or more plus the deposit trio", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.retirementDelta.missingE33fLeaves, CURE_MESSAGE).toEqual([]);
    expect(scan.retirementDelta.unexpectedLeaves, CURE_MESSAGE).toEqual([]);
    expect(scan.retirementDelta.onUnknownMatches, CURE_MESSAGE).toBe(true);
    expect(scan.retirementDelta.validPeriodMatches, CURE_MESSAGE).toBe(true);
    expect(scan.retirementDelta.e33eCoversRetirement, CURE_MESSAGE).toBe(true);
    expect(scan.retirementDelta.e33fCoversRetirement, CURE_MESSAGE).toBe(true);
    expect(scan.retirementDelta.ageLeaf, CURE_MESSAGE).toEqual({
      fact: "derived.age_years",
      op: "gte",
      value: 55,
    });
    expect(scan.retirementDelta.depositLeaf, CURE_MESSAGE).toEqual({
      fact: "secondhome.bank_deposit_usd",
      op: "gte",
      value: E33E_DEPOSIT_THRESHOLD_USD,
    });
    expect(scan.retirementDelta.stateBankLeaf, CURE_MESSAGE).toEqual({
      fact: "secondhome.bank_deposit_at_state_bank",
      op: "eq",
      value: true,
    });
    expect(scan.retirementDelta.ownNameLeaf, CURE_MESSAGE).toEqual({
      fact: "secondhome.bank_deposit_in_own_name",
      op: "eq",
      value: true,
    });
  });

  it("the disputed-band rule never excludes and itself requires the deposit trio", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.disputedBandExcludes, CURE_MESSAGE).toBe(false);
    expect(scan.disputedBandEffectType, CURE_MESSAGE).toBe("SUPPORT");
    expect(scan.disputedBandHasDepositTrio, CURE_MESSAGE).toBe(true);
  });

  it("no rule targets both E33E and E33F", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.bothProductRules, CURE_MESSAGE).toEqual([]);
    expect(scan.globalRuleCount, CURE_MESSAGE).toBe(EXPECTED_GLOBAL_RULE_COUNT);
  });

  it("the note's EN and ID figures equal the pack's deposit threshold", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    const threshold = Number(scan.depositThreshold);
    const note = SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE;
    expect(threshold, CURE_MESSAGE).toBe(E33E_DEPOSIT_THRESHOLD_USD);
    expect(note.en, CURE_MESSAGE).toContain("50,000");
    expect(note.id, CURE_MESSAGE).toContain("50.000");
    expect(note.en, CURE_MESSAGE).toContain(
      new Intl.NumberFormat("en-US").format(threshold),
    );
    expect(note.id, CURE_MESSAGE).toContain(
      new Intl.NumberFormat("id-ID").format(threshold),
    );
  });

  it("the note names the state-owned bank and the own-name condition in EN and ID", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    const note = SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE;
    expect(scan.retirementDelta.stateBankLeaf, CURE_MESSAGE).toBeDefined();
    expect(scan.retirementDelta.ownNameLeaf, CURE_MESSAGE).toBeDefined();
    expect(note.en, CURE_MESSAGE).toMatch(/state-owned bank/);
    expect(note.en, CURE_MESSAGE).toMatch(/your own name/);
    expect(note.id, CURE_MESSAGE).toMatch(/bank milik negara/);
    expect(note.id, CURE_MESSAGE).toMatch(/atas nama Anda sendiri/);
  });

  it("a harmless new identical twin pair does not fail the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const baseE33e = pack.rules.find(
      (r) => r.rule_id === "hf.e33e.age-below-55",
    );
    const baseE33f = pack.rules.find(
      (r) => r.rule_id === "hf.e33f.age-below-55",
    );
    if (!baseE33e || !baseE33f) {
      throw new Error("hf.e33e.age-below-55 or hf.e33f.age-below-55 missing");
    }
    const newE33e = structuredClone(baseE33e);
    newE33e.rule_id = "hf.e33e.age-above-120";
    newE33e.when = { fact: "derived.age_years", op: "gt", value: 120 };
    const newE33f = structuredClone(baseE33f);
    newE33f.rule_id = "hf.e33f.age-above-120";
    newE33f.when = { fact: "derived.age_years", op: "gt", value: 120 };
    pack.rules.push(newE33e, newE33f);
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.twinsChecked, CURE_MESSAGE).toContain("hf.e33e.age-above-120");
    expect(scan.problems, CURE_MESSAGE).toEqual([]);
  });

  // Guilt probes: mutate a clone of the newest signed pack in memory (locating
  // targets by rule_id / product_code) to prove the scan fails with the cure
  // message when any invariant separating E33E from E33F drifts.

  it("guilt: a changed deposit threshold fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    expect(mutateAllE33eDepositThresholds(pack, 60000)).toBeGreaterThanOrEqual(
      2,
    );
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.disputedBandHasDepositTrio).toBe(true);
    expect(
      scan.problems.some((p) =>
        p.includes(
          `pack deposit threshold 60000 !== note threshold ${E33E_DEPOSIT_THRESHOLD_USD}`,
        ),
      ),
    ).toBe(true);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: removing the deposit clause from el.e33e.retirement fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "el.e33e.retirement");
    if (!rule) throw new Error("el.e33e.retirement missing");
    rule.when = removeDepositClauses(rule.when);
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: appending an age cap to el.e33e.retirement fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "el.e33e.retirement");
    if (!rule) throw new Error("el.e33e.retirement missing");
    appendToTopLevelAll(rule.when, {
      fact: "derived.age_years",
      op: "lte",
      value: 80,
    });
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: appending a second deposit leaf to el.e33e.retirement fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "el.e33e.retirement");
    if (!rule) throw new Error("el.e33e.retirement missing");
    appendToTopLevelAll(rule.when, {
      fact: "secondhome.bank_deposit_usd",
      op: "gte",
      value: 100000,
    });
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: appending a contradictory state-bank leaf to el.e33e.retirement fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "el.e33e.retirement");
    if (!rule) throw new Error("el.e33e.retirement missing");
    appendToTopLevelAll(rule.when, {
      fact: "secondhome.bank_deposit_at_state_bank",
      op: "eq",
      value: false,
    });
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: a new E33E-only EXCLUDE rule fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const e33e = pack.products.find((p) => p.product_code === "E33E");
    if (!e33e) throw new Error("E33E missing");
    pack.rules.push({
      rule_id: "hf.e33e.extra-exclude",
      scope: "PRODUCTS",
      product_version_ids: [e33e.product_version_id],
      stage: "HARD_FILTER",
      effect: { type: "EXCLUDE", reason_code: "EXTRA_EXCLUDE" },
      when: {
        fact: "secondhome.bank_deposit_usd",
        op: "lt",
        value: E33E_DEPOSIT_THRESHOLD_USD,
      },
    });
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.e33eOnlyExcludes).toContain("hf.e33e.extra-exclude");
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: a new E33F-only SUPPORT rule fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const e33f = pack.products.find((p) => p.product_code === "E33F");
    if (!e33f) throw new Error("E33F missing");
    pack.rules.push({
      rule_id: "el.e33f.retirement-alt",
      scope: "PRODUCTS",
      product_version_ids: [e33f.product_version_id],
      stage: "ELIGIBILITY",
      on_unknown: "NEEDS_INPUT",
      effect: { type: "SUPPORT", covered_purposes: ["RETIREMENT"] },
      when: {
        fact: "intent.purposes",
        op: "intersects",
        values: ["RETIREMENT"],
      },
    });
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.e33fOnlyUntwinned).toContain("el.e33f.retirement-alt");
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain("el.e33f.retirement-alt");
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: adding or removing a global rule fails the scan", () => {
    const packWithExtra = structuredClone(newestSignedPack());
    const globalRule = packWithExtra.rules.find((r) => r.scope === "GLOBAL");
    if (!globalRule) throw new Error("no GLOBAL rule found");
    packWithExtra.rules.push({
      ...structuredClone(globalRule),
      rule_id: `${globalRule.rule_id}-extra`,
    });
    const scanExtra = scanE33eVsE33f(packWithExtra, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scanExtra.globalRuleCount).toBe(EXPECTED_GLOBAL_RULE_COUNT + 1);
    expect(scanExtra.problems.length).toBeGreaterThan(0);
    expect(scanExtra.problems.join("\n")).toContain(CURE_MESSAGE);

    const packWithFewer = structuredClone(newestSignedPack());
    const idx = packWithFewer.rules.findIndex((r) => r.scope === "GLOBAL");
    if (idx === -1) throw new Error("no GLOBAL rule found");
    packWithFewer.rules.splice(idx, 1);
    const scanFewer = scanE33eVsE33f(packWithFewer, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scanFewer.globalRuleCount).toBe(EXPECTED_GLOBAL_RULE_COUNT - 1);
    expect(scanFewer.problems.length).toBeGreaterThan(0);
    expect(scanFewer.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: a twin whose on_unknown differs fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "hf.e33e.age-below-55");
    if (!rule) throw new Error("hf.e33e.age-below-55 missing");
    rule.on_unknown = "HUMAN_REVIEW";
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.twinMismatches).toContain("hf.e33e.age-below-55");
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: el.e33e.retirement no longer covering RETIREMENT fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "el.e33e.retirement");
    if (!rule?.effect?.covered_purposes) {
      throw new Error("el.e33e.retirement covered_purposes missing");
    }
    rule.effect.covered_purposes = rule.effect.covered_purposes.filter(
      (purpose) => purpose !== "RETIREMENT",
    );
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.retirementDelta.e33eCoversRetirement).toBe(false);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: el.e33e.retirement with a closed validity period fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "el.e33e.retirement");
    if (!rule?.valid_period) {
      throw new Error("el.e33e.retirement valid_period missing");
    }
    rule.valid_period.to = "2026-11-01T00:00:00Z";
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.retirementDelta.validPeriodMatches).toBe(false);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: turning the disputed-band rule into an EXCLUDE fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find(
      (r) => r.rule_id === "el.e33e.age-55-59-disputed-band",
    );
    if (!rule) throw new Error("el.e33e.age-55-59-disputed-band missing");
    rule.effect = { type: "EXCLUDE", reason_code: "DISPUTED_BAND_EXCLUDED" };
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.disputedBandExcludes).toBe(true);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });

  it("guilt: a rule that targets both products fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const e33e = pack.products.find((p) => p.product_code === "E33E");
    const e33f = pack.products.find((p) => p.product_code === "E33F");
    const rule = pack.rules.find((r) => r.rule_id === "hf.e33f.age-below-55");
    if (!e33e || !e33f || !rule) {
      throw new Error("E33E, E33F, or hf.e33f.age-below-55 missing");
    }
    rule.product_version_ids = [
      e33e.product_version_id,
      e33f.product_version_id,
    ];
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.bothProductRules).toEqual(["hf.e33f.age-below-55"]);
    expect(scan.problems.length).toBeGreaterThan(0);
    expect(scan.problems.join("\n")).toContain(CURE_MESSAGE);
  });
});
