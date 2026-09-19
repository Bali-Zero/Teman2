/**
 * Parsing/comparison mechanism for oracle-state-tokens.test.ts (MANDATE-vo.md
 * "Slice C1b'", after vo-gate-c1b REWORK-BUILD on #6833 —
 * GATE-C1B-REPORT-6833.md OBS-C1b-1..6). Sibling helper, not `_lib/` (that
 * directory is frozen for design PRs — R19 map §4.5 — and this is unrelated
 * to it). Pure functions only, no new dependency.
 *
 * vo-gate-c1b found the fence's colour-normalisation (B1) and block-identity
 * (B3/B4/B5) work correct, but its inheritance model (B2) wrong on the
 * shipped file: it keyed a block's "theme" off the FIRST
 * `data-oracle-theme="…"` STRING in its selector, so the two pre-hydration
 * blocks (`oracle.css:114`, `:143`) — which declare DARK values under a
 * selector that also happens to say `data-oracle-theme="light"` — keyed as
 * "light" and became the (wrong) inheritance base for any new light-theme
 * override. A real two-state collapse in the DEFAULT light theme shipped
 * green (D3b); its innocent mirror shipped red (D4).
 *
 * This module replaces theme-string keying with a SIGNATURE model: a
 * block's signature is the set of {attribute: value} constraints its full
 * context (selector attribute selectors + any enclosing @-rule's media
 * features) actually imposes. A context B may inherit from a preceding
 * block A only if signature(A) is a SUBSET of signature(B) — A's context is
 * a provable generalisation of B's, exactly like an ancestor rule with
 * equal-or-lower specificity in real CSS. Among all valid bases, the one
 * with the LARGEST (most specific) signature wins; if two or more tie at
 * the largest size with DIFFERENT signatures, the choice is genuinely
 * ambiguous and the fence fails LOUD naming both candidates rather than
 * guessing. Candidate bases are drawn ONLY from preceding blocks that
 * declare at least one `--oracle-state-*` token themselves — the file has
 * hundreds of unrelated `.oracle-root …` rules for layout/typography, and a
 * rule with no state tokens has nothing to contribute to the chain even
 * when its signature would otherwise qualify (caught while curing D3b: the
 * naive nearest-empty-signature match latched onto an unrelated component
 * rule and reported every token as missing).
 *
 * Known limit (OBS-C1b-5, recorded, not fixed here): this is a hand-rolled
 * parser for exactly this file's shape — one level of `@media` nesting, no
 * CSS nesting syntax, no `@supports`. A stylesheet shaped differently fails
 * loud, naming the construct and the line, rather than silently
 * mis-parsing.
 */

const STATE_NAMES = [
  "eligible",
  "likely",
  "conditional",
  "likely-not",
] as const;
type StateName = (typeof STATE_NAMES)[number];
export type StateValues = Record<StateName, string>;

interface EffectiveBlock {
  /** selector, or `${at-rule} :: ${selector}` when wrapped in one — never a
   * line number: a reformat that doesn't touch this block's own text leaves
   * its identity, and this fence, unchanged. */
  identity: string;
  /** normalised (comparison) values. */
  fg: StateValues;
  bg: StateValues;
  /** values exactly as declared in THIS block, unresolved/unnormalised —
   * used only to pin the shipped baseline verbatim. */
  fgRaw: StateValues;
}

const FG_KEYS: Record<StateName, string> = {
  eligible: "--oracle-state-eligible",
  likely: "--oracle-state-likely",
  conditional: "--oracle-state-conditional",
  "likely-not": "--oracle-state-likely-not",
};
const BG_KEYS: Record<StateName, string> = {
  eligible: "--oracle-state-eligible-bg",
  likely: "--oracle-state-likely-bg",
  conditional: "--oracle-state-conditional-bg",
  "likely-not": "--oracle-state-likely-not-bg",
};
const ALL_STATE_KEYS: string[] = [
  ...Object.values(FG_KEYS),
  ...Object.values(BG_KEYS),
];

/** Throws naming both tokens the moment two of them resolve to the same
 * (normalised) value. */
export function assertDistinct(values: StateValues, label: string): void {
  const seenBy = new Map<string, StateName>();
  for (const name of STATE_NAMES) {
    const value = values[name];
    const priorName = seenBy.get(value);
    if (priorName) {
      throw new Error(
        `${label}: --oracle-state-${priorName} and --oracle-state-${name} both resolve to ${value}`,
      );
    }
    seenBy.set(value, name);
  }
}

// ─── B4: comment-aware extraction ──────────────────────────────────────────

/** Removes comment TEXT but keeps every newline inside it, so offsets taken
 * against the result still line up with the ORIGINAL file's line numbers
 * (used for the "unsupported CSS construct at line N" diagnostics). */
function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ""));
}

// ─── Structural split: leaf rule blocks, one level of @-rule nesting only ──

interface RawBlock {
  atRule: string | null;
  selector: string;
  declarations: string;
}

function normalizeWhitespace(s: string): string {
  return s.replace(/\s+/g, " ").trim();
}

function findMatchingBrace(css: string, openIdx: number): number {
  let depth = 0;
  for (let j = openIdx; j < css.length; j++) {
    if (css[j] === "{") depth++;
    else if (css[j] === "}") {
      depth--;
      if (depth === 0) return j;
    }
  }
  throw new Error(`unbalanced braces starting at offset ${openIdx}`);
}

/**
 * Splits comment-stripped CSS into leaf rule blocks (selector { decls }),
 * unwrapping one level of @-rule nesting (the only nesting this file uses —
 * a plain selector rule inside `@media`). Refuses, loudly and naming the
 * ORIGINAL file's line number, anything deeper or a leaf whose body itself
 * contains another `{` — this parser accepts exactly one stylesheet shape
 * (OBS-C1b-5) and never silently mis-parses a different one.
 */
function splitBlocks(css: string): RawBlock[] {
  const lineAt = (offset: number) => css.slice(0, offset).split("\n").length;

  function recurse(
    segment: string,
    offsetInOriginal: number,
    atRule: string | null,
  ): RawBlock[] {
    const blocks: RawBlock[] = [];
    let i = 0;
    while (i < segment.length) {
      const openIdx = segment.indexOf("{", i);
      if (openIdx === -1) break;
      const header = segment.slice(i, openIdx).trim();
      const closeIdx = findMatchingBrace(segment, openIdx);
      const body = segment.slice(openIdx + 1, closeIdx);
      if (!header) {
        i = closeIdx + 1;
        continue;
      }
      if (header.startsWith("@")) {
        if (atRule !== null) {
          throw new Error(
            `unsupported CSS construct at line ${lineAt(offsetInOriginal + i)}: nested at-rule "${header}" inside ${atRule}`,
          );
        }
        blocks.push(...recurse(body, offsetInOriginal + openIdx + 1, header));
      } else {
        if (body.includes("{")) {
          throw new Error(
            `unsupported CSS construct at line ${lineAt(offsetInOriginal + i)}: nested rule inside selector ${header}`,
          );
        }
        blocks.push({
          atRule,
          selector: normalizeWhitespace(header),
          declarations: body,
        });
      }
      i = closeIdx + 1;
    }
    return blocks;
  }

  return recurse(css, 0, null);
}

function extractCustomProps(declarations: string): Map<string, string> {
  const props = new Map<string, string>();
  // CSS allows the LAST declaration in a block to omit its trailing `;`
  // (it's still a legal declaration, terminated by the block's `}` instead,
  // which `declarations` has already had stripped) — the terminator is
  // `;` OR end of string, never just `;`.
  const re = /(--[\w-]+)\s*:\s*([^;]+?)(?:;|$)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(declarations)) !== null) {
    props.set(m[1], m[2].trim());
  }
  return props;
}

// ─── B2 / Q1: judge every context on its EFFECTIVE values, inheriting only
// from a PROVABLE generalisation of its own context ─────────────────────────

type Signature = Map<string, string>;

/** `[name="value"]` attribute selectors anywhere in the text — a boolean
 * attribute like `:not([data-oracle-theme-ready])` carries no value and is
 * not a theme signal, so it's deliberately not captured. */
function attrPairs(text: string): [string, string][] {
  const pairs: [string, string][] = [];
  const re = /\[([\w-]+)="([^"]+)"\]/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) pairs.push([m[1], m[2]]);
  return pairs;
}

/** `(feature: value)` media-feature pairs from an @-rule prelude. */
function atRuleFeaturePairs(atRule: string | null): [string, string][] {
  if (!atRule) return [];
  const pairs: [string, string][] = [];
  const re = /\(\s*([\w-]+)\s*:\s*([^)]+?)\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(atRule)) !== null) {
    pairs.push([m[1].trim(), m[2].trim()]);
  }
  return pairs;
}

function selectorBranches(selector: string): string[] {
  return selector
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function signatureKey(sig: Signature): string {
  return [...sig.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join("&");
}

/**
 * One signature per comma-separated selector alternative (a rule with a
 * selector list `A, B` matches whatever A matches OR whatever B matches —
 * each alternative needs its own signature for the subset check below, so
 * a rule with a bare, unconstrained alternative — like `.oracle-root, ` in
 * this file's light block — can validly generalise ANY context).
 */
function branchSignatures(block: {
  atRule: string | null;
  selector: string;
}): Signature[] {
  const atPairs = atRuleFeaturePairs(block.atRule);
  return selectorBranches(block.selector).map((branch) => {
    const sig: Signature = new Map(atPairs);
    for (const [k, v] of attrPairs(branch)) sig.set(k, v);
    return sig;
  });
}

function isSubsetSignature(candidate: Signature, target: Signature): boolean {
  for (const [k, v] of candidate) {
    if (target.get(k) !== v) return false;
  }
  return true;
}

interface ParsedBlock {
  identity: string;
  customProps: Map<string, string>;
  branchSignatures: Signature[];
}

interface RankedCandidate {
  blockIndex: number;
  size: number;
  key: string;
}

/**
 * Finds the base a partial-override block (index `index`) inherits from: the
 * preceding STATE-BEARING block (one that declares at least one
 * `--oracle-state-*` token — an unrelated rule that merely happens to share
 * a selector shape has no state props to contribute and is never a
 * candidate) whose best qualifying branch signature is (a) a SUBSET of the
 * override's own signature and (b) the LARGEST such subset (most specific —
 * the closest real-CSS analogue of "the ancestor rule this one actually
 * overrides"). Two or more preceding blocks tying for the largest size with
 * DIFFERENT signatures means the base cannot be derived with certainty —
 * thrown, naming every tied candidate, rather than guessed.
 */
function findInheritanceBase(
  blocks: ParsedBlock[],
  index: number,
): Map<string, string> | undefined {
  // An override's own matching signature is its first selector alternative.
  // A multi-branch override (a comma-separated override selector) is a
  // shape this file's actual overrides never use; out of scope.
  const target = blocks[index].branchSignatures[0] ?? new Map();

  const ranked: RankedCandidate[] = [];
  for (let j = index - 1; j >= 0; j--) {
    if (!ALL_STATE_KEYS.some((key) => blocks[j].customProps.has(key))) {
      continue;
    }
    let best: Signature | null = null;
    for (const sig of blocks[j].branchSignatures) {
      if (isSubsetSignature(sig, target)) {
        if (best === null || sig.size > best.size) best = sig;
      }
    }
    if (best) {
      ranked.push({ blockIndex: j, size: best.size, key: signatureKey(best) });
    }
  }
  if (ranked.length === 0) return undefined;

  const maxSize = Math.max(...ranked.map((r) => r.size));
  const top = ranked.filter((r) => r.size === maxSize);
  const distinctKeys = new Set(top.map((r) => r.key));
  if (distinctKeys.size > 1) {
    const names = top.map((r) => blocks[r.blockIndex].identity);
    throw new Error(
      `${blocks[index].identity}: cannot derive effective values with certainty — ` +
        `${top.length} equally specific but different contexts could be its base: ${names.join(" | ")}`,
    );
  }
  // All top candidates share one signature (equal specificity) — nearest
  // preceding wins, exactly as CSS breaks a specificity tie by document
  // order.
  const nearest = top.reduce((a, b) => (a.blockIndex > b.blockIndex ? a : b));
  return blocks[nearest.blockIndex].customProps;
}

// ─── B1 / Q4: compare resolved, CLAMPED colour VALUES ──────────────────────

function expandShorthand(digits: string): string {
  // 3- or 4-digit hex shorthand: each character is one channel, doubled.
  return digits.length <= 4
    ? digits
        .split("")
        .map((c) => c + c)
        .join("")
    : digits;
}

function clampChannel(n: number): number {
  return Math.min(255, Math.max(0, Math.round(n)));
}

function clampAlpha(n: number): number {
  // Fixed precision so `1`, `1.0` and `100%` all collapse to the same
  // string; clamped to [0, 1] the way a browser treats alpha > 1 as opaque.
  return Number(Math.min(1, Math.max(0, n)).toFixed(4));
}

function formatRgba(r: number, g: number, b: number, a: number): string {
  return `rgba(${clampChannel(r)}, ${clampChannel(g)}, ${clampChannel(b)}, ${clampAlpha(a)})`;
}

/**
 * Parses a `#hex` or `rgb()`/`rgba()` colour literal (comma or space
 * syntax, either alpha form) into a canonical `rgba(r, g, b, a)` string, so
 * two different NOTATIONS of the same colour compare equal while two
 * genuinely different colours still compare different — including
 * out-of-gamut channels and alpha > 1, which a browser clamps the same way
 * (`rgb(300, 0, 0)` renders identically to `#ff0000`). Throws naming the raw
 * input on any other notation — never silently treated as distinct or
 * equal.
 */
function normalizeColor(raw: string): string {
  const value = raw.trim();

  const hexMatch = value.match(
    /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/,
  );
  if (hexMatch) {
    const full = expandShorthand(hexMatch[1].toLowerCase());
    const r = parseInt(full.slice(0, 2), 16);
    const g = parseInt(full.slice(2, 4), 16);
    const b = parseInt(full.slice(4, 6), 16);
    const a = full.length === 8 ? parseInt(full.slice(6, 8), 16) / 255 : 1;
    return formatRgba(r, g, b, a);
  }

  const rgbMatch = value.match(/^rgba?\(\s*([^)]+?)\s*\)$/i);
  if (rgbMatch) {
    // Unify comma syntax and modern space syntax (with an optional `/
    // alpha`) into one whitespace-separated token list.
    const tokens = rgbMatch[1]
      .replace(/[,/]/g, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (tokens.length !== 3 && tokens.length !== 4) {
      throw new Error(`unrecognised rgb()/rgba() colour: ${raw}`);
    }
    const [r, g, b] = tokens.slice(0, 3).map(Number);
    const alphaToken = tokens[3];
    const a =
      alphaToken === undefined
        ? 1
        : alphaToken.endsWith("%")
          ? Number(alphaToken.slice(0, -1)) / 100
          : Number(alphaToken);
    if ([r, g, b, a].some((n) => Number.isNaN(n))) {
      throw new Error(`unrecognised rgb()/rgba() colour: ${raw}`);
    }
    return formatRgba(r, g, b, a);
  }

  throw new Error(
    `unrecognised colour notation (not #hex or rgb()/rgba()): ${raw}`,
  );
}

const VAR_RE = /^var\(\s*(--[\w-]+)\s*(?:,\s*([\s\S]+))?\)$/;

/**
 * Resolves a declared value to a canonical colour string, following one
 * `var(--x)` indirection at a time through the given scopes (own block
 * first, then its provable inherited base, if any — "resolved within the
 * SAME block then up the cascade the file defines"; a fallback argument is
 * itself resolved the same way). An unresolvable reference — no matching
 * custom property in either scope, and no fallback — throws naming the
 * token; it is never treated as distinct by default.
 */
function resolveValue(
  raw: string,
  scopes: Map<string, string>[],
  label: string,
  depth = 0,
): string {
  const trimmed = raw.trim();
  const varMatch = trimmed.match(VAR_RE);
  if (!varMatch) {
    return normalizeColor(trimmed);
  }
  if (depth > 10) {
    throw new Error(`${label}: var() reference cycle resolving ${raw}`);
  }
  const [, refName, fallback] = varMatch;
  for (const scope of scopes) {
    const refValue = scope.get(refName);
    if (refValue !== undefined) {
      return resolveValue(refValue, scopes, label, depth + 1);
    }
  }
  if (fallback !== undefined) {
    return resolveValue(fallback, scopes, label, depth + 1);
  }
  throw new Error(
    `${label}: --oracle-state token references undefined custom property ${refName} with no fallback`,
  );
}

function buildStateValues(compute: (name: StateName) => string): StateValues {
  const result: Partial<StateValues> = {};
  for (const name of STATE_NAMES) {
    result[name] = compute(name);
  }
  return result as StateValues;
}

/**
 * Finds every context that declares ANY of the eight `--oracle-state-*`
 * tokens (B2 — not just the four that declare all eight) and returns its
 * EFFECTIVE, colour-normalised values (B1), with block identity keyed by
 * selector/at-rule (B3), after stripping CSS comments (B4). A context that
 * declares only a subset inherits the rest from the nearest preceding block
 * PROVABLY generalising its own context (Q1) — never from a block merely
 * sharing a substring of its selector. Throws loudly, naming the block and
 * either the missing token or the ambiguous candidates, if fewer than four
 * effective foreground or background values can be derived with certainty
 * for a context (B5 — the blind-scan floor).
 */
export function parseEffectiveBlocks(css: string): EffectiveBlock[] {
  const raw = splitBlocks(stripComments(css));

  const blocks: ParsedBlock[] = raw.map((b) => ({
    identity: b.atRule
      ? `${normalizeWhitespace(b.atRule)} :: ${b.selector}`
      : b.selector,
    customProps: extractCustomProps(b.declarations),
    branchSignatures: branchSignatures(b),
  }));

  const effective: EffectiveBlock[] = [];
  blocks.forEach((block, index) => {
    if (!ALL_STATE_KEYS.some((key) => block.customProps.has(key))) return;

    const ownCount = ALL_STATE_KEYS.filter((k) =>
      block.customProps.has(k),
    ).length;
    const inherited =
      ownCount < ALL_STATE_KEYS.length
        ? findInheritanceBase(blocks, index)
        : undefined;
    const scopes = inherited
      ? [block.customProps, inherited]
      : [block.customProps];

    const lookup = (key: string): string | undefined => {
      for (const scope of scopes) {
        const v = scope.get(key);
        if (v !== undefined) return v;
      }
      return undefined;
    };

    const fgRaw = buildStateValues((name) => {
      const value = lookup(FG_KEYS[name]);
      if (value === undefined) {
        throw new Error(
          `${block.identity}: missing ${FG_KEYS[name]} (not declared here or in a provable inherited base)`,
        );
      }
      return value;
    });
    const fg = buildStateValues((name) =>
      resolveValue(fgRaw[name], scopes, `${block.identity} foreground`),
    );
    const bg = buildStateValues((name) => {
      const value = lookup(BG_KEYS[name]);
      if (value === undefined) {
        throw new Error(
          `${block.identity}: missing ${BG_KEYS[name]} (not declared here or in a provable inherited base)`,
        );
      }
      return resolveValue(value, scopes, `${block.identity} background`);
    });

    effective.push({ identity: block.identity, fg, bg, fgRaw });
  });
  return effective;
}
