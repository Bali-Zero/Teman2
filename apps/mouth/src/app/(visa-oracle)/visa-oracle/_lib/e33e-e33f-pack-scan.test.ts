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

const NAMED_E33E_ELIGIBILITY_RULES = new Set([
  "el.e33e.retirement",
  "el.e33e.age-55-59-disputed-band",
]);

type PackRuleEffect = {
  type: string;
  reason_code?: string;
  covered_purposes?: string[];
};

type PackRule = {
  rule_id: string;
  scope: string;
  product_version_ids?: string[] | null;
  effect?: PackRuleEffect;
  stage?: string;
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
};

type ScanFacts = {
  e33eOnlyRuleIds: string[];
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
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableJson(record[key])}`);
  return `{${entries.join(",")}}`;
}

function flattenAndLeaves(node: unknown): Record<string, unknown>[] {
  if (!isRecord(node)) return [];
  if (node.op === "all" && Array.isArray(node.args)) {
    return node.args.flatMap((arg) => flattenAndLeaves(arg));
  }
  return [node];
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
    stableJson(facts.e33eOnlyRuleIds) !== stableJson(EXPECTED_E33E_ONLY_RULES)
  ) {
    out.push(
      problem(
        `expected E33E-only rules ${EXPECTED_E33E_ONLY_RULES.join(", ")}, got ${facts.e33eOnlyRuleIds.join(", ")}`,
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

  if (facts.retirementDelta.missingE33fLeaves.length > 0) {
    out.push(
      problem(
        `el.e33e.retirement is missing el.e33f.retirement leaves: ${stableJson(facts.retirementDelta.missingE33fLeaves)}`,
      ),
    );
  }

  if (facts.retirementDelta.unexpectedLeaves.length > 0) {
    out.push(
      problem(
        `el.e33e.retirement has unexpected extra leaves: ${stableJson(facts.retirementDelta.unexpectedLeaves)}`,
      ),
    );
  }

  if (
    stableJson(facts.retirementDelta.ageLeaf) !==
    stableJson({ fact: "derived.age_years", op: "gte", value: 55 })
  ) {
    out.push(
      problem(
        `el.e33e.retirement age leaf is ${stableJson(facts.retirementDelta.ageLeaf)}`,
      ),
    );
  }

  if (!facts.retirementDelta.depositLeaf) {
    out.push(
      problem("el.e33e.retirement is missing secondhome.bank_deposit_usd gte"),
    );
  }

  if (
    stableJson(facts.retirementDelta.stateBankLeaf) !==
    stableJson({
      fact: "secondhome.bank_deposit_at_state_bank",
      op: "eq",
      value: true,
    })
  ) {
    out.push(
      problem(
        `el.e33e.retirement state-bank leaf is ${stableJson(facts.retirementDelta.stateBankLeaf)}`,
      ),
    );
  }

  if (
    stableJson(facts.retirementDelta.ownNameLeaf) !==
    stableJson({
      fact: "secondhome.bank_deposit_in_own_name",
      op: "eq",
      value: true,
    })
  ) {
    out.push(
      problem(
        `el.e33e.retirement own-name leaf is ${stableJson(facts.retirementDelta.ownNameLeaf)}`,
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
  const e33eOnlyExcludes: string[] = [];

  for (const rule of e33eOnlyRules) {
    const isNamedEligibility = NAMED_E33E_ELIGIBILITY_RULES.has(rule.rule_id);
    const twinId = rule.rule_id.includes("e33e")
      ? rule.rule_id.replace("e33e", "e33f")
      : null;
    const twin = twinId
      ? e33fOnlyRules.find((candidate) => candidate.rule_id === twinId)
      : undefined;
    const hasIdenticalTwin =
      Boolean(twin) &&
      twin?.effect?.type === rule.effect?.type &&
      stableJson(twin?.when) === stableJson(rule.when);

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
  e33eOnlyExcludes.sort();

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

  const e33eLeaves = flattenAndLeaves(e33eRetirement?.when);
  const e33fLeaves = flattenAndLeaves(e33fRetirement?.when);
  const e33eLeafSet = new Set(e33eLeaves.map((leaf) => stableJson(leaf)));
  const e33fLeafSet = new Set(e33fLeaves.map((leaf) => stableJson(leaf)));

  const missingE33fLeaves = e33fLeaves.filter(
    (leaf) => !e33eLeafSet.has(stableJson(leaf)),
  );
  const e33eOnlyLeaves = e33eLeaves.filter(
    (leaf) => !e33fLeafSet.has(stableJson(leaf)),
  );

  const ageLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "derived.age_years",
  );
  const depositLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "secondhome.bank_deposit_usd" && leaf.op === "gte",
  );
  const stateBankLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "secondhome.bank_deposit_at_state_bank",
  );
  const ownNameLeaf = e33eOnlyLeaves.find(
    (leaf) => leaf.fact === "secondhome.bank_deposit_in_own_name",
  );

  const expectedExtraFacts = new Set([
    "derived.age_years",
    "secondhome.bank_deposit_usd",
    "secondhome.bank_deposit_at_state_bank",
    "secondhome.bank_deposit_in_own_name",
  ]);
  const unexpectedLeaves = e33eOnlyLeaves.filter(
    (leaf) =>
      typeof leaf.fact !== "string" || !expectedExtraFacts.has(leaf.fact),
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

  const globalRuleCount = payload.rules.filter(
    (rule) => rule.scope === "GLOBAL",
  ).length;

  const baseFacts: Omit<ScanFacts, "problems"> = {
    e33eOnlyRuleIds,
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

function mutateDepositThreshold(node: unknown, value: number): boolean {
  if (!isRecord(node)) return false;
  if (
    node.fact === "secondhome.bank_deposit_usd" &&
    node.op === "gte" &&
    typeof node.value === "number"
  ) {
    node.value = value;
    return true;
  }
  if (Array.isArray(node.args)) {
    return node.args.some((arg) => mutateDepositThreshold(arg, value));
  }
  return false;
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
    expect(scan.problems).toEqual([]);
    expect(scan.e33eOnlyRuleIds).toEqual(EXPECTED_E33E_ONLY_RULES);
    expect(scan.twinMismatches).toEqual([]);
  });

  it("the E33E-only rules are exactly the hard filters with identical twins plus el.e33e.retirement and the disputed-band rule", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.e33eOnlyRuleIds).toEqual([
      "el.e33e.age-55-59-disputed-band",
      "el.e33e.retirement",
      "hf.e33e.age-below-55",
      "hf.e33e.retirement-income-below-minimum",
    ]);
    expect(scan.twinsChecked).toEqual([
      "hf.e33e.age-below-55",
      "hf.e33e.retirement-income-below-minimum",
    ]);
    expect(scan.twinMismatches).toEqual([]);
    expect(scan.e33eOnlyExcludes).toEqual([]);
  });

  it("el.e33e.retirement is the E33F rule plus age 55 or more plus the deposit trio", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.retirementDelta.missingE33fLeaves).toEqual([]);
    expect(scan.retirementDelta.unexpectedLeaves).toEqual([]);
    expect(scan.retirementDelta.ageLeaf).toEqual({
      fact: "derived.age_years",
      op: "gte",
      value: 55,
    });
    expect(scan.retirementDelta.depositLeaf).toEqual({
      fact: "secondhome.bank_deposit_usd",
      op: "gte",
      value: E33E_DEPOSIT_THRESHOLD_USD,
    });
    expect(scan.retirementDelta.stateBankLeaf).toEqual({
      fact: "secondhome.bank_deposit_at_state_bank",
      op: "eq",
      value: true,
    });
    expect(scan.retirementDelta.ownNameLeaf).toEqual({
      fact: "secondhome.bank_deposit_in_own_name",
      op: "eq",
      value: true,
    });
  });

  it("the disputed-band rule never excludes and itself requires the deposit trio", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.disputedBandExcludes).toBe(false);
    expect(scan.disputedBandEffectType).toBe("SUPPORT");
    expect(scan.disputedBandHasDepositTrio).toBe(true);
  });

  it("no rule targets both E33E and E33F", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    expect(scan.bothProductRules).toEqual([]);
  });

  it("the note's EN and ID figures equal the pack's deposit threshold", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    const threshold = Number(scan.depositThreshold);
    const note = SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE;
    expect(threshold).toBe(E33E_DEPOSIT_THRESHOLD_USD);
    expect(note.en).toContain("50,000");
    expect(note.id).toContain("50.000");
    expect(note.en).toContain(new Intl.NumberFormat("en-US").format(threshold));
    expect(note.id).toContain(new Intl.NumberFormat("id-ID").format(threshold));
  });

  it("the note names the state-owned bank and the own-name condition in EN and ID", () => {
    const scan = scanE33eVsE33f(newestSignedPack());
    const note = SUPPORT_REASON_COPY.E33F_E33E_DEPOSIT_NOTE;
    expect(scan.retirementDelta.stateBankLeaf).toBeDefined();
    expect(scan.retirementDelta.ownNameLeaf).toBeDefined();
    expect(note.en).toMatch(/state-owned bank/);
    expect(note.en).toMatch(/your own name/);
    expect(note.id).toMatch(/bank milik negara/);
    expect(note.id).toMatch(/atas nama Anda sendiri/);
  });

  // Guilt probes: mutate a clone of the newest signed pack in memory (locating
  // targets by rule_id / product_code) to prove the scan fails with the cure
  // message when any invariant separating E33E from E33F drifts.

  it("guilt: a changed deposit threshold fails the scan", () => {
    const pack = structuredClone(newestSignedPack());
    const rule = pack.rules.find((r) => r.rule_id === "el.e33e.retirement");
    if (!rule) throw new Error("el.e33e.retirement missing");
    expect(mutateDepositThreshold(rule.when, 60000)).toBe(true);
    const scan = scanE33eVsE33f(pack, E33E_DEPOSIT_THRESHOLD_USD);
    expect(scan.problems.length).toBeGreaterThan(0);
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
