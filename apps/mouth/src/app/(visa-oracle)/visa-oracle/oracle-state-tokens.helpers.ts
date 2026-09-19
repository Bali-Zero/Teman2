/**
 * Parsing/comparison mechanism for oracle-state-tokens.test.ts (MANDATE-vo.md
 * "Slice C1b", after vo-gate-c1 PASS on #6820 — GATE-C1-REPORT-6820.md OBS-1,
 * OBS-2, OBS-5, OBS-6). Sibling helper, not `_lib/` (that directory is frozen
 * for design PRs — R19 map §4.5 — and this is unrelated to it). Pure
 * functions only, no new dependency.
 *
 * The gate found the C1 fence real but bounded: it compared raw declaration
 * TEXT (so `#4ADE80` vs `#4ade80` passed green — OBS-1), it found blocks by
 * anchoring on one token so a context overriding only a SUBSET was invisible
 * (OBS-2), it pinned block identity by absolute line number (OBS-5), and its
 * regex had no comment awareness (OBS-6). This module fixes all four:
 * colours are parsed into a canonical form before comparison, blocks are
 * found by declaring ANY of the eight tokens and judged on their EFFECTIVE
 * values (own declarations layered over the nearest preceding same-theme
 * block), block identity is the selector (+ enclosing at-rule), and CSS
 * comments are stripped before anything is read.
 */

export const STATE_NAMES = [
  "eligible",
  "likely",
  "conditional",
  "likely-not",
] as const;
export type StateName = (typeof STATE_NAMES)[number];
export type StateValues = Record<StateName, string>;

export interface EffectiveBlock {
  /** selector, or `${at-rule} :: ${selector}` when wrapped in one — never a
   * line number (OBS-5): a reformat that doesn't touch this block's own text
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

function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
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
 * a plain selector rule inside `@media`). Refuses, loudly, anything deeper
 * or a leaf whose body itself contains another `{` — never silently
 * mis-parsed (blind-scan floor, B5).
 */
function splitBlocks(css: string, atRule: string | null = null): RawBlock[] {
  const blocks: RawBlock[] = [];
  let i = 0;
  while (i < css.length) {
    const openIdx = css.indexOf("{", i);
    if (openIdx === -1) break;
    const header = css.slice(i, openIdx).trim();
    const closeIdx = findMatchingBrace(css, openIdx);
    const body = css.slice(openIdx + 1, closeIdx);
    if (!header) {
      i = closeIdx + 1;
      continue;
    }
    if (header.startsWith("@")) {
      if (atRule !== null) {
        throw new Error(
          `unsupported nested at-rule inside ${atRule}: ${header}`,
        );
      }
      blocks.push(...splitBlocks(body, header));
    } else {
      if (body.includes("{")) {
        throw new Error(`unsupported nested rule inside selector ${header}`);
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

/** The `data-oracle-theme` value a selector targets, or `"light"` — this
 * file's default when the attribute is absent (bare `.oracle-root`). */
function themeKeyOf(selector: string): string {
  const m = selector.match(/data-oracle-theme="([^"]+)"/);
  return m ? m[1] : "light";
}

interface ParsedBlock {
  identity: string;
  themeKey: string;
  customProps: Map<string, string>;
}

// ─── B2: judge every context on its EFFECTIVE values, not just a "complete"
// block found by anchoring on one token ─────────────────────────────────────

/**
 * `chain[0]` is the block's own declarations; `chain[1..]` are every
 * PRECEDING block (document order) whose selector targets the same
 * `data-oracle-theme`, nearest first — "resolved within the SAME block then
 * up the cascade the file defines" (B1/B2). A context overriding only a
 * SUBSET of the eight tokens (the gate's M6) still yields all eight: the
 * ones it declares itself, the rest inherited.
 */
function buildScopeChain(
  blocks: ParsedBlock[],
  index: number,
): Map<string, string>[] {
  const target = blocks[index];
  const chain: Map<string, string>[] = [target.customProps];
  for (let i = index - 1; i >= 0; i--) {
    if (blocks[i].themeKey === target.themeKey) {
      chain.push(blocks[i].customProps);
    }
  }
  return chain;
}

function lookupInChain(
  chain: Map<string, string>[],
  key: string,
): string | undefined {
  for (const scope of chain) {
    const value = scope.get(key);
    if (value !== undefined) return value;
  }
  return undefined;
}

// ─── B1: compare resolved colour VALUES, not declaration text ─────────────

function expandShorthand(digits: string): string {
  // 3- or 4-digit hex shorthand: each character is one channel, doubled.
  return digits.length <= 4
    ? digits
        .split("")
        .map((c) => c + c)
        .join("")
    : digits;
}

function formatRgba(r: number, g: number, b: number, a: number): string {
  // Fixed precision so `1`, `1.0` and `100%` all collapse to the same
  // string; 4 decimals is far past this file's 1-2 significant digits.
  return `rgba(${r}, ${g}, ${b}, ${Number(a.toFixed(4))})`;
}

/**
 * Parses a `#hex` or `rgb()`/`rgba()` colour literal (comma or space
 * syntax, either alpha form) into a canonical `rgba(r, g, b, a)` string, so
 * two different NOTATIONS of the same colour compare equal while two
 * genuinely different colours still compare different (OBS-1: `#4ADE80` ==
 * `#4ade80`; `rgba(125,211,252,0.14)` == `rgba(125, 211, 252, 0.14)`; hex ==
 * the equivalent `rgb()`). Throws naming the raw input on any other
 * notation — never silently treated as distinct or equal.
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
 * `var(--x)` indirection at a time through the scope chain (a fallback
 * argument is itself resolved the same way). An unresolvable reference —
 * no matching custom property anywhere in the chain, and no fallback —
 * throws naming the token; it is never treated as distinct by default.
 */
function resolveValue(
  raw: string,
  chain: Map<string, string>[],
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
  const refValue = lookupInChain(chain, refName);
  if (refValue !== undefined) {
    return resolveValue(refValue, chain, label, depth + 1);
  }
  if (fallback !== undefined) {
    return resolveValue(fallback, chain, label, depth + 1);
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
 * selector/at-rule (B3), after stripping CSS comments (B4). Throws loudly,
 * naming the block and the missing token, if fewer than four effective
 * foreground or background values can be found for a context anywhere in
 * its scope chain (B5 — the blind-scan floor).
 */
export function parseEffectiveBlocks(css: string): EffectiveBlock[] {
  const raw = splitBlocks(stripComments(css));

  const blocks: ParsedBlock[] = raw.map((b) => ({
    identity: b.atRule
      ? `${normalizeWhitespace(b.atRule)} :: ${b.selector}`
      : b.selector,
    themeKey: themeKeyOf(b.selector),
    customProps: extractCustomProps(b.declarations),
  }));

  const effective: EffectiveBlock[] = [];
  blocks.forEach((block, index) => {
    if (!ALL_STATE_KEYS.some((key) => block.customProps.has(key))) return;

    const chain = buildScopeChain(blocks, index);

    const fgRaw = buildStateValues((name) => {
      const raw = lookupInChain(chain, FG_KEYS[name]);
      if (raw === undefined) {
        throw new Error(
          `${block.identity}: missing ${FG_KEYS[name]} (not declared here or in an inherited same-theme block)`,
        );
      }
      return raw;
    });
    const fg = buildStateValues((name) =>
      resolveValue(fgRaw[name], chain, `${block.identity} foreground`),
    );
    const bg = buildStateValues((name) => {
      const raw = lookupInChain(chain, BG_KEYS[name]);
      if (raw === undefined) {
        throw new Error(
          `${block.identity}: missing ${BG_KEYS[name]} (not declared here or in an inherited same-theme block)`,
        );
      }
      return resolveValue(raw, chain, `${block.identity} background`);
    });

    effective.push({ identity: block.identity, fg, bg, fgRaw });
  });
  return effective;
}
