/**
 * Parsing/comparison mechanism for oracle-state-tokens.test.ts (MANDATE-vo.md
 * "Slice C1b''", after vo-gate-c1c REWORK-BUILD on #6845 —
 * GATE-C1C-REPORT-6845.md OBS-C1c-1..6). Sibling helper, not `_lib/` (that
 * directory is frozen for design PRs — R19 map §4.5 — and this is unrelated
 * to it). Pure functions only, no new dependency.
 *
 * vo-gate-c1c found the signature/subset inheritance model (Slice C1b')
 * right IN SUBSTANCE but leaking through two textual shortcuts: a
 * multi-branch selector (`A, B`) was judged on its first alternative only
 * (`branchSignatures[0]`, called "out of scope" instead of failing loud —
 * OBS-C1c-1), and a regex read attributes out of raw branch text including
 * INSIDE `:not(...)`, so `:not([data-oracle-theme="dark"])` — the LIGHT
 * theme — was recorded as `data-oracle-theme = dark` (OBS-C1c-2). Both let a
 * real two-state collapse in the DEFAULT light theme ship green through two
 * selector shapes this file's own idiom already uses.
 *
 * THE RULE this module now enforces (U1, not a third shape-by-shape patch):
 * effective values are NEVER derived from a partially-read selector. Every
 * token of every selector branch for a state-bearing rule must be consumed
 * by an explicit, closed-world GRAMMAR (`SELECTOR_GRAMMAR` below) — anything
 * left over throws `unmodelled selector construct "<text>" in <identity>`,
 * naming the exact offending text, never a silent guess. A rule with N
 * comma-branches is N independent contexts (U2): each is parsed, keyed and
 * judged on its own signature, never on the first alternative. Attributes
 * are read ONLY from tokens the grammar has already classified as positive
 * constraints — never by a regex scanning raw text, which is how a negated
 * attribute got read as asserted.
 *
 * A rule with NO `--oracle-state-*` token never has its selector parsed at
 * all (the file has hundreds of unrelated `.oracle-root …` rules for
 * layout/typography using constructs — `:hover`, child combinators, other
 * at-rules — this grammar does not model; they are invisible to the fence
 * by design, exactly as before).
 *
 * Inheritance composes the FULL chain (U5): a subset override whose best
 * base is ITSELF a subset override walks further up, accumulating every
 * ancestor's own declared tokens, until every one of the eight is covered
 * or no further base can be found — at which point the thrown message
 * names the whole chain of identities walked, not just "missing token".
 *
 * Known limits, recorded not fixed:
 * - One level of `@media`/`@supports` nesting only (OBS-C1b-5); any other
 *   at-rule keyword, or two levels of nesting, is unmodelled and throws
 *   naming the construct — never silently mis-parsed. A leading statement
 *   at-rule (`@import "…";`, `@charset "…";`) is consumed as a no-op so the
 *   rule that follows it is still found (U6/OBS-C1c-4).
 * - "unsupported CSS construct at line N" names the line where the
 *   offending construct itself STARTS, not where the scanner last resumed
 *   (U7/OBS-C1c-5).
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
  /** selector, or `${at-rule} :: ${selector}` when wrapped in one — a
   * SINGLE comma-branch's own text (U2: N branches = N identities), never a
   * line number: a reformat that doesn't touch this branch's own text
   * leaves its identity, and this fence, unchanged. */
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

/** Offset of the first non-whitespace character in `s`, or `s.length` if
 * `s` is all whitespace — used to point line diagnostics at where a
 * construct actually STARTS, not at wherever the previous rule ended
 * (U7/OBS-C1c-5: blank lines and stripped comments between rules used to
 * shift the reported line number away from the real one). */
function firstNonWhitespaceOffset(s: string): number {
  const m = s.match(/^\s*/);
  return m ? m[0].length : 0;
}

/**
 * Splits comment-stripped CSS into leaf rule blocks (selector { decls }),
 * unwrapping one level of @-rule nesting (the only nesting this file uses —
 * a plain selector rule inside `@media`/`@supports`). A leading STATEMENT
 * at-rule (`@import "…";`, `@charset "…";`) is consumed as a no-op so the
 * rule that follows it is still found (U6/OBS-C1c-4 — it used to be
 * swallowed into a malformed "header" together with the next selector,
 * silently returning zero blocks instead of failing loud). Refuses, loudly
 * and naming the line the construct STARTS on (U7), anything deeper than
 * one level of at-rule nesting or a leaf whose body itself contains another
 * `{` — this parser accepts exactly one stylesheet shape (OBS-C1b-5) and
 * never silently mis-parses a different one.
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
      const semiIdx = segment.indexOf(";", i);
      const braceIdx = segment.indexOf("{", i);
      if (semiIdx !== -1 && (braceIdx === -1 || semiIdx < braceIdx)) {
        const stmtStart =
          i + firstNonWhitespaceOffset(segment.slice(i, semiIdx));
        const stmt = segment.slice(stmtStart, semiIdx).trim();
        if (/^@[\w-]+/.test(stmt)) {
          // A statement at-rule (`@import "…";`, `@charset "…";`) — no
          // body, consumed as a no-op; keep scanning for the next rule.
          i = semiIdx + 1;
          continue;
        }
        throw new Error(
          `unsupported CSS construct at line ${lineAt(offsetInOriginal + stmtStart)}: bare statement "${stmt}" (not a recognised at-rule statement)`,
        );
      }
      const openIdx = braceIdx;
      if (openIdx === -1) break;
      const headerStart =
        i + firstNonWhitespaceOffset(segment.slice(i, openIdx));
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
            `unsupported CSS construct at line ${lineAt(offsetInOriginal + headerStart)}: nested at-rule "${header}" inside ${atRule}`,
          );
        }
        blocks.push(...recurse(body, offsetInOriginal + openIdx + 1, header));
      } else {
        const nestedIdx = body.indexOf("{");
        if (nestedIdx !== -1) {
          throw new Error(
            `unsupported CSS construct at line ${lineAt(offsetInOriginal + openIdx + 1 + nestedIdx)}: nested rule inside selector ${header}`,
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

// ─── U1: THE CLOSED-WORLD SELECTOR GRAMMAR ─────────────────────────────────

/**
 * The closed-world selector grammar this fence models (MANDATE-vo.md Slice
 * C1b'' U1). Effective values are NEVER derived from a partially-read
 * selector: every token of every branch of a STATE-BEARING rule must be
 * consumed here, or the context is UNDERIVABLE and the fence throws
 * `unmodelled selector construct "<text>" in <identity>` naming the exact
 * offending text — never a silent guess. A rule declaring no
 * `--oracle-state-*` token never has its selector parsed at all.
 *
 * At-rule wrappers understood (one level of nesting, unchanged from B4/B5):
 * `@media`, `@supports`. Any other at-rule keyword — `@layer`,
 * `@container`, `@scope`, … — is unmodelled.
 *
 * Per selector branch (a comma-separated selector list is N INDEPENDENT
 * branches, U2 — never judged on the first alternative only), left to
 * right, any sequence of:
 *   - a TYPE selector (`html`)
 *   - a CLASS selector (`.oracle-root`)
 *   - `[name="value"]` — a valued attribute selector (positive: name=value)
 *   - `[name]` — a valueless attribute selector (positive: name present)
 *   - `:not([name])` — a VALUELESS negation ONLY; recognised and consumed,
 *     contributes NO positive constraint (a `:not([a="v"])` VALUED negation
 *     is unmodelled — reading an attribute's value out of a `:not()` as a
 *     positive assertion was OBS-C1c-2's exact defect)
 *   - the DESCENDANT combinator (one or more spaces) between two of the
 *     above
 *
 * NOT modelled — the fence throws on any of these: `:is()`, `:where()`,
 * `:has()`, any other pseudo-class or pseudo-element, a VALUED `:not()`,
 * `&` nesting, any at-rule keyword other than the two above, the
 * child/sibling combinators (`>`, `+`, `~`), and an attribute selector
 * using any operator other than `=` (`^=`, `$=`, `*=`, `~=`, `|=`).
 */
export const SELECTOR_GRAMMAR = Object.freeze({
  atRules: ["media", "supports"] as const,
  combinator: "descendant (whitespace) only",
  perBranchTokens: [
    "TYPE selector (e.g. html)",
    "CLASS selector (e.g. .oracle-root)",
    '[name="value"] (valued attribute, positive)',
    "[name] (valueless attribute, positive presence)",
    ":not([name]) (valueless negation only — consumed, contributes no positive constraint)",
  ] as const,
});

type Constraint = { kind: "eq"; value: string } | { kind: "present" };
type Signature = Map<string, Constraint>;

function signatureKey(sig: Signature): string {
  return [...sig.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, c]) => `${k}=${c.kind === "eq" ? c.value : "*"}`)
    .join("&");
}

/** `candidate` is a subset of (a provable generalisation implied by)
 * `target` when every constraint it declares also holds for `target`'s own
 * signature: an `eq` constraint needs the SAME value on both sides; a
 * `present` constraint is satisfied by target having EITHER `present` or a
 * concrete `eq` for that attribute (a concrete value implies presence). */
function isSubsetSignature(candidate: Signature, target: Signature): boolean {
  for (const [k, c] of candidate) {
    const t = target.get(k);
    if (!t) return false;
    if (c.kind === "eq" && (t.kind !== "eq" || t.value !== c.value)) {
      return false;
    }
  }
  return true;
}

/** `(feature: value)` media/supports-feature pairs from an @-rule prelude. */
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

const ALLOWED_AT_RULE_KEYWORDS = new Set<string>(SELECTOR_GRAMMAR.atRules);

/** Only called for a STATE-BEARING rule (U1's grammar governs what a
 * state-bearing rule's context may look like; a rule with no state token
 * never reaches here). */
function validateAtRuleKeyword(atRule: string | null, identity: string): void {
  if (atRule === null) return;
  const m = atRule.match(/^@([\w-]+)/);
  const keyword = m ? m[1].toLowerCase() : "";
  if (!ALLOWED_AT_RULE_KEYWORDS.has(keyword)) {
    throw new Error(`unmodelled selector construct "${atRule}" in ${identity}`);
  }
}

/** Splits a selector into its comma-separated branches (U2), ignoring a
 * comma nested inside `[...]`/`(...)` (none of this grammar's forms use
 * one, but a closed-world splitter should not be fooled by it either). */
function splitTopLevelCommas(selector: string): string[] {
  const parts: string[] = [];
  let current = "";
  let depth = 0;
  for (const ch of selector) {
    if (ch === "[" || ch === "(") depth++;
    else if (ch === "]" || ch === ")") depth--;
    if (ch === "," && depth === 0) {
      parts.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  parts.push(current);
  return parts.map((p) => normalizeWhitespace(p)).filter(Boolean);
}

/** Splits one branch into compound selectors on the DESCENDANT combinator
 * (whitespace at bracket/paren depth 0) — the only combinator this grammar
 * models. `>`, `+`, `~` at depth 0 (with or without surrounding whitespace)
 * are unmodelled and throw immediately, naming the combinator. */
function splitCompounds(branch: string, identity: string): string[] {
  const compounds: string[] = [];
  let current = "";
  let depth = 0;
  let i = 0;
  while (i < branch.length) {
    const ch = branch[i];
    if (ch === "[" || ch === "(") {
      depth++;
      current += ch;
      i++;
      continue;
    }
    if (ch === "]" || ch === ")") {
      depth--;
      current += ch;
      i++;
      continue;
    }
    if (depth === 0 && ">+~".includes(ch)) {
      throw new Error(`unmodelled selector construct "${ch}" in ${identity}`);
    }
    if (depth === 0 && /\s/.test(ch)) {
      if (current) {
        compounds.push(current);
        current = "";
      }
      while (i < branch.length && /\s/.test(branch[i])) i++;
      if (i < branch.length && depth === 0 && ">+~".includes(branch[i])) {
        throw new Error(
          `unmodelled selector construct "${branch[i]}" in ${identity}`,
        );
      }
      continue;
    }
    current += ch;
    i++;
  }
  if (current) compounds.push(current);
  return compounds;
}

const TYPE_RE = /^[A-Za-z][\w-]*/;
const CLASS_RE = /^\.[A-Za-z][\w-]*/;
const ATTR_EQ_RE = /^\[([\w-]+)="([^"]*)"\]/;
const ATTR_PRESENT_RE = /^\[([\w-]+)\]/;
const NOT_VALUELESS_RE = /^:not\(\[([\w-]+)\]\)/;

/** Captures a plausible chunk of the NEXT token for an error message even
 * though it doesn't match anything the grammar allows, so `unmodelled
 * selector construct` names the actual offending text, not a truncated
 * fragment or the whole remaining branch. */
function captureUnknownToken(text: string): string {
  if (text.startsWith("[")) {
    const end = text.indexOf("]");
    return end === -1 ? text : text.slice(0, end + 1);
  }
  if (text.startsWith(":")) {
    const m = text.match(/^:+[\w-]+(\([^)]*\))?/);
    return m ? m[0] : text.slice(0, 1);
  }
  if (text.startsWith("&")) return "&";
  const m = text.match(/^[^\s.[\]:]+/);
  return m && m[0] ? m[0] : text.slice(0, 1);
}

/**
 * Parses ONE compound selector (no combinator inside) into the positive
 * attribute constraints it asserts, accumulating into `sig`. Throws
 * `unmodelled selector construct` naming the first token the grammar (U1)
 * doesn't recognise — a VALUED `:not(…)`, `:is()`/`:where()`/`:has()`, `&`,
 * or any other pseudo-class/operator.
 */
function parseCompound(
  compound: string,
  identity: string,
  sig: Signature,
): void {
  let rest = compound;
  while (rest.length > 0) {
    let m: RegExpMatchArray | null;
    if ((m = rest.match(TYPE_RE))) {
      rest = rest.slice(m[0].length);
      continue;
    }
    if ((m = rest.match(CLASS_RE))) {
      rest = rest.slice(m[0].length);
      continue;
    }
    if ((m = rest.match(NOT_VALUELESS_RE))) {
      // Recognised and consumed — contributes NOTHING positive (U1;
      // OBS-C1c-2 was reading the negated attribute as if it were true).
      rest = rest.slice(m[0].length);
      continue;
    }
    if ((m = rest.match(ATTR_EQ_RE))) {
      sig.set(m[1], { kind: "eq", value: m[2] });
      rest = rest.slice(m[0].length);
      continue;
    }
    if ((m = rest.match(ATTR_PRESENT_RE))) {
      if (!sig.has(m[1])) sig.set(m[1], { kind: "present" });
      rest = rest.slice(m[0].length);
      continue;
    }
    throw new Error(
      `unmodelled selector construct "${captureUnknownToken(rest)}" in ${identity}`,
    );
  }
}

/** Computes one branch's full signature: its enclosing at-rule's
 * `(feature: value)` pairs, plus every positive attribute constraint its
 * own compound selectors assert (U1/U2). */
function branchSignature(
  branchText: string,
  atRule: string | null,
  identity: string,
): Signature {
  const sig: Signature = new Map(
    atRuleFeaturePairs(atRule).map(
      ([k, v]) => [k, { kind: "eq", value: v } as Constraint] as const,
    ),
  );
  for (const compound of splitCompounds(branchText, identity)) {
    parseCompound(compound, identity, sig);
  }
  return sig;
}

interface BranchContext {
  identity: string;
  customProps: Map<string, string>;
  signature: Signature;
}

/**
 * Flattens raw rules into one BranchContext PER COMMA-BRANCH (U2), in
 * document order. A rule that declares no `--oracle-state-*` token is
 * skipped BEFORE its selector is ever parsed — its selector need not be
 * (and, for the hundreds of unrelated layout/typography rules this file
 * has, is not) inside the closed-world grammar.
 */
function buildBranchContexts(raw: RawBlock[]): BranchContext[] {
  const contexts: BranchContext[] = [];
  for (const b of raw) {
    const customProps = extractCustomProps(b.declarations);
    if (!ALL_STATE_KEYS.some((key) => customProps.has(key))) continue;

    const ruleIdentity = b.atRule
      ? `${normalizeWhitespace(b.atRule)} :: ${b.selector}`
      : b.selector;
    validateAtRuleKeyword(b.atRule, ruleIdentity);

    for (const branchText of splitTopLevelCommas(b.selector)) {
      const identity = b.atRule
        ? `${normalizeWhitespace(b.atRule)} :: ${branchText}`
        : branchText;
      const signature = branchSignature(branchText, b.atRule, identity);
      contexts.push({ identity, customProps, signature });
    }
  }
  return contexts;
}

interface RankedCandidate {
  blockIndex: number;
  size: number;
  key: string;
}

/**
 * Finds the ONE base a partial-override context (index `index`) inherits
 * from: the preceding STATE-BEARING branch context whose signature is (a) a
 * SUBSET of the override's own signature and (b) the LARGEST such subset
 * (most specific — the closest real-CSS analogue of "the ancestor rule this
 * one actually overrides"). Two or more preceding contexts tying for the
 * largest size with DIFFERENT signatures means the base cannot be derived
 * with certainty — thrown, naming every tied candidate, rather than
 * guessed. Each branch of a multi-branch rule is its OWN independent
 * context here (U2) — there is no "best branch" selection left to make.
 */
function findInheritanceBase(
  contexts: BranchContext[],
  index: number,
): { customProps: Map<string, string>; index: number } | undefined {
  const target = contexts[index].signature;
  const ranked: RankedCandidate[] = [];
  for (let j = index - 1; j >= 0; j--) {
    if (!ALL_STATE_KEYS.some((key) => contexts[j].customProps.has(key))) {
      continue;
    }
    const sig = contexts[j].signature;
    if (isSubsetSignature(sig, target)) {
      ranked.push({ blockIndex: j, size: sig.size, key: signatureKey(sig) });
    }
  }
  if (ranked.length === 0) return undefined;

  const maxSize = Math.max(...ranked.map((r) => r.size));
  const top = ranked.filter((r) => r.size === maxSize);
  const distinctKeys = new Set(top.map((r) => r.key));
  if (distinctKeys.size > 1) {
    const names = top.map((r) => contexts[r.blockIndex].identity);
    throw new Error(
      `${contexts[index].identity}: cannot derive effective values with certainty — ` +
        `${top.length} equally specific but different contexts could be its base: ${names.join(" | ")}`,
    );
  }
  const nearest = top.reduce((a, b) => (a.blockIndex > b.blockIndex ? a : b));
  return {
    customProps: contexts[nearest.blockIndex].customProps,
    index: nearest.blockIndex,
  };
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
 * `var(--x)` indirection at a time through the given scopes (own context
 * first, then each provable inherited ancestor in order, if any — "resolved
 * within the SAME context then up the cascade the file defines"; a fallback
 * argument is itself resolved the same way). An unresolvable reference — no
 * matching custom property in any scope, and no fallback — throws naming
 * the token; it is never treated as distinct by default.
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
 * Finds every branch context that declares ANY of the eight
 * `--oracle-state-*` tokens (B2 — not just the four that declare all eight)
 * and returns its EFFECTIVE, colour-normalised values (B1), with identity
 * keyed by selector-branch/at-rule (B3/U2), after stripping CSS comments
 * (B4). A context that declares only a subset inherits the rest by
 * COMPOSING THE FULL CHAIN (U5) of provable generalisations of its own
 * context — never from a context merely sharing a substring of its
 * selector, and never stopping at the first partial ancestor. Throws
 * loudly, naming the context and either the missing token (with the whole
 * chain walked, if more than one hop) or the ambiguous candidates, if fewer
 * than four effective foreground or background values can be derived with
 * certainty for a context (B5 — the blind-scan floor).
 */
export function parseEffectiveBlocks(css: string): EffectiveBlock[] {
  const raw = splitBlocks(stripComments(css));
  const contexts = buildBranchContexts(raw);

  const effective: EffectiveBlock[] = [];
  contexts.forEach((ctx, index) => {
    if (!ALL_STATE_KEYS.some((key) => ctx.customProps.has(key))) return;

    const scopes: Map<string, string>[] = [ctx.customProps];
    const chainIdentities: string[] = [ctx.identity];
    const coveredKeys = new Set(
      ALL_STATE_KEYS.filter((k) => ctx.customProps.has(k)),
    );
    let current = index;
    while (coveredKeys.size < ALL_STATE_KEYS.length) {
      const base = findInheritanceBase(contexts, current);
      if (!base) break;
      scopes.push(base.customProps);
      chainIdentities.push(contexts[base.index].identity);
      for (const k of ALL_STATE_KEYS) {
        if (base.customProps.has(k)) coveredKeys.add(k);
      }
      current = base.index;
    }

    const lookup = (key: string): string | undefined => {
      for (const scope of scopes) {
        const v = scope.get(key);
        if (v !== undefined) return v;
      }
      return undefined;
    };

    // Every state-bearing context is evaluated independently, earliest
    // first (U5): if a context's whole reachable chain still cannot cover
    // a token, the SHALLOWEST broken ancestor along that chain always
    // throws its OWN (necessarily length-1) message first — this format's
    // multi-identity branch documents what the message becomes for a
    // context reached only through a longer, still-unresolved walk.
    const missingMessage = (key: string): string =>
      chainIdentities.length > 1
        ? `${ctx.identity}: missing ${key} — chain search of [${chainIdentities.join(" -> ")}] found no provable base for it`
        : `${ctx.identity}: missing ${key} (not declared here or in a provable inherited base)`;

    const fgRaw = buildStateValues((name) => {
      const value = lookup(FG_KEYS[name]);
      if (value === undefined) throw new Error(missingMessage(FG_KEYS[name]));
      return value;
    });
    const fg = buildStateValues((name) =>
      resolveValue(fgRaw[name], scopes, `${ctx.identity} foreground`),
    );
    const bg = buildStateValues((name) => {
      const value = lookup(BG_KEYS[name]);
      if (value === undefined) throw new Error(missingMessage(BG_KEYS[name]));
      return resolveValue(value, scopes, `${ctx.identity} background`);
    });

    effective.push({ identity: ctx.identity, fg, bg, fgRaw });
  });
  return effective;
}
